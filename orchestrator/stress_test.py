#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stress_test.py —— M37 完整闭环压测

上传 5 个目标到极狐 pipeline, 记录成功率/耗时/失败原因。
"""
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trigger_upload import upload_target, get_latest_pipeline  # noqa: E402

TOKEN = os.environ.get("GITLAB_TOKEN", "")
HOST = os.environ.get("GITLAB_HOST", "https://jihulab.com")
PID = os.environ.get("GITLAB_PROJECT_ID", "370403")
# REPO_DIR: 优先当前工作目录(在仓库内跑), 否则从脚本位置推断
REPO_DIR = os.getcwd()
if not os.path.exists(os.path.join(REPO_DIR, "real-binaries")):
    REPO_DIR = os.path.abspath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", ".."))
print(f"REPO_DIR: {REPO_DIR}")

TARGETS = [
    ("real-binaries/crackme-angr", "真实 ELF crackme"),
    ("dynamic-crackmes/ad1", "反调试 crackme"),
    ("dynamic-crackmes/mc2", "完整性+卡密"),
    ("protected-crackmes/cm-base", "UPX 加壳基类"),
    ("real-crackmes/cm05", "取模校验 crackme"),
]


def poll_pipeline(run_id, wait=30, max_wait=900):
    waited = 0
    while waited < max_wait:
        url = f"{HOST}/api/v4/projects/{PID}/pipelines/{run_id}"
        req = urllib.request.Request(url, headers={"PRIVATE-TOKEN": TOKEN,
                                                   "User-Agent": "hermes"})
        with urllib.request.urlopen(req, timeout=15) as r:
            d = json.loads(r.read())
        status = d.get("status")
        if status in ("success", "failed", "canceled"):
            return {"status": status, "waited": waited, "id": run_id}
        time.sleep(wait)
        waited += wait
    return {"status": "timeout", "waited": waited, "id": run_id}


def main():
    results = []
    for rel, desc in TARGETS:
        tgt = os.path.join(REPO_DIR, rel)
        if not os.path.exists(tgt):
            print(f"[SKIP] {rel} 不存在")
            results.append({"target": rel, "status": "missing"})
            continue
        print(f"\n=== [{rel}] {desc} ===")
        t0 = time.time()
        try:
            upload_target(tgt)
            time.sleep(8)
            pipe = get_latest_pipeline()
            if not pipe:
                results.append({"target": rel, "status": "no-pipeline"})
                continue
            res = poll_pipeline(str(pipe["id"]))
            dt = time.time() - t0
            res["target"] = rel
            res["desc"] = desc
            res["time"] = round(dt, 1)
            results.append(res)
            print(f"  结果: {res['status']} 耗时 {res['time']}s")
        except Exception as e:
            results.append({"target": rel, "status": f"error:{e}"})
            print(f"  异常: {e}")

    # 汇总
    print(f"\n{'='*50}\n压测汇总\n{'='*50}")
    n_ok = sum(1 for r in results if r["status"] == "success")
    for r in results:
        mark = "✅" if r["status"] == "success" else "❌"
        print(f"  {mark} {r['target']}: {r['status']} "
              f"({r.get('time', '')}s)")
    total_time = sum(r.get("time", 0) for r in results)
    print(f"\n成功率: {n_ok}/{len(results)}")
    print(f"总耗时: {total_time:.0f}s | 平均: {total_time/max(len(results),1):.0f}s/次")
    report = {"results": results, "success_rate": f"{n_ok}/{len(results)}",
              "total_time_s": round(total_time)}
    with open("/tmp/m37/stress-report.json", "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return 0 if n_ok >= len(results) * 0.6 else 1


if __name__ == "__main__":
    raise SystemExit(main())
