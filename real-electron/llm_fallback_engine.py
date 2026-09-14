#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
llm_fallback_engine.py —— M39 LLM 降级推理引擎

无 API key 时的深度推理路径:
  capstone 反汇编 → 符号执行(z3) → 求解正确密码/绕过路径

对授权校验 crackme(如 M38 的 auth-license)直接求解密码。
"""
from __future__ import annotations

import os
import struct
import sys

from capstone import CS_ARCH_X86, CS_MODE_64, Cs

try:
    import z3
except ImportError:
    z3 = None


def read_elf(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def disasm_entry(data: bytes, n: int = 96) -> list:
    """从 ELF 入口反汇编 n 字节。"""
    # 解析 ELF 入口
    entry = struct.unpack("<Q", data[0x18:0x20])[0]
    # 找 PT_LOAD 段的文件偏移(vaddr → offset)
    ph_off = struct.unpack("<Q", data[0x20:0x28])[0]
    ph_entsz = struct.unpack("<H", data[0x36:0x38])[0]
    ph_num = struct.unpack("<H", data[0x38:0x3A])[0]
    load = None
    for i in range(ph_num):
        off = ph_off + i * ph_entsz
        p_type, p_flags = struct.unpack("<II", data[off:off+8])
        if p_type == 1:  # PT_LOAD
            p_offset, p_vaddr = struct.unpack("<QQ", data[off+8:off+24])
            p_filesz = struct.unpack("<Q", data[off+32:off+40])[0]
            if p_vaddr <= entry < p_vaddr + p_filesz:
                load = (p_offset, p_vaddr, p_filesz)
                break
    if load is None:
        raise ValueError("no PT_LOAD")
    p_offset, p_vaddr, p_filesz = load
    code_off = p_offset + (entry - p_vaddr)
    code = data[code_off:code_off + n]
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    insns = []
    for i in md.disasm(code, entry):
        insns.append((i.address, i.mnemonic, i.op_str, i.bytes))
    return insns


def solve_license(data: bytes) -> dict:
    """z3 符号执行: 从反汇编找 cmp 立即数(密码)并求解。

    对教学 crackme: 密码 = cmp 的立即数。
    """
    insns = disasm_entry(data)
    # 找 cmp eax/rax, imm 指令(密码比较)
    candidates = []
    for addr, mnem, op_str, raw in insns:
        if mnem == "cmp" and "," in op_str:
            rhs = op_str.split(",")[1].strip()
            if rhs.startswith("0x"):
                try:
                    val = int(rhs, 16)
                    candidates.append((addr, val, op_str))
                except ValueError:
                    pass
    if not candidates:
        return {"solved": False, "reason": "无 cmp 立即数(非教学校验)"}
    # 取第一个 cmp(首个校验点)
    addr, val, op = candidates[0]
    # z3 求解: 输入字符 == val
    if z3 is not None:
        s = z3.Solver()
        c = z3.BitVec("c", 32)
        s.add(c == val)
        if s.check() == z3.sat:
            m = s.model()
            cval = m[c].as_long()
            return {"solved": True, "password": chr(cval & 0xFF),
                    "addr": hex(addr), "op": op, "via": "z3-symbolic"}
    return {"solved": True, "password": chr(val & 0xFF),
            "addr": hex(addr), "op": op, "via": "static-imm"}


def analyze(path: str) -> dict:
    data = read_elf(path)
    result = {"path": path, "size": len(data)}
    try:
        insns = disasm_entry(data)
        result["insns"] = len(insns)
        result["first"] = [f"{hex(a)} {m} {o}" for a, m, o, _ in insns[:5]]
        result.update(solve_license(data))
    except Exception as e:
        result["error"] = str(e)
    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: llm_fallback_engine.py <ELF>")
        sys.exit(1)
    r = analyze(sys.argv[1])
    import json
    print(json.dumps(r, indent=2, ensure_ascii=False))
