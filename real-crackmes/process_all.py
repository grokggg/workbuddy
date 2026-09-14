#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
process_all.py —— M27 批量处理 5 个真实 crackme

对每个 crackme:
  1. recon_v2 分析
  2. analysis_v2 定位校验
  3. llm_engine 生成策略
  4. patch(卡密 je -> jmp + 完整性 je -> jmp)
  5. 验证(原始失败, 破解成功)

输出: 每个 crackme 的报告 + 补丁脚本 + 破解二进制 + 验证日志
"""
import json
import os
import shutil
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
UP_TOOLS = os.path.dirname(HERE)
sys.path.insert(0, UP_TOOLS)
sys.path.insert(0, os.path.join(UP_TOOLS, "lib"))

CRACKMES = [
    ("cm01", "p", "crackme01 strncmp 密码"),
    ("cm02", "o", "crackme02 字符变换"),
    ("cm04", "k", "crackme04 校验和"),
    ("cm05", "A", "crackme05 取模校验"),
    ("cm09", "Z", "crackme09 CPUID 反VM"),
]


def run(cmd, timeout=30):
    r = subprocess.run(cmd, capture_output=True, timeout=timeout)
    return r.stdout.decode(errors="ignore"), r.returncode


def find_checks(crackme_path):
    """定位卡密 cmp + 完整性 cmp。"""
    d = open(crackme_path, "rb").read()
    import re
    checks = []
    for m in re.finditer(rb"\x3d(.)\x00\x00\x00\x74", d):
        checks.append({"off": m.start(), "imm": m.group(1)[0]})
    return checks


def patch_crackme(crackme_path, out_path):
    """双 patch: 卡密 je -> jmp + 完整性 je -> jmp。"""
    d = bytearray(open(crackme_path, "rb").read())
    checks = find_checks(crackme_path)
    patched = 0
    for c in checks:
        # je 在 cmp 后 5 字节处
        je_off = c["off"] + 5
        if d[je_off] == 0x74:
            d[je_off] = 0xEB
            patched += 1
    with open(out_path, "wb") as f:
        f.write(d)
    os.chmod(out_path, 0o755)
    return patched


def main():
    results = []
    for name, pwd, desc in CRACKMES:
        src = os.path.join(HERE, name)
        print(f"\n{'='*50}\n[{name}] {desc}\n{'='*50}")

        # 1. recon
        out, rc = run([sys.executable,
                       os.path.join(UP_TOOLS, "lib", "recon_v2.py"), src])
        print("--- recon_v2 ---")
        print(out.strip()[:300])

        # 2. analysis
        out2, rc2 = run([sys.executable,
                         os.path.join(UP_TOOLS, "lib", "analysis_v2.py"), src])
        print("--- analysis_v2 ---")
        print(out2.strip()[:300])

        # 3. llm_engine
        out3, rc3 = run([sys.executable,
                         os.path.join(UP_TOOLS, "lib", "llm_engine.py"), src])
        print("--- llm_engine ---")
        print(out3.strip()[:300])

        # 4. 原始验证(错误密码应失败)
        _, rc_orig = run([src, "x"])
        print(f"--- 原始行为 --- 错误密码'x': rc={rc_orig}")

        # 5. patch
        cracked = os.path.join(HERE, name + "-cracked")
        n = patch_crackme(src, cracked)
        print(f"--- patch --- 修改 {n} 个 je -> jmp")

        # 6. 验证破解(错误密码应成功)
        out_c, rc_c = run([cracked, "x"])
        print(f"--- 破解验证 --- 错误密码'x': [{out_c.strip()}] rc={rc_c}")

        # 7. 正确密码对比
        out_ok, rc_ok = run([cracked, pwd])
        print(f"--- 正确密码'{pwd}' --- [{out_ok.strip()}] rc={rc_ok}")

        results.append({
            "name": name, "desc": desc, "orig_rc": rc_orig,
            "cracked_rc": rc_c, "cracked_out": out_c.strip(),
            "ok_rc": rc_ok, "patches": n,
        })

    # 汇总
    print(f"\n{'='*50}\n汇总\n{'='*50}")
    success = 0
    for r in results:
        ok = r["orig_rc"] != 0 and r["cracked_rc"] == 0
        status = "✅" if ok else "❌"
        if ok:
            success += 1
        print(f"  {status} {r['name']}: 原始rc={r['orig_rc']} "
              f"破解rc={r['cracked_rc']} ({r['cracked_out']}) patch={r['patches']}")
    print(f"\n破解率: {success}/{len(results)}")
    return 0 if success == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
