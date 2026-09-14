#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lib/recon.py —— 目标探测模块

输入: 目标文件路径
输出: 文件类型/架构/加壳检测/字符串/导入表/段结构/入口点

只依赖 Python 3.8+ 标准库。
"""
from __future__ import annotations

import math
import os
import re
import struct
from typing import Any, Dict, List, Optional


def _entropy(data: bytes) -> float:
    """香农熵(加壳检测核心指标)。"""
    if not data:
        return 0.0
    freq = [0] * 256
    for b in data:
        freq[b] += 1
    h = 0.0
    for c in freq:
        if c:
            p = c / len(data)
            h -= p * math.log2(p)
    return round(h, 3)


class Recon:
    """目标文件探测。"""

    def __init__(self, path: str) -> None:
        self.path = path
        self.data = b""
        self.info: Dict[str, Any] = {}

    def load(self) -> bool:
        if not os.path.exists(self.path):
            self.info["error"] = f"文件不存在: {self.path}"
            return False
        try:
            with open(self.path, "rb") as f:
                self.data = f.read()
        except OSError as e:
            self.info["error"] = str(e)
            return False
        self.info["size"] = len(self.data)
        return True

    # -- 文件类型 ----------------------------------------------------------
    def file_type(self) -> str:
        d = self.data
        if d[:2] == b"MZ" and b"PE\x00\x00" in d[:0x400]:
            return "PE"
        if d[:4] == b"\x7fELF":
            return "ELF"
        if d[:4] in (b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf",
                     b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xce"):
            return "Mach-O"
        if d[:2] == b"#!":
            return "Script"
        return "Unknown"

    # -- 架构 ------------------------------------------------------------
    def arch(self) -> str:
        d = self.data
        ft = self.file_type()
        if ft == "PE":
            pe_off = struct.unpack("<I", d[0x3C:0x40])[0]
            machine = struct.unpack("<H", d[pe_off + 4:pe_off + 6])[0]
            return {0x14C: "x86", 0x8664: "x64", 0x1C0: "ARM",
                    0xAA64: "ARM64"}.get(machine, f"0x{machine:x}")
        if ft == "ELF":
            return {2: "x64", 3: "x86", 40: "ARM", 183: "ARM64"}.get(
                d[4], f"0x{d[4]:x}")
        if ft == "Mach-O":
            return "x64" if d[4] == 0x07 else "x86"
        return "?"

    # -- 加壳检测 ----------------------------------------------------------
    def packed(self) -> Dict[str, Any]:
        """加壳检测: 熵 + 特征。"""
        d = self.data
        sample = d[:min(len(d), 4096)]
        ent = _entropy(sample)
        # 壳特征
        markers = []
        for sig in (b"UPX", b"ASPack", b"FSG", b"Petite", b"MPRESS",
                    b"Themida", b"VMProtect", b"Enigma"):
            if sig in d[:len(d)]:
                markers.append(sig.decode())
        verdict = "可疑" if (ent > 6.5 or markers) else "正常"
        return {"entropy": ent, "markers": markers, "verdict": verdict}

    # -- 字符串提取 ----------------------------------------------------------
    def strings(self, min_len: int = 4,
                sensitive: Optional[List[str]] = None) -> Dict[str, Any]:
        """提取字符串 + 敏感词过滤。"""
        sens = sensitive or ["password", "key", "secret", "token", "license",
                             "activation", "卡密", "激活", "serial", "login",
                             "admin", "crack", "注册"]
        found = re.findall(rb"[\x20-\x7e]{%d,}" % min_len, self.data)
        strs = [s.decode("ascii", errors="ignore") for s in found]
        hits = [s for s in strs if any(k.lower() in s.lower() for k in sens)]
        return {"total": len(strs), "sensitive": hits[:30],
                "sample": strs[:20]}

    # -- 导入表 ------------------------------------------------------------
    def imports(self) -> Dict[str, Any]:
        """PE 导入表分析(简化: 找常见 API 名)。"""
        d = self.data
        apis = []
        for name in (b"CreateFile", b"ReadFile", b"WriteFile", b"RegOpenKey",
                     b"GetProcAddress", b"LoadLibrary", b"VirtualAlloc",
                     b"WinExec", b"ShellExecute", b"CreateProcess",
                     b"InternetOpen", b"HttpSendRequest", b"OpenProcess"):
            if name in d:
                apis.append(name.decode())
        return {"apis": apis}

    # -- 段结构 ------------------------------------------------------------
    def sections(self) -> Dict[str, Any]:
        """PE 节表分析。"""
        d = self.data
        ft = self.file_type()
        if ft != "PE":
            return {"note": "非 PE, 跳过节表"}
        pe_off = struct.unpack("<I", d[0x3C:0x40])[0]
        # 节表在 optional header 之后
        opt_size = struct.unpack("<H", d[pe_off + 20:pe_off + 22])[0]
        sec_off = pe_off + 24 + opt_size
        secs = []
        for i in range(20):
            o = sec_off + i * 40
            if o + 40 > len(d):
                break
            name = d[o:o + 8].rstrip(b"\x00").decode(errors="ignore")
            if not name:
                break
            vsize = struct.unpack("<I", d[o + 8:o + 12])[0]
            raw_size = struct.unpack("<I", d[o + 16:o + 20])[0]
            secs.append({"name": name, "virtual_size": vsize,
                         "raw_size": raw_size})
        return {"sections": secs}

    # -- 入口点 ------------------------------------------------------------
    def entry_point(self) -> Dict[str, Any]:
        d = self.data
        ft = self.file_type()
        if ft == "PE":
            pe_off = struct.unpack("<I", d[0x3C:0x40])[0]
            ep = struct.unpack("<I", d[pe_off + 24 + 16:pe_off + 24 + 20])[0]
            return {"ep": hex(ep), "raw": ep}
        if ft == "ELF":
            # e_entry at offset 0x18 (x64) / 0x18 (x86)
            if len(d) > 0x20:
                ep = struct.unpack("<Q", d[0x18:0x20])[0] if d[4] == 2 else \
                    struct.unpack("<I", d[0x18:0x1C])[0]
                return {"ep": hex(ep), "raw": ep}
        return {"note": "无法解析"}

    # -- 完整报告 ------------------------------------------------------------
    def report(self) -> Dict[str, Any]:
        if not self.load():
            return self.info
        ft = self.file_type()
        self.info.update({
            "file_type": ft,
            "arch": self.arch(),
            "packed": self.packed(),
            "strings": self.strings(),
            "imports": self.imports(),
            "sections": self.sections(),
            "entry_point": self.entry_point(),
        })
        return self.info


# ---------------------------------------------------------------- CLI
def main(argv: Optional[List[str]] = None) -> int:
    import argparse, json
    p = argparse.ArgumentParser(prog="recon")
    p.add_argument("target", help="目标文件")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    r = Recon(args.target)
    rep = r.report()
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        print(f"=== 目标探测: {args.target} ===")
        print(f"文件类型: {rep.get('file_type','?')} | 架构: {rep.get('arch','?')}")
        print(f"大小: {rep.get('size',0)} 字节")
        pkg = rep.get("packed", {})
        print(f"加壳: {pkg.get('verdict','?')} (熵 {pkg.get('entropy',0)})"
              f" 特征: {pkg.get('markers',[])}")
        st = rep.get("strings", {})
        print(f"字符串: {st.get('total',0)} 个, 敏感 {len(st.get('sensitive',[]))} 个")
        if st.get("sensitive"):
            print(f"  敏感: {st['sensitive'][:8]}")
        imp = rep.get("imports", {})
        if imp.get("apis"):
            print(f"导入 API: {imp['apis'][:10]}")
        secs = rep.get("sections", {})
        if secs.get("sections"):
            print(f"节表: {[s['name'] for s in secs['sections'][:8]]}")
        ep = rep.get("entry_point", {})
        if "ep" in ep:
            print(f"入口点: {ep['ep']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
