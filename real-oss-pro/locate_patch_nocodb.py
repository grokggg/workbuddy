#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
locate_patch_nocodb.py —— NocoDB EE 门控定位 + patch(源码层, 可执行)

门控机制(真实):
  - CE stub: src/helpers/lookupSortLimitGate.ts
      isLookupSortLimitLicensed() → false(恒)
      assertLookupSortLimitLicensed() → 恒拒绝
  - EE 版 shadow 同路径文件(src/ee/...) 做真实 license 检查
  - 所有消费方(display/filter/formula/sort/group-by)走单一 gate

patch 原理(对照 auth_patcher 比较型):
  原始: [isEE] ? allow : deny  →  isLookupSortLimitLicensed()==false
  patch: return false → return true(恒真)

用法: python3 locate_patch_nocodb.py <nocodb_root>
"""
from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path

GATE_REL = "packages/nocodb/src/helpers/lookupSortLimitGate.ts"


def locate(root: str) -> dict:
    r = Path(root)
    gate = r / GATE_REL
    if not gate.exists():
        return {"error": f"{gate} 不存在"}
    src = gate.read_text()
    # 定位 return false / assert 拒绝
    ret_false = bool(re.search(r"return\s+false", src))
    rejects = bool(re.search(r"featureNotSupported", src))
    # 找消费方
    consumers = []
    for f in (r / "packages/nocodb/src/services").rglob("*.ts"):
        t = f.read_text(errors="ignore")
        if "assertLookupSortLimitLicensed" in t or "isLookupSortLimitLicensed" in t:
            consumers.append(f.relative_to(r).as_posix())
    # 找 EE shadow
    ee_shadow = r / "packages/nocodb/src/ee/helpers/lookupSortLimitGate.ts"
    return {
        "gate_file": GATE_REL,
        "is_ce_stub": ret_false and rejects,
        "consumers": consumers,
        "ee_shadow_exists": ee_shadow.exists(),
        "gate_src": src,
    }


def patch(root: str, dry: bool = False) -> dict:
    r = Path(root)
    gate = r / GATE_REL
    src = gate.read_text()
    # patch: return false → return true
    new_src = re.sub(r"return\s+false", "return true", src, count=1)
    if new_src == src:
        return {"patched": False, "reason": "无 return false 可改(可能已 patch)"}
    if dry:
        return {"patched": True, "dry": True}
    out = root + "-patched"
    shutil.copytree(r, out, dirs_exist_ok=True)
    (Path(out) / GATE_REL).write_text(new_src)
    return {"patched": True, "output": out}


def verify(root: str) -> dict:
    gate = Path(root) / GATE_REL
    src = gate.read_text()
    return {"isLookupSortLimitLicensed_returns_true": bool(re.search(r"return\s+true", src))}


def main():
    if len(sys.argv) < 2:
        print("用法: locate_patch_nocodb.py <nocodb_root> [--dry]")
        sys.exit(1)
    dry = "--dry" in sys.argv
    root = sys.argv[1]
    print("=== NocoDB EE 门控定位 ===")
    r = locate(root)
    if "error" in r:
        print(r); sys.exit(1)
    print(f"门控文件: {r['gate_file']}")
    print(f"CE stub: {r['is_ce_stub']}(return false + 恒拒绝)")
    print(f"EE shadow: {'存在' if r['ee_shadow_exists'] else '不存在'}")
    print(f"消费方: {len(r['consumers'])} 处")
    for c in r["consumers"][:8]:
        print(f"  {c}")
    print("\n=== patch ===")
    p = patch(root, dry=dry)
    print(p)
    if p.get("patched") and not dry:
        v = verify(p["output"])
        print(f"验证: isLookupSortLimitLicensed → {v['isLookupSortLimitLicensed_returns_true']}")


if __name__ == "__main__":
    main()
