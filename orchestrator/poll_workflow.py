#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
poll_workflow.py —— M33 轮询 workflow 状态 + 拉取产物

用法:
  python3 poll_workflow.py <run_id> [--wait 秒数]
  python3 poll_workflow.py latest [--wait]

环境变量: GH_TOKEN, GH_REPO
"""
import json
import os
import sys
import time
import urllib.request
import urllib.parse

TOKEN = os.environ.get("GH_TOKEN", "")
REPO = os.environ.get("GH_REPO", "grokggg/workbuddy")


def api(url):
    req = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {TOKEN}",
                      "User-Agent": "hermes-orchestrator"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def get_latest_run() -> dict:
    """获取最新的 analyze workflow run。"""
    url = (f"https://api.github.com/repos/{REPO}"
           f"/actions/workflows/analyze.yml/runs?per_page=1")
    d = api(url)
    runs = d.get("workflow_runs", [])
    return runs[0] if runs else {}


def poll(run_id: str, wait: int = 30) -> dict:
    """轮询直到完成。"""
    if run_id == "latest":
        run = get_latest_run()
        run_id = str(run.get("id", ""))
    if not run_id:
        return {"error": "无 workflow run"}
    url = f"https://api.github.com/repos/{REPO}/actions/runs/{run_id}"
    while True:
        run = api(url)
        status = run.get("status")
        concl = run.get("conclusion", "")
        print(f"  [{run_id}] status={status} conclusion={concl or '...'}")
        if status == "completed":
            # 拉取产物列表
            arts_url = (f"https://api.github.com/repos/{REPO}"
                        f"/actions/runs/{run_id}/artifacts")
            arts = api(arts_url)
            artifacts = [a["name"] for a in arts.get("artifacts", [])]
            return {"run_id": run_id, "status": status,
                    "conclusion": concl, "artifacts": artifacts,
                    "html_url": run.get("html_url", "")}
        time.sleep(wait)


if __name__ == "__main__":
    if not TOKEN:
        print("需要 GH_TOKEN 环境变量")
        sys.exit(1)
    run_id = sys.argv[1] if len(sys.argv) > 1 else "latest"
    wait = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    r = poll(run_id, wait)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    sys.exit(0)
