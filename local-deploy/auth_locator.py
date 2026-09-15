#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
auth_locator.py —— 通用授权函数定位器(方法论 + 可执行)

对 5 种授权类型给出 capstone 反汇编定位规则:
  1. 字符串引用型   : 扫 .rodata 授权字符串 → 找引用位置(xref)
  2. 比较型         : cmp + jcc 模式识别(校验点)
  3. 签名验证型     : 找 RSA/Ed25519 相关调用(call 到 crypto 函数)
  4. 时间型         : 找 time()/gettimeofday() 调用(PLT)
  5. 在线型         : 找 socket/connect/send/recv/curl 调用

定位规则是"模式 → 信号 → 候选点", 输出候选偏移(不自动 patch)。
"""
from __future__ import annotations

import os
import re
import struct
import sys

from capstone import CS_ARCH_X86, CS_MODE_64, Cs
from capstone.x86 import X86_OP_REG, X86_OP_IMM, X86_OP_MEM

# 授权字符串(用于字符串引用型)
AUTH_STRINGS = [
    b"license", b"licence", b"serial", b"activation", b"registered",
    b"unregistered", b"trial", b"expired", b"invalid key", b"valid key",
    b"key file", b"registration",
]


class AuthLocator:
    def __init__(self, path: str):
        self.path = path
        with open(path, "rb") as f:
            self.data = f.read()
        self.md = Cs(CS_ARCH_X86, CS_MODE_64)
        self.md.detail = True
        self._load_elf()

    def _load_elf(self):
        d = self.data
        self.entry = struct.unpack("<Q", d[0x18:0x20])[0]
        ph_off = struct.unpack("<Q", d[0x20:0x28])[0]
        ph_entsz = struct.unpack("<H", d[0x36:0x38])[0]
        ph_num = struct.unpack("<H", d[0x38:0x3A])[0]
        self.segments = []
        for i in range(ph_num):
            off = ph_off + i * ph_entsz
            p_type, p_flags = struct.unpack("<II", d[off:off+8])
            if p_type == 1:
                p_offset, p_vaddr = struct.unpack("<QQ", d[off+8:off+24])
                p_filesz = struct.unpack("<Q", d[off+32:off+40])[0]
                self.segments.append((p_offset, p_vaddr, p_filesz, p_flags))
        # 入口段
        for (po, pv, psz, pf) in self.segments:
            if pv <= self.entry < pv + psz:
                self.code_off = po + (self.entry - pv)
                self.code_va = self.entry
                self.code_size = psz - (self.entry - pv)
                break

    def va_to_off(self, va: int) -> int | None:
        for (po, pv, psz, _) in self.segments:
            if pv <= va < pv + psz:
                return po + (va - pv)
        return None

    def off_to_va(self, off: int) -> int | None:
        for (po, pv, psz, _) in self.segments:
            if po <= off < po + psz:
                return pv + (off - po)
        return None

    def disasm(self, start_off: int, size: int = 0x400) -> list:
        """反汇编一段(从文件偏移 start_off 开始)。"""
        code = self.data[start_off:start_off + size]
        base = self.off_to_va(start_off) or 0
        insns = []
        for i in self.md.disasm(code, base):
            insns.append((i.address, i.mnemonic, i.op_str, i.bytes))
        return insns

    # ── 1. 字符串引用型 ──
    def find_string_refs(self) -> list:
        """扫授权字符串 → 找 .rodata 位置 → 找 xref(lea rip+disp 引用)。"""
        hits = []
        for pat in AUTH_STRINGS:
            for m in re.finditer(re.escape(pat), self.data, re.IGNORECASE):
                str_off = m.start()
                str_va = self.off_to_va(str_off)
                if str_va is None:
                    continue
                hits.append((str_va, pat.decode(errors="ignore")))
        # 找 xref: 反汇编入口段, 找 lea reg, [rip+disp] 且目标命中字符串
        refs = []
        insns = self.disasm(self.code_off, min(self.code_size, 0x4000))
        for addr, mnem, op_str, raw in insns:
            if mnem in ("lea", "mov") and "rip" in op_str:
                # 解析 rip-relative: lea reg, [rip + disp]
                m2 = re.search(r"\[rip \+ (0x[0-9a-f]+)\]", op_str)
                if m2:
                    disp = int(m2.group(1), 16)
                    target = (addr + len(raw) + disp) & 0xFFFFFFFFFFFFFFFF
                    for (sva, sname) in hits:
                        if abs(target - sva) < 8:
                            refs.append({"insn_addr": hex(addr), "insn": f"{mnem} {op_str}",
                                         "string_va": hex(sva), "string": sname})
        return refs

    # ── 2. 比较型 ──
    def find_cmp_jcc(self) -> list:
        """找 cmp + jcc 模式(校验点候选)。"""
        insns = self.disasm(self.code_off, min(self.code_size, 0x4000))
        cands = []
        for i in range(len(insns) - 1):
            addr, mnem, op_str, raw = insns[i]
            if mnem == "cmp":
                nxt_addr, nxt_mnem, nxt_op, nxt_raw = insns[i + 1]
                if nxt_mnem in ("je", "jne", "jz", "jnz", "jg", "jl", "jge", "jle"):
                    cands.append({"cmp_addr": hex(addr), "cmp": f"cmp {op_str}",
                                  "jcc_addr": hex(nxt_addr), "jcc": nxt_mnem,
                                  "jcc_target": nxt_op})
        return cands

    # ── 3. 签名验证型 ──
    def find_crypto_calls(self) -> list:
        """找 crypto 相关 call(RSA/Ed25519 验证函数)。"""
        # 从导入段找 crypto 符号名(简化: 字符串命中)
        crypto_names = [b"RSA_verify", b"ED25519", b"EVP_DigestVerify", b"crypto_sign",
                        b"verify", b"BN_bin2bn"]
        found = []
        for pat in crypto_names:
            for m in re.finditer(re.escape(pat), self.data, re.IGNORECASE):
                va = self.off_to_va(m.start())
                if va:
                    found.append((va, pat.decode()))
        # 找 call 到这些地址(或 call 到 PLT 附近)
        calls = []
        insns = self.disasm(self.code_off, min(self.code_size, 0x4000))
        for addr, mnem, op_str, raw in insns:
            if mnem == "call" and op_str.startswith("0x"):
                tgt = int(op_str, 16)
                for (va, name) in found:
                    if abs(tgt - va) < 0x100:
                        calls.append({"call_addr": hex(addr), "call": f"call {op_str}",
                                      "crypto": name})
        return calls

    # ── 4. 时间型 ──
    def find_time_calls(self) -> list:
        """找 time()/gettimeofday() 调用。"""
        time_syms = [b"time@", b"gettimeofday", b"clock_gettime", b"time("]
        found = []
        for pat in time_syms:
            for m in re.finditer(re.escape(pat), self.data, re.IGNORECASE):
                va = self.off_to_va(m.start())
                if va:
                    found.append((va, pat.decode(errors="ignore")))
        calls = []
        insns = self.disasm(self.code_off, min(self.code_size, 0x4000))
        for addr, mnem, op_str, raw in insns:
            if mnem == "call" and op_str.startswith("0x"):
                tgt = int(op_str, 16)
                for (va, name) in found:
                    if abs(tgt - va) < 0x100:
                        calls.append({"call_addr": hex(addr), "call": f"call {op_str}",
                                      "sym": name})
        return calls

    # ── 5. 在线型 ──
    def find_network_calls(self) -> list:
        """找 socket/connect/send/recv/curl 调用。"""
        net_syms = [b"socket@", b"connect@", b"send@", b"recv@", b"curl_easy",
                    b"getaddrinfo", b"http"]
        found = []
        for pat in net_syms:
            for m in re.finditer(re.escape(pat), self.data, re.IGNORECASE):
                va = self.off_to_va(m.start())
                if va:
                    found.append((va, pat.decode(errors="ignore")))
        calls = []
        insns = self.disasm(self.code_off, min(self.code_size, 0x4000))
        for addr, mnem, op_str, raw in insns:
            if mnem == "call" and op_str.startswith("0x"):
                tgt = int(op_str, 16)
                for (va, name) in found:
                    if abs(tgt - va) < 0x100:
                        calls.append({"call_addr": hex(addr), "call": f"call {op_str}",
                                      "sym": name})
        return calls

    def locate_all(self) -> dict:
        return {
            "string_refs": self.find_string_refs(),
            "cmp_jcc": self.find_cmp_jcc(),
            "crypto_calls": self.find_crypto_calls(),
            "time_calls": self.find_time_calls(),
            "network_calls": self.find_network_calls(),
        }


def main():
    if len(sys.argv) < 2:
        print("用法: auth_locator.py <ELF>")
        sys.exit(1)
    loc = AuthLocator(sys.argv[1])
    r = loc.locate_all()
    print(f"=== 授权定位: {sys.argv[1]} ===")
    print(f"字符串引用型: {len(r['string_refs'])} 处")
    for x in r["string_refs"][:5]:
        print(f"  {x['insn_addr']} {x['insn']} → '{x['string']}'")
    print(f"比较型(cmp+jcc): {len(r['cmp_jcc'])} 处")
    for c in r["cmp_jcc"][:5]:
        print(f"  {c['cmp_addr']} {c['cmp']} → {c['jcc_addr']} {c['jcc']}")
    print(f"签名验证型: {len(r['crypto_calls'])} 处")
    for c in r["crypto_calls"][:5]:
        print(f"  {c['call_addr']} {c['call']} ({c['crypto']})")
    print(f"时间型: {len(r['time_calls'])} 处")
    for c in r["time_calls"][:5]:
        print(f"  {c['call_addr']} {c['call']} ({c['sym']})")
    print(f"在线型: {len(r['network_calls'])} 处")
    for c in r["network_calls"][:5]:
        print(f"  {c['call_addr']} {c['call']} ({c['sym']})")


if __name__ == "__main__":
    main()
