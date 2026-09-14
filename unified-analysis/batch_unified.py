#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""batch_unified.py —— M31 批量用统一入口处理 M28-M30 所有目标。"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
UP = os.path.dirname(HERE)


def run(cmd, timeout=30):
    r = subprocess.run(cmd, capture_output=True, timeout=timeout)
    return r.stdout.decode(errors="ignore"), r.returncode

# 历史目标清单
TARGETS = [
    # M28: 真实编译
    ("real-binaries/crackme-angr", "ELF"),
    # M29: 带壳
    ("protected-crackmes/cm-base", "ELF"),
    # M30: 反调试/多校验
    ("dynamic-crackmes/ad1", "ELF"),
    ("dynamic-crackmes/ad2", "ELF"),
    ("dynamic-crackmes/mc1", "ELF"),
    ("dynamic-crackmes/mc2", "ELF"),
]


def main():
    results = []
    out_root = os.path.join(HERE, "batch-out")
    os.makedirs(out_root, exist_ok=True)
    for rel, fmt in TARGETS:
        tgt = os.path.join(UP, rel)
        if not os.path.exists(tgt):
            print(f"[SKIP] {rel} 不存在")
            continue
        name = os.path.basename(rel)
        out_dir = os.path.join(out_root, name)
        os.makedirs(out_dir, exist_ok=True)
        print(f"\n{'='*50}\n[{name}] {fmt}\n{'='*50}")
        r = subprocess.run([sys.executable, os.path.join(HERE, "analysis_all.py"),
                            tgt, "--out", out_dir, "--json"],
                           capture_output=True, timeout=120)
        try:
            rep = json.loads(r.stdout)
        except Exception as e:
            print(f"  输出解析失败: {e}")
            print(r.stdout[-300:])
            results.append({"name": name, "cracked": False, "reason": "解析失败"})
            continue
        # 验证: 用 argv 参数(这些 crackme 都是 argv 校验)
        cracked_path = rep.get("cracked_path", "")
        verify = {}
        if cracked_path and os.path.exists(cracked_path):
            for inp in ["x", "abc", "test", "p", "k", "A", "o"]:
                out, rc = run([cracked_path, inp], timeout=10)
                verify[inp] = {"out": out.strip()[-40:], "rc": rc}
        rep["verify"] = verify
        cracked = any(v.get("rc") == 0 and
                      ("OK" in v.get("out", "") or
                       "Congratulations" in v.get("out", "") or
                       "found the flag" in v.get("out", ""))
                      for v in verify.values())
        print(f"  保护: {rep.get('protections')}")
        print(f"  patches: {len(rep.get('patches', []))} 处")
        results.append({"name": name, "cracked": cracked,
                        "patches": len(rep.get("patches", [])),
                        "verify": verify})
        # 保存报告
        with open(os.path.join(out_dir, "report.json"), "w") as f:
            json.dump(rep, f, ensure_ascii=False, indent=2, default=str)

    # 汇总
    print(f"\n{'='*50}\n批量汇总\n{'='*50}")
    n = sum(1 for r in results if r["cracked"])
    for r in results:
        st = "✅" if r["cracked"] else "❌"
        print(f"  {st} {r['name']}: {r.get('reason', str(r.get('patches', 0)) + ' patches')}")
    print(f"\n破解率: {n}/{len(results)}")
    return 0 if n == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
