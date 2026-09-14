#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
oracle_cloud.py —— M35 Oracle Cloud 后端(长期兜底)

流程: SSH 上传目标 → 远程执行分析 → 拉回结果
依赖: 本机 ssh/scp + Oracle VM(见 oraclesetup.md)

环境变量: ORACLE_SSH_KEY(私钥路径), ORACLE_HOST(主机)
"""
from __future__ import annotations

import os
import subprocess
import sys
from typing import Any, Dict, Optional

HOST = os.environ.get("ORACLE_HOST", "")
USER = os.environ.get("ORACLE_USER", "ubuntu")
KEY = os.environ.get("ORACLE_SSH_KEY", "~/.ssh/id_rsa")
REMOTE_DIR = os.environ.get("ORACLE_REMOTE_DIR", "~/up-tools")


def ssh_cmd(cmd: str, timeout: int = 60) -> tuple:
    r = subprocess.run(
        ["ssh", "-i", os.path.expanduser(KEY), "-o", "StrictHostKeyChecking=no",
         f"{USER}@{HOST}", cmd],
        capture_output=True, timeout=timeout)
    return r.stdout.decode(errors="ignore"), r.returncode


def upload(local: str, remote: str, timeout: int = 120) -> bool:
    r = subprocess.run(
        ["scp", "-i", os.path.expanduser(KEY), "-o", "StrictHostKeyChecking=no",
         local, f"{USER}@{HOST}:{remote}"],
        capture_output=True, timeout=timeout)
    return r.returncode == 0


def download(remote: str, local: str, timeout: int = 120) -> bool:
    r = subprocess.run(
        ["scp", "-i", os.path.expanduser(KEY), "-o", "StrictHostKeyChecking=no",
         f"{USER}@{HOST}:{remote}", local],
        capture_output=True, timeout=timeout)
    return r.returncode == 0


def setup_remote(timeout: int = 180) -> Dict[str, Any]:
    """远程装工具(首次)。"""
    cmds = [
        "sudo apt-get update -qq",
        "sudo apt-get install -y -qq gcc gdb binutils python3-pip",
        "pip3 install --quiet capstone pyelftools pefile",
    ]
    for c in cmds:
        out, rc = ssh_cmd(c, timeout)
        if rc != 0:
            return {"ok": False, "step": c, "error": out[-200:]}
    return {"ok": True, "steps": len(cmds)}


def run_analysis(target: str, timeout: int = 300) -> Dict[str, Any]:
    """远程跑统一分析。"""
    # 1. 上传目标
    remote_target = f"{REMOTE_DIR}/{os.path.basename(target)}"
    if not upload(target, remote_target):
        return {"ok": False, "step": "upload", "error": "scp 失败"}
    # 2. 远程执行
    cmd = (f"cd {REMOTE_DIR} && "
           f"python3 unified-analysis/analysis_all.py "
           f"{os.path.basename(target)} --out /tmp/o --json")
    out, rc = ssh_cmd(cmd, timeout)
    return {"ok": rc == 0, "rc": rc, "output": out[-500:]}


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(prog="oracle-backend")
    p.add_argument("--setup", action="store_true", help="远程装工具")
    p.add_argument("--run", metavar="TARGET", help="上传+远程分析")
    args = p.parse_args()

    if not HOST:
        print("未配置 ORACLE_HOST 环境变量(见 oraclesetup.md)")
        return 1
    if args.setup:
        r = setup_remote()
        print(f"setup: {'✅' if r['ok'] else '❌'} {r.get('error', '')}")
    if args.run:
        r = run_analysis(args.run)
        print(f"run: {'✅' if r['ok'] else '❌'}")
        if r.get("output"):
            print(r["output"])
    return 0 if (not args.setup and not args.run) or \
        (not args.setup or r.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
