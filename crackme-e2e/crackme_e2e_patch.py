#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
crackme_e2e_patch.py —— M26 端到端破解补丁脚本

破解路径:
  1. patch 卡密 je(0xcd): 74 24 -> EB 24(无条件跳 OK)
  2. patch 完整性 je(0x94): 74 24 -> EB 24(跳过完整性校验)

用法: python3 crackme_e2e_patch.py crackme [输出名]
"""
import os
import sys

KEY_JE_OFF = 0xCD   # 卡密比较 je(74 24)
INT_JE_OFF = 0x94   # 完整性校验 je(74 24)


def patch(path: str, out: str = "") -> str:
    data = bytearray(open(path, "rb").read())
    orig_key = data[KEY_JE_OFF]
    orig_int = data[INT_JE_OFF]
    assert orig_key == 0x74, f"卡密 je 偏移错误: {KEY_JE_OFF:#x} = {orig_key:02x}"
    assert orig_int == 0x74, f"完整性 je 偏移错误: {INT_JE_OFF:#x} = {orig_int:02x}"
    data[KEY_JE_OFF] = 0xEB
    data[INT_JE_OFF] = 0xEB
    out = out or (path + ".cracked")
    with open(out, "wb") as f:
        f.write(data)
    os.chmod(out, 0o755)
    print(f"[+] 补丁完成: {out}")
    print(f"    卡密 je @ {KEY_JE_OFF:#x}: {orig_key:02x} -> EB")
    print(f"    完整性 je @ {INT_JE_OFF:#x}: {orig_int:02x} -> EB")
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 crackme_e2e_patch.py <crackme> [输出名]")
        sys.exit(1)
    out = patch(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "")
    print(f"[+] 验证: 运行 '{out} x' 应输出 OK")
