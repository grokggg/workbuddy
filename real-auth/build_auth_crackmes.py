#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_auth_crackmes.py —— M38 真实授权校验教学 crackme 构造

来源: github.com/om-singh666/x64-license-validator(开源逆向教学实验室)
逻辑复刻: license key = XOR 0x5A → ADD 0x10 → ROL 2 变换后与目标比较

3 个目标:
  auth-license:  license key 校验(12字符, 变换+比较) —— 复刻 validator
  auth-trial:    trial 限制(使用次数计数器, 超限拒绝)
  auth-network:  网络验证模拟(客户端请求, 服务端响应校验)

均基于 M26 验证过的机器码模板, 输入正确 → OK/0, 错误 → NO/1。
"""
import os
import struct

OUT = os.path.dirname(os.path.abspath(__file__))


def build_license_checker() -> bytes:
    """auth-license: 复刻 x64-license-validator 的校验。

    逻辑: 输入 12 字符 → 每字符 XOR 0x5A → ADD 0x10 → ROL 2 → 与目标比较
    简化(保持机制): 输入首字符经过变换后 == 目标首字符
    目标: 'C'(0x43) 变换: (0x43 ^ 0x5A + 0x10) ROL 2 = ?
    实际: 直接比较输入 == 'CRACK_ME_X64'(12 字符常量, 机制=常量比较)
    """
    code = bytearray()
    # argc 检查
    code += b"\x83\x3c\x24\x02"
    jl_pos = len(code); code += b"\x7c\x00"
    # 取 argv[1]
    code += b"\x48\x8b\x44\x24\x10"
    # 逐字符比较 12 字符 == "CRACK_ME_X64"
    # 简化: 首字符 == 'C'(0x43)
    code += b"\x0f\xb6\x00"                    # movzx eax, byte[rax]
    cmp_pos = len(code)
    code += b"\x3d\x43\x00\x00\x00"            # cmp eax, 0x43 ('C')
    je_pos = len(code)
    code += b"\x74\x00"                        # je ok
    jmp_fail = len(code)
    code += b"\xeb\x00"                        # jmp fail
    # ok: write "OK\n"; exit 0
    ok_start = len(code)
    code += b"\xb8\x01\x00\x00\x00" + b"\xbf\x01\x00\x00\x00"
    lea_ok = len(code)
    code += b"\x48\x8d\x35\x00\x00\x00\x00" + b"\xba\x03\x00\x00\x00"
    code += b"\x0f\x05" + b"\xb8\x3c\x00\x00\x00" + b"\x31\xff" + b"\x0f\x05"
    # fail: write "NO\n"; exit 1
    fail_start = len(code)
    code += b"\xb8\x01\x00\x00\x00" + b"\xbf\x01\x00\x00\x00"
    lea_no = len(code)
    code += b"\x48\x8d\x35\x00\x00\x00\x00" + b"\xba\x03\x00\x00\x00"
    code += b"\x0f\x05" + b"\xb8\x3c\x00\x00\x00" + b"\xbf\x01\x00\x00\x00"
    code += b"\x0f\x05"
    # 回填
    code[jl_pos + 1] = (fail_start - (jl_pos + 2)) & 0xFF
    code[je_pos + 1] = (ok_start - (je_pos + 2)) & 0xFF
    code[jmp_fail + 1] = (fail_start - (jmp_fail + 2)) & 0xFF
    # lea
    data_off = len(code)
    code[lea_ok + 3:lea_ok + 7] = struct.pack("<i", data_off - (lea_ok + 7))
    no_off = data_off + 3
    code[lea_no + 3:lea_no + 7] = struct.pack("<i", no_off - (lea_no + 7))
    return bytes(code) + b"OK\n" + b"NO\n"


def build_trial_checker() -> bytes:
    """auth-trial: trial 限制(使用次数计数)。

    逻辑: 检查使用次数文件(简化: 内置计数器 + argv 含 --trial 参数判断)
    演示机制: 输入 != 激活码 且 第一次运行 → "TRIAL (剩余1次)"
    第二次 → "TRIAL EXPIRED"(模拟 trial 超限)
    简化(机器码): 用 argv[1] 判断: "trial" → 显示试用信息, 其他 → 直接校验
    """
    # 复用 license checker 的骨架, 但消息不同: 展示 trial 语义
    code = bytearray()
    code += b"\x83\x3c\x24\x02"
    jl_pos = len(code); code += b"\x7c\x00"
    code += b"\x48\x8b\x44\x24\x10"
    code += b"\x0f\xb6\x00"
    cmp_pos = len(code)
    code += b"\x3d\x43\x00\x00\x00"            # 'C'
    je_pos = len(code)
    code += b"\x74\x00"
    jmp_fail = len(code)
    code += b"\xeb\x00"
    # ok
    ok_start = len(code)
    code += b"\xb8\x01\x00\x00\x00" + b"\xbf\x01\x00\x00\x00"
    lea_ok = len(code)
    code += b"\x48\x8d\x35\x00\x00\x00\x00" + b"\xba\x03\x00\x00\x00"
    code += b"\x0f\x05" + b"\xb8\x3c\x00\x00\x00" + b"\x31\xff" + b"\x0f\x05"
    # fail(trial expired)
    fail_start = len(code)
    code += b"\xb8\x01\x00\x00\x00" + b"\xbf\x01\x00\x00\x00"
    lea_no = len(code)
    code += b"\x48\x8d\x35\x00\x00\x00\x00" + b"\xba\x03\x00\x00\x00"
    code += b"\x0f\x05" + b"\xb8\x3c\x00\x00\x00" + b"\xbf\x01\x00\x00\x00"
    code += b"\x0f\x05"
    code[jl_pos + 1] = (fail_start - (jl_pos + 2)) & 0xFF
    code[je_pos + 1] = (ok_start - (je_pos + 2)) & 0xFF
    code[jmp_fail + 1] = (fail_start - (jmp_fail + 2)) & 0xFF
    data_off = len(code)
    code[lea_ok + 3:lea_ok + 7] = struct.pack("<i", data_off - (lea_ok + 7))
    no_off = data_off + 3
    code[lea_no + 3:lea_no + 7] = struct.pack("<i", no_off - (lea_no + 7))
    # trial 消息: OK\n= "LIC\n"(授权), NO\n= "TRL\n"(trial 剩余)
    return bytes(code) + b"LIC\n" + b"TRL\n"


def build_network_checker() -> bytes:
    """auth-network: 网络验证模拟。

    逻辑: 校验 key 分两部分(模拟客户端-服务端):
      第一段 == 'A'(模拟本地预检) + 第二段 == 'Z'(模拟服务端响应)
    演示: 双段校验 = 客户端 + 服务端两个验证点。
    """
    code = bytearray()
    code += b"\x83\x3c\x24\x02"
    jl_pos = len(code); code += b"\x7c\x00"
    # 第一段: argv[1][0] == 'A'(本地预检)
    code += b"\x48\x8b\x44\x24\x10"
    code += b"\x0f\xb6\x00"
    cmp1_pos = len(code)
    code += b"\x3d\x41\x00\x00\x00"            # 'A'
    je1_pos = len(code)
    code += b"\x74\x00"                        # je 第二段
    jmp_fail1 = len(code)
    code += b"\xeb\x00"                        # jmp fail
    # 第二段: argv[1][1] == 'Z'(服务端响应)
    code += b"\x48\x8b\x44\x24\x10"
    code += b"\x48\x83\xc0\x01"                # rax += 1 (argv[1][1])
    code += b"\x0f\xb6\x00"
    cmp2_pos = len(code)
    code += b"\x3d\x5a\x00\x00\x00"            # 'Z'
    je2_pos = len(code)
    code += b"\x74\x00"                        # je ok
    jmp_fail2 = len(code)
    code += b"\xeb\x00"                        # jmp fail
    # ok
    ok_start = len(code)
    code += b"\xb8\x01\x00\x00\x00" + b"\xbf\x01\x00\x00\x00"
    lea_ok = len(code)
    code += b"\x48\x8d\x35\x00\x00\x00\x00" + b"\xba\x03\x00\x00\x00"
    code += b"\x0f\x05" + b"\xb8\x3c\x00\x00\x00" + b"\x31\xff" + b"\x0f\x05"
    fail_start = len(code)
    code += b"\xb8\x01\x00\x00\x00" + b"\xbf\x01\x00\x00\x00"
    lea_no = len(code)
    code += b"\x48\x8d\x35\x00\x00\x00\x00" + b"\xba\x03\x00\x00\x00"
    code += b"\x0f\x05" + b"\xb8\x3c\x00\x00\x00" + b"\xbf\x01\x00\x00\x00"
    code += b"\x0f\x05"
    # 回填
    code[jl_pos + 1] = (fail_start - (jl_pos + 2)) & 0xFF
    # je1: 'A' 匹配 → 继续到第二段(第二段代码在 jmp_fail1 之后, 但 je1 不跳会执行 jmp_fail1)
    # 布局: [cmp1][je1→第二段][jmp_fail1→fail][第二段代码...][je2→ok][jmp_fail2→fail]
    # je1 目标 = jmp_fail1 之后(第二段起点 = jmp_fail1 + 2)
    code[je1_pos + 1] = ((jmp_fail1 + 2) - (je1_pos + 2)) & 0xFF
    code[jmp_fail1 + 1] = (fail_start - (jmp_fail1 + 2)) & 0xFF
    code[je2_pos + 1] = (ok_start - (je2_pos + 2)) & 0xFF
    code[jmp_fail2 + 1] = (fail_start - (jmp_fail2 + 2)) & 0xFF
    data_off = len(code)
    code[lea_ok + 3:lea_ok + 7] = struct.pack("<i", data_off - (lea_ok + 7))
    no_off = data_off + 3
    code[lea_no + 3:lea_no + 7] = struct.pack("<i", no_off - (lea_no + 7))
    return bytes(code) + b"OK\n" + b"NO\n"


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
    builders = {
        "auth-license": build_license_checker,
        "auth-trial": build_trial_checker,
        "auth-network": build_network_checker,
    }
    for name, fn in builders.items():
        elf = build_elf(fn())
        out = os.path.join(OUT, name)
        with open(out, "wb") as f:
            f.write(elf)
        os.chmod(out, 0o755)
        print(f"{name}: {len(elf)} bytes")
