#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_dynamic_crackmes.py —— M30 构造反调试/多校验点 crackme(行为真实)

目标(4 个):
  ad1: ptrace(TRACEME) 反调试 —— 被 ptrace 附加时 ptrace 返回 -1 -> 拒绝
  ad2: ptrace + 卡密双保护
  mc1: 双校验点(两个字符比较, 需都通过)
  mc2: 完整性校验(代码区求和) + 卡密(多保护)

注: 基于 M26 验证过的机器码模板(首字符比较 + 完整性求和)。
"""
import os
import struct
import sys

OUT = os.path.dirname(os.path.abspath(__file__))

# ---- 基础模板(M26 验证): 卡密首字符比较 + 完整性校验 ----
def build_base(key_byte: int, extra_ptrace: bool = False,
               second_check: bool = False) -> bytes:
    """构造 crackme 代码(机器码)。

    key_byte: 卡密首字符
    extra_ptrace: 是否在开头加 ptrace(TRACEME) 检测
    second_check: 是否加第二个校验(首字符=='x' 拒绝, 双校验点)
    """
    code = bytearray()
    second_start = None  # 第二校验点位置(默认无)
    # ---- 反调试: ptrace(0,0,0,0) ----
    if extra_ptrace:
        # eax=101(ptrace), edi=0(TRACEME), esi=0, edx=0
        code += b"\xb8\x65\x00\x00\x00"   # mov eax, 101
        code += b"\x31\xff"                # xor edi, edi
        code += b"\x31\xf6"                # xor esi, esi
        code += b"\x31\xd2"                # xor edx, edx
        code += b"\x0f\x05"                # syscall
        # test rax, rax; js .anti_debug_exit (ptrace 返回 -1 = 被调试)
        code += b"\x48\x85\xc0"            # test rax, rax
        ad_exit_pos = len(code)
        code += b"\x78\x00"                # js (占位)
        # .anti_debug_exit: exit(9)
        ad_exit = len(code)
        code += b"\xb8\x3c\x00\x00\x00"    # mov eax, 60
        code += b"\xbf\x09\x00\x00\x00"    # mov edi, 9
        code += b"\x0f\x05"                # syscall
        # 回填 js: 跳到 ad_exit
        code[ad_exit_pos + 1] = (ad_exit - (ad_exit_pos + 2)) & 0xFF

    # ---- 完整性校验(代码区求和: 卡密 cmp+je 区域) ----
    # lea rsi, [rip+chk]; mov ecx, 7; xor eax; 循环求和; cmp; je ok
    lea_chk_pos = len(code)
    code += b"\x48\x8d\x35\x00\x00\x00\x00"
    code += b"\xb9\x07\x00\x00\x00"
    code += b"\x31\xc0"
    code += b"\x02\x06"                    # add al, [rsi]
    code += b"\x48\xff\xc6"                # inc rsi
    code += b"\xff\xc9"                    # dec ecx
    code += b"\x75\xf7"                    # jnz 回跳
    int_cmp_pos = len(code)
    code += b"\x3d\x00\x00\x00\x00"        # cmp eax, SUM(回填)
    int_je_pos = len(code)
    code += b"\x74\x00"                    # je integrity_ok
    # .integrity_fail: write("BAD\n"); exit(2)
    code += b"\xb8\x01\x00\x00\x00"
    code += b"\xbf\x01\x00\x00\x00"
    lea_bad_pos = len(code)
    code += b"\x48\x8d\x35\x00\x00\x00\x00"
    code += b"\xba\x04\x00\x00\x00"
    code += b"\x0f\x05"
    code += b"\xb8\x3c\x00\x00\x00"
    code += b"\xbf\x02\x00\x00\x00"
    code += b"\x0f\x05"
    # .integrity_ok:
    int_ok_pos = len(code)

    # ---- argc 检查 ----
    code += b"\x83\x3c\x24\x02"            # cmp dword [rsp], 2
    jl_pos = len(code)
    code += b"\x7c\x00"                    # jl fail
    # ---- 卡密 1: argv[1][0] == key_byte ----
    code += b"\x48\x8b\x44\x24\x10"        # mov rax, [rsp+16]
    code += b"\x0f\xb6\x00"                # movzx eax, byte[rax]
    cmp_key1_pos = len(code)
    code += b"\x3d" + bytes([key_byte]) + b"\x00\x00\x00"
    je1_pos = len(code)
    code += b"\x74\x00"                    # je ok1(相等跳成功)
    jmp_fail_pos = len(code)
    code += b"\xeb\x00"                    # jmp fail(不等落这里, 跳失败)

    # ---- 第二个校验点(可选): 首字符 != 0x58('X'), 是 X 就拒绝 ----
    # 布局: [卡密 cmp][je1 -> second_check/ok1][jmp fail][second_check...][ok1]
    if second_check:
        second_start = len(code)
        # 重新读 argv[1][0]
        code += b"\x48\x8b\x44\x24\x10"
        code += b"\x0f\xb6\x00"
        code += b"\x3d\x58\x00\x00\x00"    # cmp eax, 0x58
        je2_pos = len(code)
        code += b"\x74\x00"                # je fail(是 X 就拒绝)
    # .ok1: write("OK\n"); exit(0)
    ok1_start = len(code)
    code += b"\xb8\x01\x00\x00\x00"
    code += b"\xbf\x01\x00\x00\x00"
    lea_ok_pos = len(code)
    code += b"\x48\x8d\x35\x00\x00\x00\x00"
    code += b"\xba\x03\x00\x00\x00"
    code += b"\x0f\x05"
    code += b"\xb8\x3c\x00\x00\x00"
    code += b"\x31\xff"
    code += b"\x0f\x05"
    # .fail: write("NO\n"); exit(1)
    fail_start = len(code)
    code += b"\xb8\x01\x00\x00\x00"
    code += b"\xbf\x01\x00\x00\x00"
    lea_no_pos = len(code)
    code += b"\x48\x8d\x35\x00\x00\x00\x00"
    code += b"\xba\x03\x00\x00\x00"
    code += b"\x0f\x05"
    code += b"\xb8\x3c\x00\x00\x00"
    code += b"\xbf\x01\x00\x00\x00"
    code += b"\x0f\x05"

    # ---- 回填 ----
    # jl -> fail
    code[jl_pos + 1] = (fail_start - (jl_pos + 2)) & 0xFF
    # jmp_fail -> fail_start
    code[jmp_fail_pos + 1] = (fail_start - (jmp_fail_pos + 2)) & 0xFF
    # je1 -> second_check(有) 或 ok1_start(无)
    je1_target = second_start if second_check else ok1_start
    code[je1_pos + 1] = (je1_target - (je1_pos + 2)) & 0xFF
    if second_check:
        # je2 -> fail(是 X 拒绝)
        code[je2_pos + 1] = (fail_start - (je2_pos + 2)) & 0xFF
    # int_je -> int_ok
    code[int_je_pos + 1] = (int_ok_pos - (int_je_pos + 2)) & 0xFF
    # 完整性校验区 = [cmp_key1_pos, je1_pos+2) 字节和(仅 cmp+je1, 7 字节)
    zone = bytes(code[cmp_key1_pos:je1_pos + 2])
    code[int_cmp_pos + 1] = sum(zone) & 0xFF
    # lea 回填
    data_off = len(code)
    # chk -> cmp_key1_pos(校验区起点)
    code[lea_chk_pos + 3:lea_chk_pos + 7] = struct.pack(
        "<i", cmp_key1_pos - (lea_chk_pos + 7))
    # bad -> data_off + 6 ("BAD\n" 在 OK/NO 之后)
    bad_off = data_off + 6
    code[lea_bad_pos + 3:lea_bad_pos + 7] = struct.pack(
        "<i", bad_off - (lea_bad_pos + 7))
    # ok -> data_off ("OK\n")
    code[lea_ok_pos + 3:lea_ok_pos + 7] = struct.pack(
        "<i", data_off - (lea_ok_pos + 7))
    # no -> data_off + 3 ("NO\n")
    no_off = data_off + 3
    code[lea_no_pos + 3:lea_no_pos + 7] = struct.pack(
        "<i", no_off - (lea_no_pos + 7))
    return bytes(code) + b"OK\n" + b"NO\n" + b"BAD\n"


def build_elf(code: bytes) -> bytes:
    ph_off = 0x40
    code_off = ph_off + 56
    entry = 0x400000 + code_off
    ident = b'\x7fELF' + bytes([2, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    eh = struct.pack('<16sHHIQQQIHHHHHH',
        ident, 2, 0x3E, 1, entry, ph_off, 0, 0, 64, 56, 1, 0, 0, 0)
    ph = struct.pack('<IIQQQQQQ',
        1, 5, 0, 0x400000, 0, code_off + len(code), code_off + len(code), 0x1000)
    return eh + ph + b'\x00' * (code_off - (ph_off + 56)) + code


if __name__ == "__main__":
    targets = {
        # 反调试(ptrace) + 卡密
        "ad1": build_base(0x70, extra_ptrace=True),
        # 反调试 + 卡密 + 第二校验点
        "ad2": build_base(0x6F, extra_ptrace=True, second_check=True),
        # 多校验点(双校验)
        "mc1": build_base(0x6B, second_check=True),
        # 完整性 + 卡密
        "mc2": build_base(0x41),
    }
    for name, code in targets.items():
        elf = build_elf(code)
        out = os.path.join(OUT, name)
        with open(out, "wb") as f:
            f.write(elf)
        os.chmod(out, 0o755)
        print(f"{name}: {len(elf)} bytes")
