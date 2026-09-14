#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
batch_ci.py —— M36 多目标批量上传处理

用法:
  python3 batch_ci.py <目录或文件...>
  python3 batch_ci.py --search "crackme linux" [--count 3]

流程: 逐个目标 → 上传 inbox → push → 等 pipeline → 汇总结果
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trigger_upload import upload_target, get_latest_pipeline, poll_pipeline  # noqa: E402


def search_download(query: str, count: int) -> list:
    """GitHub 搜索 + 下载候选。"""
    url = (f"https://api.github.com/search/repositories?q={query}"
           f"&sort=stars&per_page={count}")
    req = urllib.request.Request(url, headers={"User-Agent": "hermes"})
    with urllib.request.urlopen(req, timeout=15) as r:
        d = json.loads(r.read())
    results = []
    for repo in d.get("items", [])[:count]:
        results.append({"repo": repo["full_name"], "stars": repo["stargazers_count"]})
    return results


def main():
    p = argparse.ArgumentParser(prog="batch-ci")
    p.add_argument("targets", nargs="*", help="目标文件/目录")
    p.add_argument("--search", help="GitHub 搜索词(替代手动指定)")
    p.add_argument("--count", type=int, default=3)
    args = p.parse_args()

    # 收集目标
    targets = []
    if args.search:
        print(f"搜索 '{args.search}' ...")
        found = search_download(args.search, args.count)
        for f in found:
            print(f"  {f['repo']} ⭐{f['stars']}")
        print("(下载需逐个处理, 此处列出候选)")
        return 0
    for t in args.targets:
        if os.path.isfile(t):
            targets.append(t)
        elif os.path.isdir(t):
            targets += [os.path.join(t, f) for f in os.listdir(t)
                        if os.path.isfile(os.path.join(t, f))]
    if not targets:
        print("无目标, 用法: batch_ci.py <文件或目录> 或 --search")
        return 1

    # 逐个上传 + 等结果
    results = []
    for t in targets:
        print(f"\n{'='*40}\n[{os.path.basename(t)}]\n{'='*40}")
        try:
            upload_target(t)
            time.sleep(10)
            pipe = get_latest_pipeline()
            if not pipe:
                results.append({"target": t, "status": "no-pipeline"})
                continue
            res = poll_pipeline(str(pipe["id"]), wait=30, max_wait=600)
            results.append({"target": t, "pipeline": pipe.get("id"),
                            "status": res.get("status")})
        except Exception as e:
            results.append({"target": t, "status": f"error: {e}"})

    # 汇总
    print(f"\n{'='*40}\n批量汇总\n{'='*40}")
    n_ok = sum(1 for r in results if r["status"] == "success")
    for r in results:
        mark = "✅" if r["status"] == "success" else "❌"
        print(f"  {mark} {os.path.basename(r['target'])}: {r['status']}")
    print(f"\n成功率: {n_ok}/{len(results)}")
    return 0 if n_ok == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
