#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
trigger_workflow.py —— M33 通过 GitHub API 触发 Actions workflow

用法:
  python3 trigger_workflow.py <目标路径> [mode]
  例: python3 trigger_workflow.py up-tools/real-binaries/crackme-angr full

环境变量: GH_TOKEN(GitHub 令牌), GH_REPO(仓库, 默认 grokggg/workbuddy)
"""
import json
import os
import sys
import urllib.request

TOKEN = os.environ.get("GH_TOKEN", "")
REPO = os.environ.get("GH_REPO", "grokggg/workbuddy")


def trigger(target: str, mode: str = "full") -> dict:
    """触发 workflow_dispatch。"""
    url = (f"https://api.github.com/repos/{REPO}"
           f"/actions/workflows/analyze.yml/dispatches")
    payload = json.dumps({
        "ref": "main",
        "inputs": {"target_path": target, "mode": mode},
    }).encode()
    req = urllib.request.Request(
        url, data=payload, method="POST",
        headers={"Authorization": f"Bearer {TOKEN}",
                 "Content-Type": "application/json",
                 "User-Agent": "hermes-orchestrator"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return {"ok": r.status == 204, "status": r.status}
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="ignore")
        return {"ok": False, "status": e.code, "error": body[:200]}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    target = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "full"
    if not TOKEN:
        print("需要 GH_TOKEN 环境变量")
        sys.exit(1)
    r = trigger(target, mode)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    sys.exit(0 if r.get("ok") else 1)
