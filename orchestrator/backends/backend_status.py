#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""backend_status.py —— M35 后端状态面板

用法: python3 backend_status.py [--json]
环境变量: GITLAB_TOKEN / GITHUB_TOKEN(可选)
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backend_manager import BackendManager


def main() -> int:
    mgr = BackendManager()
    st = mgr.status_all()
    if "--json" in sys.argv:
        print(json.dumps(st, ensure_ascii=False, indent=2))
        return 0
    print("╔══════════════════════════════════════════╗")
    print("║        M35 后端状态面板                    ║")
    print("╚══════════════════════════════════════════╝")
    for name, s in st.items():
        mark = "✅ 可用" if s.get("available") else "❌ 不可用"
        reason = s.get("reason", s.get("quota", s.get("api", "")))
        print(f"  {name:<8} {mark:<10} {reason}")
    sel = mgr.select()
    print(f"\n➤ 推荐后端: {sel['backend'] or '无可用'}")
    if sel["backend"]:
        print(f"  状态: {sel['status']}")
    q = mgr.quota_estimate()
    print(f"\n➤ 额度:")
    for name, v in q.items():
        if v.get("可用"):
            k = [x for x in v if x != "可用"][0]
            print(f"  {name}: {k}={v[k]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
