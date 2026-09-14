#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
remote_run.py —— M36 通过 SSH 远程执行分析

用法:
  python3 remote_run.py <目标文件> [--host IP] [--key 私钥] [--user ubuntu]

流程: 上传目标 → 远程跑 analysis_all → 拉回报告
"""
import argparse
import os
import subprocess
import sys

DEFAULT_HOST = os.environ.get("ORACLE_HOST", "")
DEFAULT_KEY = os.environ.get("ORACLE_SSH_KEY", "~/.ssh/oracle_arm")
DEFAULT_USER = os.environ.get("ORACLE_USER", "ubuntu")
REMOTE = "~/up-tools"


def ssh(host, key, user, cmd, timeout=300):
    r = subprocess.run(
        ["ssh", "-i", os.path.expanduser(key), "-o",
         "StrictHostKeyChecking=no", f"{user}@{host}", cmd],
        capture_output=True, timeout=timeout)
    return r.stdout.decode(errors="ignore"), r.returncode


def scp_up(host, key, user, local, remote, timeout=120):
    r = subprocess.run(
        ["scp", "-i", os.path.expanduser(key), "-o",
         "StrictHostKeyChecking=no", local, f"{user}@{host}:{remote}"],
        capture_output=True, timeout=timeout)
    return r.returncode == 0


def main():
    p = argparse.ArgumentParser(prog="remote-run")
    p.add_argument("target", help="目标文件")
    p.add_argument("--host", default=DEFAULT_HOST)
    p.add_argument("--key", default=DEFAULT_KEY)
    p.add_argument("--user", default=DEFAULT_USER)
    args = p.parse_args()

    if not args.host:
        print("需要 --host 或 ORACLE_HOST 环境变量")
        return 1
    if not os.path.exists(args.target):
        print(f"目标不存在: {args.target}")
        return 1

    print(f"[1/3] 上传 {args.target} → Oracle")
    base = os.path.basename(args.target)
    if not scp_up(args.host, args.key, args.user, args.target, f"{REMOTE}/inbox/"):
        print("上传失败")
        return 1

    print("[2/3] 远程执行分析")
    out, rc = ssh(args.host, args.key, args.user,
                  f"cd {REMOTE} && python3 unified-analysis/analysis_all.py "
                  f"inbox/{base} --out /tmp/o --json")
    print(out[:800])
    if rc != 0:
        print(f"远程执行 rc={rc}")
        return 1

    print("[3/3] 拉回报告")
    r = subprocess.run(
        ["scp", "-i", os.path.expanduser(args.key), "-o",
         "StrictHostKeyChecking=no",
         f"{args.user}@{args.host}:{REMOTE}/inbox/{base}",
         f"{base}.remote"],
        capture_output=True, timeout=120)
    print(f"结果: {base}.remote")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
