#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
locate_docuseal_pro.py —— DocuSeal Pro 门控定位(M42 适配)

定位结果(真实, 源码级):
  - 门控机制: CanCanCan Ability 授权列表(默认 deny)
  - 门控资源: :email_reminders / :countless(Pro), :mcp(免费)
  - 定位文件: lib/ability.rb(授权定义) + 门控调用点(controllers)
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path


class DocuSealLocator:
    def __init__(self, root: str):
        self.root = Path(root)

    def locate_ability(self) -> dict:
        """定位 Ability 授权定义 + 门控资源清单。"""
        ability_path = self.root / "lib" / "ability.rb"
        if not ability_path.exists():
            return {"error": "ability.rb 不存在"}
        src = ability_path.read_text()
        # 已授权资源(can :manage, :sym 或 can :manage, Symbol)
        granted = re.findall(r"can\s+:[a-z_]+(?:,|,?)\s*:?([a-z_]+)", src)
        # 过滤误抓(只保留 :symbol 形式)
        granted_syms = re.findall(r"can\s+:manage,\s*:([a-z_]+)", src)
        # 门控调用点
        gates = []
        for f in (self.root / "app" / "controllers").rglob("*.rb"):
            text = f.read_text(errors="ignore")
            for m in re.finditer(r"can\?\(:manage,\s*:([a-z_]+)", text):
                rel = f.relative_to(self.root)
                gates.append({"file": str(rel), "resource": m.group(1)})
        return {"ability_file": str(ability_path.relative_to(self.root)),
                "granted_symbols": sorted(set(granted_syms)),
                "gate_points": gates}

    def diff_pro_vs_free(self) -> list:
        """免费版 denied(门控) vs 已授权。"""
        r = self.locate_ability()
        if "error" in r:
            return []
        gated = sorted(set(g["resource"] for g in r["gate_points"]))
        granted = set(r["granted_symbols"])
        return [g for g in gated if g not in granted]


def main():
    if len(sys.argv) < 2:
        print("用法: locate_docuseal_pro.py <docuseal_src_root>")
        sys.exit(1)
    loc = DocuSealLocator(sys.argv[1])
    r = loc.locate_ability()
    print("=== DocuSeal Pro 门控定位 ===")
    print(f"授权定义: {r.get('ability_file', '?')}")
    print(f"已授权符号: {r.get('granted_symbols', [])}")
    print(f"门控点: {len(r.get('gate_points', []))} 处")
    for g in r.get("gate_points", [])[:10]:
        print(f"  {g['file']} → can?(:manage, :{g['resource']})")
    pro = loc.diff_pro_vs_free()
    print(f"\n=== Pro 门控资源(免费版 denied) ===")
    for p in pro:
        print(f"  :{p}")
    if not pro:
        print("  (无——所有门控资源都已授权)")


if __name__ == "__main__":
    main()
