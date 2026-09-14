#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch_docuseal_pro.py —— DocuSeal Pro 门控 patch(源码层, 可执行)

原理: 免费版 = Ability 授权列表默认 deny; Pro 功能(:email_reminders/:countless)
不在列表 → 门控触发。patch = 在 Ability 类加授权行(deny → allow)。

数学等价(对照 auth_patcher 比较型):
  原始: [permitted] ? allow : deny   →  can?(:manage, :countless) == false
  patch: can :manage, :countless     →  can? == true(恒真)

用法: python3 patch_docuseal_pro.py <docuseal_src_root>
输出: ability.rb 加 2 行 + 写 patched 副本
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Pro 资源(由 locate_docuseal_pro.py 定位)
PRO_RESOURCES = [":email_reminders", ":countless"]
# 插入位置: Ability 类 can :manage, :mcp 之后
ANCHOR = "    can :manage, :mcp"


def patch_ability(root: str, dry: bool = False) -> dict:
    p = Path(root) / "lib" / "ability.rb"
    if not p.exists():
        return {"error": f"{p} 不存在"}
    src = p.read_text()
    missing = [r for r in PRO_RESOURCES if f"can :manage, {r}" not in src]
    if not missing:
        return {"patched": False, "reason": "已全部授权(无需 patch)"}
    lines = [f"    can :manage, {r}" for r in missing]
    if ANCHOR not in src:
        return {"error": f"锚点 {ANCHOR} 未找到"}
    patched_src = src.replace(ANCHOR, ANCHOR + "\n" + "\n".join(lines), 1)
    if dry:
        return {"patched": True, "dry": True, "additions": lines}
    out = root + "-patched"
    os.makedirs(out, exist_ok=True)
    for f in p.parent.rglob("*"):
        pass
    # 只输出 ability.rb 的 patched 副本 + 完整目录复制
    import shutil
    shutil.copytree(root, out, dirs_exist_ok=True)
    op = Path(out) / "lib" / "ability.rb"
    op.write_text(patched_src)
    return {"patched": True, "output": out, "additions": lines}


def verify(root: str) -> dict:
    """验证: patched 副本里门控资源已授权。"""
    p = Path(root) / "lib" / "ability.rb"
    src = p.read_text()
    results = {}
    for r in PRO_RESOURCES:
        results[r] = f"can :manage, {r}" in src
    return results


def main():
    if len(sys.argv) < 2:
        print("用法: patch_docuseal_pro.py <docuseal_src_root> [--dry]")
        sys.exit(1)
    dry = "--dry" in sys.argv
    root = sys.argv[1]
    r = patch_ability(root, dry=dry)
    print("=== DocuSeal Pro 门控 patch ===")
    print(r)
    if r.get("patched") and not dry:
        v = verify(r["output"])
        print("=== 验证(patched 副本) ===")
        for res, ok in v.items():
            print(f"  {res}: {'已授权 ✅' if ok else '未授权 ❌'}")


if __name__ == "__main__":
    main()
