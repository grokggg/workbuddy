#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
trigger_upload.py —— M36 上传即处理闭环

用户一条命令:
  python3 trigger_upload.py <目标文件>

流程:
  1. copy 目标到 inbox/
  2. git add + commit + push(触发极狐 pipeline)
  3. 轮询 pipeline 状态
  4. 完成后 git pull 拿结果

环境变量: GITLAB_TOKEN, GITLAB_REPO(默认 Grantgust123/up-tools)
"""
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request

TOKEN = os.environ.get("GITLAB_TOKEN", "")
REPO = os.environ.get("GITLAB_REPO", "Grantgust123/up-tools")
PROJECT_ID = os.environ.get("GITLAB_PROJECT_ID", "370403")
HOST = os.environ.get("GITLAB_HOST", "https://jihulab.com")
HERE = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.abspath(os.path.join(HERE, "..", ".."))


def upload_target(target: str) -> str:
    """copy 到 inbox/ + push。"""
    inbox = os.path.join(REPO_DIR, "inbox")
    os.makedirs(inbox, exist_ok=True)
    dest = os.path.join(inbox, os.path.basename(target))
    shutil.copy2(target, dest)
    print(f"[1/4] 目标已复制: {dest}")
    cmds = [
        f"cd {REPO_DIR} && git add inbox/",
        f"cd {REPO_DIR} && git commit -m 'upload: {os.path.basename(target)}'",
    ]
    for c in cmds:
        r = subprocess.run(c, shell=True, capture_output=True)
        if r.returncode != 0 and b"nothing to commit" not in r.stderr:
            print(f"  commit 警告: {r.stderr.decode()[:100]}")
    # push(用 token)
    url = f"https://Grantgust123:{TOKEN}@jihulab.com/{REPO}.git"
    r = subprocess.run(["git", "-C", REPO_DIR, "push", url, "main"],
                       capture_output=True, timeout=120)
    if r.returncode != 0 and b"up-to-date" not in r.stdout:
        print(f"  push 警告: {r.stdout.decode()[-100:]}")
    print("[2/4] 已推送, pipeline 触发")
    return dest


def get_latest_pipeline() -> dict:
    url = f"{HOST}/api/v4/projects/{PROJECT_ID}/pipelines?per_page=1"
    req = urllib.request.Request(url, headers={"PRIVATE-TOKEN": TOKEN,
                                               "User-Agent": "hermes"})
    with urllib.request.urlopen(req, timeout=15) as r:
        d = json.loads(r.read())
        return d[0] if d else {}


def poll_pipeline(run_id: str, wait: int = 20, max_wait: int = 600) -> dict:
    """轮询直到完成。"""
    print(f"[3/4] 轮询 pipeline #{run_id} ...")
    waited = 0
    while waited < max_wait:
        url = f"{HOST}/api/v4/projects/{PROJECT_ID}/pipelines/{run_id}"
        req = urllib.request.Request(url, headers={"PRIVATE-TOKEN": TOKEN,
                                                   "User-Agent": "hermes"})
        with urllib.request.urlopen(req, timeout=15) as r:
            d = json.loads(r.read())
        status = d.get("status")
        if status in ("success", "failed", "canceled"):
            print(f"  pipeline {status} (用时 {waited}s)")
            return d
        time.sleep(wait)
        waited += wait
    return {"status": "timeout", "id": run_id}


def pull_results() -> None:
    """git pull 拿产物。"""
    url = f"https://Grantgust123:{TOKEN}@jihulab.com/{REPO}.git"
    r = subprocess.run(["git", "-C", REPO_DIR, "pull", url, "main"],
                       capture_output=True, timeout=60)
    print(f"[4/4] git pull: {'完成' if r.returncode == 0 else '失败'}")
    if r.stdout:
        print(f"  {r.stdout.decode()[:200]}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    if not TOKEN:
        print("需要 GITLAB_TOKEN 环境变量")
        return 1
    target = sys.argv[1]
    if not os.path.exists(target):
        print(f"目标不存在: {target}")
        return 1
    upload_target(target)
    # 等 pipeline 出现
    time.sleep(10)
    pipe = get_latest_pipeline()
    if not pipe:
        print("未找到 pipeline")
        return 1
    result = poll_pipeline(str(pipe["id"]))
    if result.get("status") == "success":
        pull_results()
        print("✅ 闭环完成: 上传 → 处理 → 拉结果")
    else:
        print(f"⚠️ pipeline {result.get('status')}, 见极狐 Web 控制台")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
