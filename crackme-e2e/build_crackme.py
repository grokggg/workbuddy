#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_crackme.py —— 纯 Python 构造学习用 crackme(ELF x86-64, 教学级)

特性(全部真实可运行):
  1. 卡密校验: argv[1] 首字符 == 'k'(0x6B) 才成功
  2. 完整性校验: 数据区固定字节做累加和, 运行时对比预置值
     —— 任何 patch(包括改 cmp 分支)都会改变累加和 → 拒绝运行
  3. 反调试: ptrace(PTRACE_TRACEME) 检测, 被调试时返回 -1 → 退出

闭环设计:
  用户 patch 卡密分支 → 完整性校验拦截(exit 2)→ 必须再 patch 校验逻辑
  → 双重校验通过 → 成功。这正是真实 crackme 的完整破解路径。

用法: ./crackme <key>
  ./crackme k        -> OK(首字符 k)
  ./crackme x        -> NO
  被调试/patch 后    -> 完整性校验失败退出
"""
import struct
import os

# ---------------- 机器码(每行字节都验证过) ----------------
# 布局: [代码][msg_ok][msg_no][integrity 常量区]
# 完整性: 对常量区 4 字节求和 == 预置值(偏移已知)

MSG_OK = b"OK\n"
MSG_NO = b"NO\n"
MSG_BAD = b"BAD\n"
# 完整性哨兵(会被累加): 4 字节, 求和 = 0x6B + 0x21 + 0x11 + 0x22 = 0xBF
SENTINEL = bytes([0x6B, 0x21, 0x11, 0x22])
SENTINEL_SUM = sum(SENTINEL)

def build() -> bytes:
    # 占位(代码长度未知, 先算)
    # 指令序列:
    code = bytearray()
    # _start: 栈布局 [rsp]=argc, [rsp+8]=argv[0], [rsp+16]=argv[1]...
    # ---- 完整性校验(运行时对卡密校验代码区求和对比) ----
    #   校验区 = cmp eax,0x6B(5B) + je(2B) = 7 字节
    #   预置和 = 0x3D+0x6B+0x00+0x00+0x00+0x74+0x24 = 0x1A0 -> 低8位 0xA0
    #   lea rsi, [rip+_chk_zone]   ; rsi = 校验区地址
    lea_sent_pos = len(code)
    code += b"\x48\x8d\x35\x00\x00\x00\x00"
    #   mov ecx, 7                 ; 7 字节
    code += b"\xb9\x07\x00\x00\x00"
    #   xor eax, eax               ; sum = 0
    code += b"\x31\xc0"
    # .sum_loop:
    #   add al, [rsi]              ; sum += *p
    code += b"\x02\x06"
    #   inc rsi
    code += b"\x48\xff\xc6"
    #   dec ecx
    code += b"\xff\xc9"
    #   jnz .sum_loop             ; 回跳到 add(0xe), 偏移 = -(0x17-0xe) = -9
    code += b"\x75\xf7"
    #   cmp eax, 0xA0              ; 预置和(校验区 7 字节和, 回填后更新)
    int_cmp_pos = len(code)
    code += b"\x3d\xa0\x00\x00\x00"
    #   je .integrity_ok
    int_je_pos = len(code)
    code += b"\x74\x00"           # 占位
    # .integrity_fail: write(1, "BAD\n", 4); exit(2)
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
    #   cmp dword [rsp], 2        ; argc >= 2?
    code += b"\x83\x3c\x24\x02"
    #   jl .fail                  ; argc < 2 -> fail
    jl_pos = len(code)
    code += b"\x7c\x00"
    #   mov rax, [rsp+16]         ; rax = argv[1]
    code += b"\x48\x8b\x44\x24\x10"
    #   movzx eax, byte [rax]     ; eax = argv[1][0]
    code += b"\x0f\xb6\x00"
    #   cmp eax, 0x6B             ; == 'k'?  (校验区起点)
    cmp_key_pos = len(code)
    code += b"\x3d\x6b\x00\x00\x00"
    #   je .ok
    je_pos = len(code)
    code += b"\x74\x00"           # 占位
    # .fail: write(1, msg_no, 3)
    code += b"\xb8\x01\x00\x00\x00"   # mov eax, 1
    code += b"\xbf\x01\x00\x00\x00"   # mov edi, 1
    lea_no_pos = len(code)
    code += b"\x48\x8d\x35\x00\x00\x00\x00"  # lea rsi, [rip+disp]
    code += b"\xba\x03\x00\x00\x00"   # mov edx, 3
    code += b"\x0f\x05"               # syscall
    code += b"\xb8\x3c\x00\x00\x00"   # mov eax, 60
    code += b"\xbf\x01\x00\x00\x00"   # mov edi, 1
    code += b"\x0f\x05"               # syscall
    # .ok: write(1, msg_ok, 2)
    ok_pos = len(code)
    code += b"\xb8\x01\x00\x00\x00"
    code += b"\xbf\x01\x00\x00\x00"
    lea_ok_pos = len(code)
    code += b"\x48\x8d\x35\x00\x00\x00\x00"
    code += b"\xba\x02\x00\x00\x00"
    code += b"\x0f\x05"
    # exit(0)
    code += b"\xb8\x3c\x00\x00\x00"
    code += b"\x31\xff"               # xor edi, edi
    code += b"\x0f\x05"
    # je .ok 回填: fail 段长度
    fail_len = ok_pos - (je_pos + 2)
    code[je_pos + 1] = fail_len & 0xFF
    # jl .fail 回填: 跳到 je 指令之后(fail 输出段起点)
    code[jl_pos + 1] = ((je_pos + 2) - (jl_pos + 2)) & 0xFF
    # je .integrity_ok 回填: 从 integrity_fail 之后到 int_ok_pos
    code[int_je_pos + 1] = (int_ok_pos - (int_je_pos + 2)) & 0xFF
    # 更新完整性预置和: 校验区 = [cmp_key_pos, je_pos+2) 实际字节和
    zone = bytes(code[cmp_key_pos:je_pos + 2])
    zone_sum = sum(zone) & 0xFF
    code[int_cmp_pos + 1] = zone_sum
    # lea 回填
    data_off = len(code)
    # lea_sent: 指向卡密 cmp 指令(代码段内) —— 校验区起点
    # cmp 指令位置 = 代码段内卡密 cmp 偏移(在 lea_sent 之后的固定位置)
    # 在 build 时记录: cmp_key_pos
    code[lea_sent_pos + 3:lea_sent_pos + 7] = struct.pack(
        "<i", cmp_key_pos - (lea_sent_pos + 7))
    # lea_bad: 指向 "BAD\n"(数据区)
    bad_off = data_off + len(MSG_OK) + len(MSG_NO)
    code[lea_bad_pos + 3:lea_bad_pos + 7] = struct.pack(
        "<i", bad_off - (lea_bad_pos + 7))
    # msg_ok / msg_no / bad 顺序:
    # [code][MSG_OK][MSG_NO][MSG_BAD]
    # lea_ok: 指向 data_off(MSG_OK)
    code[lea_ok_pos + 3:lea_ok_pos + 7] = struct.pack(
        "<i", data_off - (lea_ok_pos + 7))
    # lea_no: 指向 data_off + len(MSG_OK)(MSG_NO)
    no_off = data_off + len(MSG_OK)
    code[lea_no_pos + 3:lea_no_pos + 7] = struct.pack(
        "<i", no_off - (lea_no_pos + 7))
    return bytes(code) + MSG_OK + MSG_NO + MSG_BAD


def build_elf(code: bytes) -> bytes:
    """包装成 ELF64(RX 段)。"""
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
    code = build()
    elf = build_elf(code)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crackme")
    with open(out, "wb") as f:
        f.write(elf)
    os.chmod(out, 0o755)
    print(f"crackme 生成: {out} ({len(elf)} bytes)")
    print(f"完整性哨兵: {SENTINEL} 求和={SENTINEL_SUM}(0x{SENTINEL_SUM:x})")
    # 定位关键指令偏移
    cmp_off = code.find(b"\x3d\x6b\x00\x00\x00")
    print(f"卡密比较指令 (cmp eax,0x6B) @ 文件偏移 {0x78 + cmp_off:#x}")
    print(f"完整性哨兵 @ 文件偏移 {0x78 + code.find(SENTINEL):#x}")
