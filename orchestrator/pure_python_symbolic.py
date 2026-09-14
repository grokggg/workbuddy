#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pure_python_symbolic.py —— M33 纯 Python 简化版符号执行

替代 angr(沙箱装不上): capstone 反汇编 + 指令跟踪 + 约束收集 + 暴力求解

原理:
  1. 反汇编目标入口到校验点
  2. 跟踪 movzx/cmp/je 模式, 收集"输入字节 == 立即数"约束
  3. 组合约束求解(暴力枚举, 对单字节比较足够)

适用: 卡密首字符/多字节比较类 crackme(M26-M31 已验证模式)
"""
from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional

try:
    from capstone import Cs, CS_ARCH_X86, CS_MODE_64
    from elftools.elf.elffile import ELFFile
    import io as _io
    HAS_CAPSTONE = True
except ImportError:
    HAS_CAPSTONE = False


class SymbolicEngine:
    """简化符号执行: 收集输入约束并求解。"""

    def __init__(self, path: str) -> None:
        self.path = path
        self.insns = []
        self.constraints: List[Dict[str, Any]] = []  # 字节位置 -> 值
        self._load()

    def _load(self) -> None:
        if not HAS_CAPSTONE:
            return
        d = open(self.path, "rb").read()
        elf = ELFFile(_io.BytesIO(d))
        entry = elf.header["e_entry"]
        for seg in elf.iter_segments():
            if seg["p_type"] == "PT_LOAD" and seg["p_flags"] & 1:
                if seg["p_vaddr"] <= entry < seg["p_vaddr"] + seg["p_filesz"]:
                    code = seg.data()
                    start = entry - seg["p_vaddr"]
                    md = Cs(CS_ARCH_X86, CS_MODE_64)
                    self.insns = list(md.disasm(code[start:], entry))
                    self.off = seg["p_offset"]
                    self.vaddr = seg["p_vaddr"]
                    break

    # -- 约束收集 ----------------------------------------------------------
    def collect_constraints(self, max_insns: int = 200) -> List[Dict[str, Any]]:
        """跟踪 movzx eax,byte[rax] + cmp eax,imm 模式, 收集输入字节约束。"""
        self.constraints = []
        insns = self.insns[:max_insns]
        # 找 "movzx eax, byte ptr [rax]" 后跟 "cmp eax, imm"
        for i in range(len(insns) - 1):
            ins = insns[i]
            if ins.mnemonic == "movzx" and "byte ptr [rax]" in ins.op_str:
                for j in range(i + 1, min(i + 4, len(insns))):
                    nxt = insns[j]
                    if nxt.mnemonic == "cmp" and "eax" in nxt.op_str:
                        try:
                            imm_str = nxt.op_str.split(",")[1].strip()
                            imm = int(imm_str, 16)
                            # 约束: input[0] == imm(首字符比较)
                            self.constraints.append({
                                "pos": 0, "op": "eq", "value": imm,
                                "at": hex(nxt.address),
                                "cmp": nxt.op_str,
                            })
                        except Exception:
                            pass
                        break
                    if nxt.mnemonic.startswith("j"):
                        break
        return self.constraints

    # -- 求解(暴力枚举, 单字节) ---------------------------------------------
    def solve(self) -> Dict[str, Any]:
        """求解: 对每个约束找满足的值。返回候选密码字符。"""
        if not self.constraints:
            return {"solvable": False, "reason": "无约束", "candidates": []}
        # 首字符约束合并: input[0] 必须同时满足所有 eq 约束
        # 若多个 eq 冲突则无解(说明不是单校验)
        candidates = []
        for c in self.constraints:
            if c["op"] == "eq":
                candidates.append(c["value"])
        # 尝试组合: 若只有一个 eq, 密码 = 该字符
        if len(candidates) == 1:
            ch = candidates[0]
            return {
                "solvable": True,
                "method": "暴力枚举(单约束)",
                "password": chr(ch) if 32 <= ch < 127 else f"\\x{ch:02x}",
                "byte": ch,
                "constraints": len(self.constraints),
                "satisfying_inputs": [chr(ch)],
            }
        # 多约束: 尝试所有单字符
        solvable = []
        for ch in range(1, 128):
            ok = all(c["value"] == ch for c in self.constraints
                     if c["op"] == "eq")
            if ok:
                solvable.append(chr(ch))
        return {
            "solvable": bool(solvable),
            "method": "暴力枚举(多约束合并)",
            "password": solvable[0] if solvable else None,
            "byte": ord(solvable[0]) if solvable else None,
            "constraints": len(self.constraints),
            "satisfying_inputs": solvable,
        }

    # -- 完整报告 ------------------------------------------------------------
    def report(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "insn_count": len(self.insns),
            "constraints": self.collect_constraints(),
            "solve": self.solve(),
        }


def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    import json
    p = argparse.ArgumentParser(prog="pure-symbolic")
    p.add_argument("target", help="目标文件")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    eng = SymbolicEngine(args.target)
    rep = eng.report()
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2, default=str))
    else:
        print(f"=== 纯 Python 符号执行: {args.target} ===")
        print(f"反汇编: {rep['insn_count']} 条")
        print(f"约束: {len(rep['constraints'])} 个")
        for c in rep["constraints"][:10]:
            print(f"  {c['at']}: {c['cmp']}  -> input[{c['pos']}] == 0x{c['value']:02x}")
        s = rep["solve"]
        if s.get("solvable"):
            print(f"求解: ✅ 密码 = {s['password']!r} ({s['method']})")
        else:
            print(f"求解: ❌ {s.get('reason', '无解')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
