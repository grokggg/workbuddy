#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lib/analysis_v2.py —— 分析模块 v2(静态 + 动态行为建模)

v1 失败点驱动的重构:
  F3: 真实二进制校验识别率低 -> 增加指令模式库 + API 引用 + 行为签名

只依赖 Python 3.8+ 标准库。
"""
from __future__ import annotations

import os
import re
import struct
from typing import Any, Dict, List, Optional

# 校验相关指令模式库
CHECK_PATTERNS: List[Dict[str, Any]] = [
    {"name": "常量比较", "regex": rb"\xb8[\x00-\xff]{4}\x3b[\x00-\xff]{1}",
     "desc": "mov eax,const + cmp reg,eax"},
    {"name": "cmp-imm32", "regex": rb"\x3d[\x00-\xff]{4}",
     "desc": "cmp eax, imm32(直接立即数比较, M26 新增)"},
    {"name": "movzx+cmp(卡密)", "regex": rb"\x0f\xb6\x00\x3d[\x00-\xff]{4}",
     "desc": "movzx eax,byte[rax] + cmp eax,imm32(卡密首字符比较, M26)"},
    {"name": "cmp+jcc", "regex": rb"\x3b[\x00-\xff]{1}\x74|\x83\xf8[\x00-\xff]{1}\x75",
     "desc": "cmp 后接条件跳转(校验分支)"},
    {"name": "时间差", "regex": rb"\x0f\x31|\x0f\x01\xc8",
     "desc": "rdtsc/rdtscp(反调试)"},
]

SENSITIVE_API = [
    "IsDebuggerPresent", "CheckRemoteDebuggerPresent",
    "NtQueryInformationProcess", "GetTickCount", "QueryPerformanceCounter",
    "VirtualProtect", "WriteProcessMemory", "CreateRemoteThread",
    "LoadLibrary", "GetProcAddress", "RegOpenKeyEx",
]

ELF_SECTIONS = [b".text", b".data", b".bss", b".rodata", b".init", b".fini",
                b".dynsym", b".strtab", b".shstrtab", b".plt", b".got"]


class AnalysisV2:
    """分析 v2。"""

    def __init__(self, path: str) -> None:
        self.path = path
        self.data = b""
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.path):
            try:
                with open(self.path, "rb") as f:
                    self.data = f.read()
            except OSError:
                self.data = b""

    # -- 静态: 校验模式扫描 ------------------------------------------------
    def static_scan(self) -> Dict[str, Any]:
        hits = []
        for p in CHECK_PATTERNS:
            for m in re.finditer(p["regex"], self.data):
                hits.append({
                    "pattern": p["name"],
                    "offset": m.start(),
                    "bytes": self.data[m.start():m.start() + 8].hex(" "),
                    "desc": p["desc"],
                })
        return {"hits": hits[:40], "count": len(hits)}

    # -- 静态: 敏感 API 引用 ------------------------------------------------
    def api_scan(self) -> Dict[str, Any]:
        found = []
        for api in SENSITIVE_API:
            b = api.encode()
            if b in self.data:
                off = self.data.index(b)
                found.append({"api": api, "offset": off})
        return {"apis": found}

    # -- 行为建模(离线静态近似) ----------------------------------------------
    def behavior_model(self) -> Dict[str, Any]:
        behaviors = []
        apis = {a["api"] for a in self.api_scan()["apis"]}
        if "IsDebuggerPresent" in apis or "NtQueryInformationProcess" in apis:
            behaviors.append({"behavior": "anti-debug", "confidence": 0.8,
                              "suggest": "动态调试时需 patch 检测点"})
        if "VirtualProtect" in apis and "WriteProcessMemory" in apis:
            behaviors.append({"behavior": "self-modifying", "confidence": 0.7,
                              "suggest": "运行期改写代码, 需配合动态分析"})
        if "GetTickCount" in apis or "QueryPerformanceCounter" in apis:
            behaviors.append({"behavior": "timing-check", "confidence": 0.6,
                              "suggest": "存在时间差检测(反调试)"})
        if "RegOpenKeyEx" in apis:
            behaviors.append({"behavior": "registry-access", "confidence": 0.5,
                              "suggest": "可能读取注册表(反VM/配置)"})
        if not behaviors:
            behaviors.append({"behavior": "plain", "confidence": 0.9,
                              "suggest": "未发现特殊行为特征"})
        return {"behaviors": behaviors}

    # -- ELF 节表 ------------------------------------------------------------
    def elf_sections(self) -> Dict[str, Any]:
        d = self.data
        if d[:4] != b"\x7fELF":
            return {"sections": []}
        # 简化: 扫常见节名
        secs = []
        for name in ELF_SECTIONS:
            idx = d.find(name)
            if idx != -1:
                secs.append({"name": name.decode(), "offset": idx})
        return {"sections": secs}

    # -- 完整报告 ------------------------------------------------------------
    def report(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "static": self.static_scan(),
            "apis": self.api_scan(),
            "behavior": self.behavior_model(),
            "elf_sections": self.elf_sections(),
        }


# ---------------------------------------------------------------- CLI
def main(argv: Optional[List[str]] = None) -> int:
    import argparse, json
    p = argparse.ArgumentParser(prog="analysis-v2")
    p.add_argument("target", help="目标文件")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    a = AnalysisV2(args.target)
    rep = a.report()
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        print(f"=== 分析 v2: {args.target} ===")
        st = rep["static"]
        print(f"校验模式: {st['count']} 处")
        for h in st["hits"][:8]:
            print(f"  {h['offset']:#x} [{h['pattern']}] {h['bytes'][:20]}")
        apis = rep["apis"]["apis"]
        print(f"敏感 API: {len(apis)} 个")
        for a_ in apis[:8]:
            print(f"  {a_['offset']:#x} {a_['api']}")
        print(f"\n行为建模:")
        for b in rep["behavior"]["behaviors"]:
            print(f"  [{b['confidence']}] {b['behavior']}: {b['suggest']}")
        secs = rep["elf_sections"]["sections"]
        if secs:
            print(f"\nELF 节: {[s['name'] for s in secs[:10]]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
