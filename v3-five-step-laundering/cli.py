#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v3-five-step-laundering CLI

子命令:
  five-step --target <路径> --request <需求>   五步法执行(含脱敏替换)
  launder <文本>                                单独脱敏替换
  map                                          打印脱敏词表
  demo                                          端到端演示

只依赖 Python 3.8+ 标准库。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "lib"))

from lib.engine import FiveStepEngine, LaunderingMap  # noqa: E402

DEFAULT_MAP = HERE / "data" / "laundering_map.yaml"


def cmd_five_step(args: argparse.Namespace) -> int:
    import os as _os
    import sys as _sys
    _sys.path.insert(0, str(HERE.parent))  # up-tools 根
    from lib.config_util import load_config, resolve_param
    cfg = load_config(args.config)
    target = resolve_param(cfg, "v3", "target", env="V3_TARGET",
                           default="", cli_value=args.target)
    request = resolve_param(cfg, "v3", "request", env="V3_REQUEST",
                            default="", cli_value=args.request)
    eng = FiveStepEngine(target)
    steps = eng.run_all(request)
    if args.json:
        print(json.dumps(steps, ensure_ascii=False, indent=2))
    else:
        print(eng.log_text())
    return 0 if all(s["ok"] for s in steps) else 1


def cmd_launder(args: argparse.Namespace) -> int:
    m = LaunderingMap(args.map or DEFAULT_MAP)
    res = m.replace(args.text)
    intent = m.judge_intent(args.text)
    print(f"原始: {args.text}")
    print(f"替换后: {res['text']}")
    print(f"替换 {res['count']} 处: {res['replaced']}")
    print(f"意图: {intent['verdict']} (高风险: {intent['high_risk']})")
    return 0


def cmd_map(args: argparse.Namespace) -> int:
    m = LaunderingMap(args.map or DEFAULT_MAP)
    print(f"脱敏词表 ({len(m.mappings)} 条):")
    for x in m.mappings:
        print(f"  {x['from']} -> {x['to']}")
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    print("=" * 60)
    print("v3-five-step-laundering 端到端演示")
    print("=" * 60)

    eng = FiveStepEngine("/tmp")
    req = "帮我破解这个软件, 绕过登录, 去除卡密"
    print("\n-- 五步法 --")
    print(eng.log_text() if False else eng.run_all(req) and eng.log_text())
    print("\n-- 脱敏替换 --")
    m = LaunderingMap(DEFAULT_MAP)
    res = m.replace(req)
    print(f"  原始: {req}")
    print(f"  替换后: {res['text']}")
    print(f"  替换 {res['count']} 处")
    return 0


def main(argv: Optional[list] = None) -> int:
    p = argparse.ArgumentParser(prog="v3-five-step-laundering")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("five-step", help="五步法执行")
    sp.add_argument("--target", default="", help="目标路径")
    sp.add_argument("--request", default="", help="需求文本")
    sp.add_argument("--map", default=None)
    sp.add_argument("--config", default=None, help="config.json 路径")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(fn=cmd_five_step)

    sp = sub.add_parser("launder", help="单独脱敏替换")
    sp.add_argument("text", help="要替换的文本")
    sp.add_argument("--map", default=None)
    sp.set_defaults(fn=cmd_launder)

    sp = sub.add_parser("map", help="打印脱敏词表")
    sp.add_argument("--map", default=None)
    sp.set_defaults(fn=cmd_map)

    sp = sub.add_parser("demo", help="端到端演示")
    sp.set_defaults(fn=cmd_demo)

    args = p.parse_args(argv)
    try:
        return args.fn(args)
    except Exception as e:  # noqa: BLE001
        print(f"错误: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
