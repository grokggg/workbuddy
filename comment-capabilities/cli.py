#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
comment-abilities —— 评论区 5 能力统一入口(M-B07)

用法:
  python3 cli.py --list-abilities              # 列全部能力
  python3 cli.py ability <name> --help          # 看某能力子命令
  python3 cli.py ability <name> <args>          # 执行(转发到模块 cli)
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

ABILITIES = {
    "agents-md": {
        "dir": "01-agents-md-universal", "desc": "40 行 AGENTS.md 通杀(生成器)"
    },
    "hotword": {
        "dir": "02-hotword-attack", "desc": "热词攻击(热度污染分析+检索影响)"
    },
    "relay": {
        "dir": "03-relay-manager", "desc": "多 LLM API 端点管理(注册/切换/健康)"
    },
    "skill-ban": {
        "dir": "04-skill-ban-analysis", "desc": "skill 绕过包封号(风险分析)"
    },
    "net-burn": {
        "dir": "05-network-verify-burn", "desc": "网络验证+用完即焚(令牌生命周期)"
    },
}


def list_abilities() -> None:
    print("=== 评论区 5 能力 ===")
    for name, info in ABILITIES.items():
        print(f"  {name:12s} {info['desc']}")
        print(f"            → python3 cli.py ability {name} --help")


def run_ability(name: str, args: list) -> int:
    if name not in ABILITIES:
        print(f"未知能力: {name}(可用: {', '.join(ABILITIES)})", file=sys.stderr)
        return 1
    d = HERE / ABILITIES[name]["dir"]
    cli = d / "cli.py"
    if not cli.exists():
        print(f"模块缺失: {cli}", file=sys.stderr)
        return 1
    r = subprocess.run([sys.executable, str(cli)] + args, cwd=str(d))
    return r.returncode


def main(argv=None) -> int:
    argv = list(argv) if argv else sys.argv[1:]
    # 手工解析: --list-abilities / ability <name> <args...>
    if argv and argv[0] == "--list-abilities":
        list_abilities()
        return 0
    if argv and argv[0] == "ability":
        rest = argv[1:]
        if not rest:
            list_abilities()
            return 0
        name = rest[0]
        return run_ability(name, rest[1:])
    # 直接转发: cli.py <name> <args...>
    if argv:
        return run_ability(argv[0], argv[1:])
    list_abilities()
    return 0


if __name__ == "__main__":
    sys.exit(main())
