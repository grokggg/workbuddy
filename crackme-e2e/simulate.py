#!/usr/bin/env python3
"""模拟执行 crackme 代码段, 找段错误位置。"""
import struct
import sys

d = open('/tmp/m26/up-tools/crackme-e2e/crackme', 'rb').read()
code = d[0x78:]
mem_base = 0x400000

rip = 0
regs = {'eax': 0, 'ecx': 0, 'esi': 0, 'edi': 0, 'edx': 0, 'rsi': 0}
steps = 0
while rip < len(code) and steps < 80:
    b = code[rip]
    steps += 1
    if b == 0x48 and code[rip + 1] == 0x8d:
        disp = struct.unpack('<i', code[rip + 3:rip + 7])[0]
        target = rip + 7 + disp
        regs['rsi'] = mem_base + 0x78 + target
        print(f"{rip:04x}: lea rsi, [{target:#x}] vaddr={regs['rsi']:#x}")
        rip += 7
    elif b == 0xb9:
        regs['ecx'] = struct.unpack('<I', code[rip + 1:rip + 5])[0]
        print(f"{rip:04x}: mov ecx, {regs['ecx']}")
        rip += 5
    elif b == 0x31 and code[rip + 1] == 0xc0:
        regs['eax'] = 0
        print(f"{rip:04x}: xor eax")
        rip += 2
    elif b == 0x02:
        addr = regs['rsi']
        file_off = addr - mem_base
        if file_off >= len(d):
            print(f"{rip:04x}: FAULT read @ {addr:#x} (off {file_off:#x} >= {len(d):#x})")
            break
        byte = d[file_off]
        regs['eax'] = (regs['eax'] + byte) & 0xFF
        print(f"{rip:04x}: add al,[rsi] +{byte:02x} -> al={regs['eax']:02x}")
        rip += 2
    elif b == 0x48 and code[rip + 1] == 0xff and code[rip + 2] == 0xc6:
        regs['rsi'] += 1
        rip += 3
    elif b == 0xff and code[rip + 1] == 0xc9:
        regs['ecx'] -= 1
        rip += 2
    elif b == 0x75:
        disp = code[rip + 1]
        if disp >= 128:
            disp -= 256
        if regs['ecx'] != 0:
            rip += 2 + disp
        else:
            rip += 2
    elif b == 0x3d:
        imm = struct.unpack('<I', code[rip + 1:rip + 5])[0]
        print(f"{rip:04x}: cmp eax={regs['eax']:#x}, {imm:#x}")
        rip += 5
    elif b == 0x74:
        disp = code[rip + 1]
        if disp >= 128:
            disp -= 256
        # je 目标
        tgt = rip + 2 + disp
        print(f"{rip:04x}: je -> {tgt:#x} (al={regs['eax']:#x})")
        if regs['eax'] == 0xBF:
            rip = tgt
        else:
            rip += 2
    elif b == 0xb8:
        regs['eax'] = struct.unpack('<I', code[rip + 1:rip + 5])[0]
        print(f"{rip:04x}: mov eax, {regs['eax']}")
        rip += 5
    elif b == 0xbf:
        regs['edi'] = struct.unpack('<I', code[rip + 1:rip + 5])[0]
        rip += 5
    elif b == 0xba:
        regs['edx'] = struct.unpack('<I', code[rip + 1:rip + 5])[0]
        rip += 5
    elif b == 0x83 and code[rip + 1] == 0x3c:
        imm = code[rip + 2]
        print(f"{rip:04x}: cmp dword[rsp], {imm}")
        rip += 3
    elif b == 0x7c:
        disp = code[rip + 1]
        if disp >= 128:
            disp -= 256
        tgt = rip + 2 + disp
        print(f"{rip:04x}: jl -> {tgt:#x}")
        rip = tgt
    elif b == 0x48 and code[rip + 1] == 0x8b:
        print(f"{rip:04x}: mov rax,[rsp+{code[rip+3]}]")
        rip += 4
    elif b == 0x0f and code[rip + 1] == 0xb6:
        print(f"{rip:04x}: movzx eax,byte[rax]")
        rip += 3
    elif b == 0x0f and code[rip + 1] == 0x05:
        print(f"{rip:04x}: syscall eax={regs['eax']}")
        if regs['eax'] == 60:
            print("  -> exit")
            break
        rip += 2
    else:
        print(f"{rip:04x}: UNKNOWN {b:02x} {code[rip:rip+4].hex()}")
        break
