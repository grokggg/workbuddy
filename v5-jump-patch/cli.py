#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v5-jump-patch CLI

用法:
  python3 cli.py jump-patch <目标文件> [--jump-index N] [--verify-cmd "..."]
  python3 cli.py analyze <目标文件>
  python3 cli.py --json ...

只依赖 Python 3.8+ 标准库。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "lib"))

from lib.engine import Analyzer, JumpPatchEngine  # noqa: E402


def cmd_jump_patch(args) -> int:
    import tempfile
    import sys as _sys
    _sys.path.insert(0, str(HERE.parent))  # up-tools 根
    from lib.config_util import load_config, resolve_param
    cfg = load_config(args.config)
    target = resolve_param(cfg, "v5", "target_file", env="V5_TARGET_FILE",
                           default="", cli_value=args.target)
    if not target:
        print("错误: 未指定目标文件。用命令行参数 / V5_TARGET_FILE / config.json",
              file=sys.stderr)
        return 1
    work_dir = args.work_dir or os.path.join(tempfile.gettempdir(),
                                             "v5-jump-patch")
    eng = JumpPatchEngine(target, work_dir)
    verify_cmd = args.verify_cmd.split() if args.verify_cmd else None
    steps = eng.run_all(args.jump_index, verify_cmd)
    if args.json:
        print(json.dumps(steps, ensure_ascii=False, indent=2))
    else:
        print(eng.log_text())
    return 0 if all(s["ok"] for s in steps) else 1


def cmd_analyze(args) -> int:
    a = Analyzer(args.target)
    r = a.analyze()
    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print(r["detail"])
        if r.get("strings"):
            print(f"  字符串样本: {r['strings'][:8]}")
        jumps = r.get("jump_hits", [])
        print(f"  条件跳转: {len(jumps)} 处")
        for j in jumps[:10]:
            print(f"    offset={j['offset']:#x} {j['mnemonic']} "
                  f"({j['opcode']})")
    return 0 if r["ok"] else 1


def main(argv=None) -> int:
    import argparse
    p = argparse.ArgumentParser(
        prog="v5-jump-patch",
        description="AI 辅助改跳转(BV1py8668Eqv 复现)")
    p.add_argument("--json", action="store_true")
    sub = p.add_subparsers(dest="cmd")

    sp = sub.add_parser("jump-patch", help="完整流程: 分析->定位->修改->验证")
    sp.add_argument("target", nargs="?", default=None,
                    help="目标文件(默认从 config/环境变量)")
    sp.add_argument("--work-dir", default=None)
    sp.add_argument("--jump-index", type=int, default=0)
    sp.add_argument("--config", default=None, help="config.json 路径")
    sp.add_argument("--verify-cmd", default=None, help="验证命令(空格分隔)")
    sp.set_defaults(fn=cmd_jump_patch)

    sp = sub.add_parser("analyze", help="只分析")
    sp.add_argument("target", help="目标文件")
    sp.set_defaults(fn=cmd_analyze)

    args = p.parse_args(argv)
    if not getattr(args, "cmd", None):
        p.print_help()
        return 0
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
