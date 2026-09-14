#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lib/static_analysis.py —— 静态分析模块

输入: 目标文件 + 关键词
输出: 关键函数定位 / 指令序列 / 跳转图 / 校验逻辑识别

只依赖 Python 3.8+ 标准库。
"""
from __future__ import annotations

import os
import re
import struct
from typing import Any, Dict, List, Optional

# x86 指令识别(简化: 常见模式)
CMP_PATTERNS = [
    (b"\x3d", "cmp eax, imm32"),
    (b"\x3b", "cmp reg, reg/mem"),
    (b"\x83\xf8", "cmp eax, imm8"),
    (b"\x83\xf9", "cmp ecx, imm8"),
    (b"\x81\xf8", "cmp eax, imm32"),
]
MOV_PATTERNS = [
    (b"\xb8", "mov eax, imm32"),
    (b"\xb9", "mov ecx, imm32"),
    (b"\x8b", "mov reg, mem"),
]
CALL_PATTERNS = [
    (b"\xe8", "call rel32"),
    (b"\xff\x15", "call [mem]"),
]
JMP_PATTERNS = [
    (b"\x74", "JE/JZ"), (b"\x75", "JNE/JNZ"), (b"\x70", "JO"),
    (b"\x71", "JNO"), (b"\x72", "JB"), (b"\x73", "JAE"),
    (b"\x76", "JBE"), (b"\x77", "JA"), (b"\x78", "JS"),
    (b"\x79", "JNS"), (b"\x7c", "JL"), (b"\x7d", "JGE"),
    (b"\x7e", "JLE"), (b"\x7f", "JG"),
    (b"\xeb", "JMP short"), (b"\xe9", "JMP rel32"),
]
RET_PATTERNS = [(b"\xc3", "ret"), (b"\xc2", "ret imm16")]


class StaticAnalyzer:
    """静态分析器。"""

    def __init__(self, path: str, keywords: Optional[List[str]] = None) -> None:
        self.path = path
        self.keywords = keywords or ["password", "key", "卡密", "激活",
                                     "license", "serial", "check", "valid"]
        self.data = b""
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.path):
            try:
                with open(self.path, "rb") as f:
                    self.data = f.read()
            except OSError:
                self.data = b""

    # -- 关键函数定位 ------------------------------------------------------
    def locate_key_functions(self) -> Dict[str, Any]:
        """按关键词定位(字符串引用附近的反汇编区域)。"""
        results = []
        for kw in self.keywords:
            kwb = kw.encode() if isinstance(kw, str) else kw
            for m in re.finditer(re.escape(kwb), self.data):
                off = m.start()
                results.append({"keyword": kw, "offset": off,
                                "context": self._context(off)})
        return {"finds": results[:30], "count": len(results)}

    def _context(self, off: int, size: int = 32) -> str:
        """取偏移附近的字节(hex)。"""
        start = max(0, off - 8)
        end = min(len(self.data), off + size)
        return self.data[start:end].hex(" ")

    # -- 指令序列 ----------------------------------------------------------
    def instruction_sequence(self, offset: int, count: int = 10) -> List[Dict[str, Any]]:
        """从 offset 开始解码指令序列(简化线性扫描)。"""
        seq = []
        i = offset
        while i < len(self.data) and len(seq) < count:
            instr = self._decode_one(i)
            if not instr:
                i += 1
                continue
            seq.append(instr)
            i += instr["size"]
        return seq

    def _decode_one(self, off: int) -> Optional[Dict[str, Any]]:
        d = self.data
        if off >= len(d):
            return None
        b = d[off]
        # 跳转
        for sig, name in JMP_PATTERNS:
            if d[off:off + len(sig)] == sig:
                size = 2 if sig in (b"\x74", b"\x75", b"\x70", b"\x71", b"\x72",
                                    b"\x73", b"\x76", b"\x77", b"\x78", b"\x79",
                                    b"\x7c", b"\x7d", b"\x7e", b"\x7f", b"\xeb") else 5
                size = 2 if len(sig) == 1 and sig != b"\xe9" else size
                return {"offset": off, "mnemonic": name,
                        "bytes": d[off:off + size].hex(" "), "size": size}
        # CMP
        for sig, name in CMP_PATTERNS:
            if d[off:off + len(sig)] == sig:
                size = 6 if sig == b"\x3d" else (3 if sig == b"\x83\xf8" else 2)
                return {"offset": off, "mnemonic": name,
                        "bytes": d[off:off + size].hex(" "), "size": size}
        # MOV
        for sig, name in MOV_PATTERNS:
            if d[off:off + len(sig)] == sig:
                size = 5 if sig == b"\xb8" else 2
                return {"offset": off, "mnemonic": name,
                        "bytes": d[off:off + size].hex(" "), "size": size}
        # CALL
        for sig, name in CALL_PATTERNS:
            if d[off:off + len(sig)] == sig:
                size = 5 if sig == b"\xe8" else 6
                return {"offset": off, "mnemonic": name,
                        "bytes": d[off:off + size].hex(" "), "size": size}
        # RET
        for sig, name in RET_PATTERNS:
            if d[off:off + len(sig)] == sig:
                return {"offset": off, "mnemonic": name,
                        "bytes": d[off:off + len(sig)].hex(" "), "size": len(sig)}
        return None

    # -- 跳转图 ------------------------------------------------------------
    def jump_graph(self) -> Dict[str, Any]:
        """扫描所有跳转, 构建目标图。"""
        edges = []
        i = 0
        while i < len(self.data):
            for sig, name in JMP_PATTERNS:
                if self.data[i:i + len(sig)] == sig:
                    src = i
                    if sig == b"\xeb":
                        rel = struct.unpack("b", self.data[i + 1:i + 2])[0]
                        dst = i + 2 + rel
                    elif sig == b"\xe9":
                        rel = struct.unpack("<i", self.data[i + 1:i + 5])[0]
                        dst = i + 5 + rel
                    elif len(sig) == 1:
                        rel = struct.unpack("b", self.data[i + 1:i + 2])[0]
                        dst = i + 2 + rel
                    else:
                        dst = i + len(sig)
                    edges.append({"from": src, "to": dst, "type": name})
                    i += 2 if len(sig) == 1 else 5
                    break
            i += 1
        return {"edges": edges, "count": len(edges)}

    # -- 校验逻辑识别 --------------------------------------------------------
    def identify_checks(self) -> Dict[str, Any]:
        """识别校验逻辑: cmp+jcc 配对。"""
        checks = []
        i = 0
        while i < len(self.data) - 1:
            # 找 CMP
            is_cmp = False
            cmp_name = ""
            for sig, name in CMP_PATTERNS:
                if self.data[i:i + len(sig)] == sig:
                    is_cmp = True
                    cmp_name = name
                    i += len(sig)
                    break
            if is_cmp:
                # 后面找跳转
                for j in range(i, min(i + 8, len(self.data))):
                    for jsig, jname in JMP_PATTERNS:
                        if self.data[j:j + len(jsig)] == jsig:
                            checks.append({
                                "cmp_offset": i - 1, "cmp": cmp_name,
                                "jmp_offset": j, "jmp": jname,
                                "pattern": "cmp+条件跳转=校验分支",
                            })
                            break
                    else:
                        continue
                    break
                i += 1
                continue
            i += 1
        return {"checks": checks[:20], "count": len(checks)}

    # -- 完整报告 ------------------------------------------------------------
    def report(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "locate": self.locate_key_functions(),
            "jump_graph": self.jump_graph(),
            "checks": self.identify_checks(),
        }


# ---------------------------------------------------------------- CLI
def main(argv: Optional[List[str]] = None) -> int:
    import argparse, json
    p = argparse.ArgumentParser(prog="static-analysis")
    p.add_argument("target", help="目标文件")
    p.add_argument("--keyword", action="append", default=[], help="关键词(可多次)")
    p.add_argument("--offset", type=lambda x: int(x, 0), default=None,
                   help="指令序列起始偏移(hex)")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    kw = args.keyword or None
    a = StaticAnalyzer(args.target, kw)
    rep = a.report()
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        loc = rep["locate"]
        print(f"=== 静态分析: {args.target} ===")
        print(f"关键词定位: {loc['count']} 处")
        for f in loc["finds"][:10]:
            print(f"  {f['keyword']} @ {f['offset']:#x}: {f['context'][:40]}")
        if args.offset is not None:
            seq = a.instruction_sequence(args.offset)
            print(f"\n指令序列 @ {args.offset:#x}:")
            for s in seq:
                print(f"  {s['offset']:#x} {s['mnemonic']:<18} {s['bytes']}")
        jg = rep["jump_graph"]
        print(f"\n跳转图: {jg['count']} 条边")
        for e in jg["edges"][:8]:
            print(f"  {e['from']:#x} --{e['type']}--> {e['to']:#x}")
        chk = rep["checks"]
        print(f"\n校验逻辑: {chk['count']} 个 (cmp+条件跳转)")
        for c in chk["checks"][:8]:
            print(f"  cmp@{c['cmp_offset']:#x} {c['cmp']} + "
                  f"jmp@{c['jmp_offset']:#x} {c['jmp']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
