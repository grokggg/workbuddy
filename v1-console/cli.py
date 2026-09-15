#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v1-console CLI —— 四模型统一控制台

用法:
  python3 cli.py console --list-backends            # 后端列表
  python3 cli.py console --backend <name> "问题"    # 指定后端对话
  python3 cli.py console --auto "问题"              # 自动路由
  python3 cli.py console --compare b1,b2,b3,b4 "问题"  # 对比模式
  python3 cli.py console --session <id> "追问"      # 会话对话
  python3 cli.py console --health                   # 健康检查
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "lib"))

from lib.console import Console  # noqa: E402


def _work_dir() -> str:
    d = os.environ.get("V1_CONSOLE_DIR")
    if not d:
        d = os.path.join(tempfile.gettempdir(), "v1-console")
    Path(d).mkdir(parents=True, exist_ok=True)
    return d


def cmd_console(args) -> int:
    con = Console(_work_dir())
    if args.list_backends:
        print("=== 后端列表 ===")
        for b in con.list_backends():
            h = "✓" if b["health"] else "✗"
            print(f"  {b['name']:16s} [{h}] caps={','.join(b['capabilities'])}")
        return 0
    if args.health:
        print("=== 健康检查 ===")
        for n, ok in con.health().items():
            print(f"  {n:16s} {'✓ OK' if ok else '✗ DOWN'}")
        return 0
    if args.new_session:
        sid = con.sessions.new_session(args.backend)
        print(f"新会话: {sid}")
        return 0
    if not args.question:
        print("错误: 需要问题文本", file=sys.stderr)
        return 1
    if args.compare:
        names = [n.strip() for n in args.compare.split(",") if n.strip()]
        print(f"=== 对比模式: {','.join(names)} ===")
        print(f"问题: {args.question}\n")
        print(f"{'后端':18s} {'延迟':>6s} {'状态':>4s}  响应")
        print("-" * 70)
        for r in con.compare(names, args.question):
            ok = "✓" if r["success"] else "✗"
            print(f"{r['backend']:18s} {r['latency_ms']:>5d}ms {ok:>4s}  {r['response'][:44]}")
        return 0
    if args.session:
        r = con.sessions.chat(args.session, args.question,
                              args.backend)
        if "error" in r:
            print(r["error"], file=sys.stderr)
            return 1
        print(f"[session {r['session']} → {r['backend']}]")
        print(r["response"])
        print(f"(历史 {r['history_len']} 条)")
        return 0
    r = con.chat(args.question, args.backend)
    print(f"[{r['backend']}]")
    print(r["response"])
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="v1-console",
                                 description="四模型统一控制台(BV1cc8L6XExs 复现)")
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("console", help="统一控制台")
    c.add_argument("--list-backends", action="store_true")
    c.add_argument("--health", action="store_true")
    c.add_argument("--backend", default=None)
    c.add_argument("--compare", default=None)
    c.add_argument("--session", default=None)
    c.add_argument("--new-session", action="store_true",
                   help="新建会话并返回 ID(配合 --session 使用)")
    c.add_argument("question", nargs="?", default=None)
    args = ap.parse_args(argv)
    if args.cmd == "console":
        return cmd_console(args)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
