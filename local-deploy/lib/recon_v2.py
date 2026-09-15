#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lib/recon_v2.py —— 探测模块 v2(真实保护机制识别)

v1 失败点驱动的重构:
  F1: 熵检测不区分代码段/数据段 -> 分段熵分布 + 段级判断
  F2: 共享库入口点 0x0 误判 -> 按类型区分 ELF EXEC/DYN
  F3: 无真实保护特征 -> 新增加壳/反调试/反VM/完整性/反重打包 5 类识别

识别范围:
  1. 加壳: UPX / VMProtect / Themida / Enigma / ASPack
  2. 反调试: IsDebuggerPresent / NtQueryInformationProcess / PEB / 时间差
  3. 反VM: CPUID / VMWare 注册表 / 设备名 / 进程
  4. 完整性: 自校验 / 哈希 / 签名
  5. 反重打包: asar 校验 / APK 签名 / 段哈希

只依赖 Python 3.8+ 标准库。
"""
from __future__ import annotations

import math
import os
import re
import struct
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------- 基础

def _entropy(data: bytes) -> float:
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
    return h


# ---------------------------------------------------------------- 壳特征
# 格式: 壳名 -> {"sigs": [特征], "platforms": (支持的平台)}
#   pe = Windows PE / elf = Linux ELF / mac = Mach-O
# M24: PE 独有壳(ASPack/MPRESS/Themida/Enigma/Obsidium/EXE Stealth)只在 PE 格式检查
PACKER_MARKERS = {
    "UPX": {"sigs": [b"UPX!", b"UPX0", b"UPX1", b"UPX2", b"UPX3"],
            "platforms": ("pe", "elf", "mac")},
    "ASPack": {"sigs": [b"ASPack", b"ASPack 2.12", b"ASProtect"],
               "platforms": ("pe",)},
    "FSG": {"sigs": [b"FSG!"], "platforms": ("pe",)},
    "Petite": {"sigs": [b"Petite"], "platforms": ("pe",)},
    "MPRESS": {"sigs": [b"MPRESS"], "platforms": ("pe",)},
    "VMProtect": {"sigs": [b"VMProtect", b"VMProtectSDK"],
                  "platforms": ("pe", "elf", "mac")},
    "Themida": {"sigs": [b"Themida", b"WinLicense"], "platforms": ("pe",)},
    "Enigma": {"sigs": [b"Enigma Protector", b"EnigmaSDK"], "platforms": ("pe",)},
    "Obsidium": {"sigs": [b"Obsidium"], "platforms": ("pe",)},
    "EXE Stealth": {"sigs": [b"EXE Stealth"], "platforms": ("pe",)},
}

# 壳常见段名
PACKED_SECTION_NAMES = [b"UPX0", b"UPX1", b".aspack", b".adata", b".petite",
                        b".MPRESS", b".vmp0", b".vmp1", b".enigma", b".obs"]

# 正常 PE 段名(非壳)
NORMAL_SECTIONS = [b".text", b".data", b".rdata", b".bss", b".reloc",
                   b".idata", b".rsrc", b".CRT", b".tls"]


# ---------------------------------------------------------------- 反调试特征

ANTI_DEBUG_API = {
    "IsDebuggerPresent": b"IsDebuggerPresent",
    "CheckRemoteDebuggerPresent": b"CheckRemoteDebuggerPresent",
    "NtQueryInformationProcess": b"NtQueryInformationProcess",
    "NtSetInformationThread": b"NtSetInformationThread",
    "OutputDebugString": b"OutputDebugString",
    "GetTickCount(时间差)": b"GetTickCount",
    "QueryPerformanceCounter": b"QueryPerformanceCounter",
}

# PEB 检测: mov eax, fs:[0x30](x86) / mov rax, gs:[0x60](x64)
PEB_PATTERNS = [
    (b"\x64\xa1\x30\x00\x00\x00", "x86: mov eax, fs:[0x30] (PEB)"),
    (b"\x65\x48\x8b\x04\x25\x60\x00\x00\x00", "x64: mov rax, gs:[0x60] (PEB)"),
]


# ---------------------------------------------------------------- 反VM特征

ANTI_VM_STRINGS = [
    "VMware", "VirtualBox", "VBOX", "QEMU", "bochs",
    "vmmouse", "vmtoolsd", "vmware-tools",
]
# CPUID 特征
CPUID_PATTERNS = [
    (b"\x0f\xa2", "CPUID 指令"),
    (b"\x0f\x01\xc8", "RDTSCP(时间差)"),
]
# 反VM API(Windows)
ANTI_VM_API = [
    b"RegOpenKeyExA", b"EnumDisplayDevicesA", b"GetAdaptersInfo",
    b"SetupDiEnumDeviceInfo",
]


# ---------------------------------------------------------------- 完整性/反重打包

INTEGRITY_STRINGS = [
    "checksum", "CRC32", "md5", "sha1", "sha256", "self_check",
    "integrity_check", "tamper", "自校验", "完整性",
]
ANTI_REPACK_STRINGS = [
    "asar", "signature_check", "apk_sign", "code_sign", "integrity_verify",
    "签名校验", "重打包检测",
]


# ---------------------------------------------------------------- 主类

class ReconV2:
    """探测 v2: 真实保护机制识别。"""

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

    # -- 文件类型/格式 ----------------------------------------------------
    def format_info(self) -> Dict[str, Any]:
        d = self.data
        ft = "Unknown"
        kind = "?"
        if d[:2] == b"MZ" and b"PE\x00\x00" in d[:0x400]:
            ft = "PE"
            pe_off = struct.unpack("<I", d[0x3C:0x40])[0]
            machine = struct.unpack("<H", d[pe_off + 4:pe_off + 6])[0]
            arch = {0x14C: "x86", 0x8664: "x64", 0x1C0: "ARM",
                    0xAA64: "ARM64"}.get(machine, f"0x{machine:x}")
            # PE 子系统判断 exe/dll
            kind = "DLL" if b"PEL" in d[pe_off:pe_off + 4] else "EXE"
        elif d[:4] == b"\x7fELF":
            ft = "ELF"
            arch = {2: "x64", 3: "x86", 40: "ARM", 183: "ARM64"}.get(d[4], "?")
            etype = struct.unpack("<H", d[16:18])[0]
            # ET_EXEC=2, ET_DYN=3, ET_REL=1
            kind = {1: "REL(对象)", 2: "EXEC(可执行)", 3: "DYN(共享库/动态)",
                    4: "CORE"}.get(etype, f"0x{etype:x}")
        elif d[:4] in (b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf",
                       b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xce"):
            ft = "Mach-O"
            arch = "x64" if d[4] == 0x07 else "x86"
            kind = "?"  # F2 修复: 不再硬编码入口点
        elif d[:2] == b"#!":
            ft = "Script"
            arch = "?"
            kind = "脚本"
        elif self._is_asar(d):
            ft = "ASAR"
            arch = "?"
            kind = "Electron 归档"
        else:
            arch = "?"
        return {"file_type": ft, "arch": arch, "kind": kind}

    def _is_asar(self, d: bytes) -> bool:
        """asar 格式识别: [4B pickle][4B header size][4B json size][4B data size][json...]
        特征: header/json size 合理 + json 含 "files"。"""
        if len(d) < 24:
            return False
        try:
            hsize = struct.unpack("<I", d[4:8])[0]
            jsize = struct.unpack("<I", d[8:12])[0]
            dsize = struct.unpack("<I", d[12:16])[0]
            if 0x10 <= hsize <= 0x100000 and 0x10 <= jsize <= 0x100000:
                if b"files" in d[16:16 + jsize]:
                    return True
        except (struct.error, IndexError):
            pass
        return False
        return {"file_type": ft, "arch": arch, "kind": kind}

    # -- 分段熵分布(F1 修复) ------------------------------------------------
    def entropy_profile(self, chunk_size: int = 4096) -> Dict[str, Any]:
        """分段熵: 区分代码段(低熵)与壳段(高熵)。"""
        chunks = []
        d = self.data
        for i in range(0, min(len(d), 65536), chunk_size):
            chunk = d[i:i + chunk_size]
            if len(chunk) < 16:
                continue
            e = _entropy(chunk)
            chunks.append({"offset": i, "entropy": round(e, 2)})
        high = [c for c in chunks if c["entropy"] > 6.8]
        avg = sum(c["entropy"] for c in chunks) / len(chunks) if chunks else 0
        return {"chunks": chunks[:64], "high_entropy_count": len(high),
                "avg_entropy": round(avg, 2),
                "suspicious": len(high) > len(chunks) * 0.3}

    # -- 段表 -----------------------------------------------------------------
    def sections(self) -> Dict[str, Any]:
        d = self.data
        ft = self.format_info()["file_type"]
        if ft != "PE":
            return {"sections": []}
        pe_off = struct.unpack("<I", d[0x3C:0x40])[0]
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
            raw_size = struct.unpack("<I", d[o + 16:o + 20])[0]
            secs.append({"name": name, "raw_size": raw_size})
        return {"sections": secs}

    # -- 加壳识别 ----------------------------------------------------------
    def detect_packer(self) -> Dict[str, Any]:
        d = self.data
        # M24: 平台上下文 —— 只检查与文件格式匹配的壳特征
        fmt = self.format_info()
        plat = {"PE": "pe", "ELF": "elf", "Mach-O": "mac"}.get(
            fmt["file_type"], None)
        markers = []
        # 1. 特征字符串(带平台过滤)
        for name, meta in PACKER_MARKERS.items():
            platforms = meta["platforms"]
            if plat is not None and plat not in platforms:
                continue  # 平台不匹配, 跳过(修复 MPRESS 误报)
            for sig in meta["sigs"]:
                if sig in d:
                    markers.append(name)
                    break
        # 2. 段名(仅 PE)
        if fmt["file_type"] == "PE":
            secs = self.sections().get("sections", [])
            sec_names = [s["name"].encode() for s in secs]
            for psec in PACKED_SECTION_NAMES:
                if psec in sec_names:
                    markers.append(f"段名:{psec.decode()}")
        # 3. 熵分布
        prof = self.entropy_profile()
        ent_suspect = prof["suspicious"]
        # 4. 导入表异常(只有少量导入但代码巨大)
        imp = self.detect_imports()
        import_anomaly = len(imp.get("apis", [])) < 5 and len(d) > 100000
        packed = bool(markers) or (ent_suspect and import_anomaly)
        return {
            "packed": packed,
            "markers": markers,
            "entropy_suspicious": ent_suspect,
            "import_anomaly": import_anomaly,
            "entropy_avg": prof["avg_entropy"],
            "verdict": "加壳" if packed else "未见壳特征",
        }

    # -- 导入表 ------------------------------------------------------------
    def detect_imports(self) -> Dict[str, Any]:
        d = self.data
        apis = []
        for name in (b"CreateFile", b"ReadFile", b"WriteFile", b"RegOpenKey",
                     b"GetProcAddress", b"LoadLibrary", b"VirtualAlloc",
                     b"WinExec", b"ShellExecute", b"CreateProcess",
                     b"InternetOpen", b"OpenProcess", b"NtQueryInformationProcess"):
            if name in d:
                apis.append(name.decode())
        return {"apis": apis}

    # -- 反调试识别 ----------------------------------------------------------
    def detect_antidebug(self) -> Dict[str, Any]:
        d = self.data
        hits = []
        for name, sig in ANTI_DEBUG_API.items():
            if sig in d:
                hits.append(name)
        for pat, desc in PEB_PATTERNS:
            if pat in d:
                hits.append(desc)
        return {"detected": hits}

    # -- 反VM识别 ------------------------------------------------------------
    def detect_antivm(self) -> Dict[str, Any]:
        d = self.data
        hits = []
        for s in ANTI_VM_STRINGS:
            if s.encode() in d:
                hits.append(f"字符串:{s}")
        for pat, desc in CPUID_PATTERNS:
            if pat in d:
                hits.append(desc)
        for api in ANTI_VM_API:
            if api in d:
                hits.append(f"API:{api.decode()}")
        return {"detected": hits}

    # -- 完整性校验识别 ---------------------------------------------------------
    def detect_integrity(self) -> Dict[str, Any]:
        d = self.data
        hits = []
        for s in INTEGRITY_STRINGS:
            if s.encode() in d:
                hits.append(f"字符串:{s}")
        # 自校验代码模式: 读自身文件(FindFirstFile + ReadFile 组合)
        if b"GetModuleFileName" in d and b"ReadFile" in d:
            hits.append("自读取模式(GetModuleFileName+ReadFile)")
        return {"detected": hits}

    # -- 反重打包识别 -----------------------------------------------------------
    def detect_anti_repack(self) -> Dict[str, Any]:
        d = self.data
        hits = []
        for s in ANTI_REPACK_STRINGS:
            if s.encode() in d:
                hits.append(f"字符串:{s}")
        # asar 文件内嵌(检测 app.asar 引用)
        if b"app.asar" in d:
            hits.append("Electron asar 引用")
        return {"detected": hits}

    # -- 完整报告 ------------------------------------------------------------
    def report(self) -> Dict[str, Any]:
        if not self.load():
            return self.info
        self.info.update({
            "format": self.format_info(),
            "packer": self.detect_packer(),
            "antidebug": self.detect_antidebug(),
            "antivm": self.detect_antivm(),
            "integrity": self.detect_integrity(),
            "anti_repack": self.detect_anti_repack(),
            "imports": self.detect_imports(),
            "entropy": self.entropy_profile(),
        })
        return self.info


# ---------------------------------------------------------------- CLI
def main(argv: Optional[List[str]] = None) -> int:
    import argparse, json
    p = argparse.ArgumentParser(prog="recon-v2")
    p.add_argument("target", help="目标文件")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    r = ReconV2(args.target)
    rep = r.report()
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        fmt = rep["format"]
        print(f"=== 探测 v2: {args.target} ===")
        print(f"格式: {fmt['file_type']} | 架构: {fmt['arch']} | 类型: {fmt['kind']}")
        pk = rep["packer"]
        print(f"加壳: {pk['verdict']} (熵均值 {pk['entropy_avg']}) "
              f"标记: {pk['markers']}")
        ad = rep["antidebug"]
        print(f"反调试: {ad['detected'] or '未检测到'}")
        av = rep["antivm"]
        print(f"反VM: {av['detected'] or '未检测到'}")
        ig = rep["integrity"]
        print(f"完整性校验: {ig['detected'] or '未检测到'}")
        ar = rep["anti_repack"]
        print(f"反重打包: {ar['detected'] or '未检测到'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
