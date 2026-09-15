#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
up-tools 总入口 —— 路线 B 全模块统一门面(M-B08)

整合: v1 控制台 / v2 冷咖啡 / v3 五步法 / v4 越狱泄露 / v5 改跳转 /
      v6 skill 路由 / 评论区 5 能力

用法:
  python3 cli.py --list-all                     # 列全部模块+能力
  python3 cli.py <module> <args>                # 执行模块(转发)
  python3 cli.py stress --rounds <n>            # 总压测
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

MODULES = {
    "v1":       {"dir": "v1-console", "desc": "四模型统一控制台(BV1cc8L6XExs)",
                 "entry": "cli.py", "args": ["console"]},
    "v2":       {"dir": "v2-codex-skill-injection",
                 "desc": "Codex Skill 注入/冷咖啡(BV15y3U6oEmt)", "entry": "cli.py"},
    "v3":       {"dir": "v3-five-step-laundering", "desc": "五步法+脱敏(BV15iti6aEuM)",
                 "entry": "cli.py"},
    "v4":       {"dir": "v4-jailbreak-leak", "desc": "越狱+提示词泄露(BV1DMUrYbEkC)",
                 "entry": "cli.py"},
    "v5":       {"dir": "v5-jump-patch", "desc": "AI 辅助改跳转(BV1py8668Eqv)",
                 "entry": "cli.py"},
    "v6":       {"dir": "v6-skill-router", "desc": "Skill 路由+iv8(BV13nTj6JEWT)",
                 "entry": "cli.py"},
    "agents-md": {"dir": "comment-capabilities/01-agents-md-universal",
                  "desc": "评论区: 40 行 AGENTS.md 通杀", "entry": "cli.py"},
    "hotword":   {"dir": "comment-capabilities/02-hotword-attack",
                  "desc": "评论区: 热词攻击", "entry": "cli.py"},
    "relay":     {"dir": "comment-capabilities/03-relay-manager",
                  "desc": "评论区: 多 LLM 端点管理", "entry": "cli.py"},
    "skill-ban": {"dir": "comment-capabilities/04-skill-ban-analysis",
                  "desc": "评论区: skill 封号分析", "entry": "cli.py"},
    "net-burn":  {"dir": "comment-capabilities/05-network-verify-burn",
                  "desc": "评论区: 网络验证+用完即焚", "entry": "cli.py"},
}


def list_all() -> None:
    print("=== up-tools 路线 B 全模块 ===")
    for name, info in MODULES.items():
        print(f"  {name:10s} {info['desc']}")
        print(f"           → python3 cli.py {name} --help")


def run_module(name: str, args: list) -> int:
    if name not in MODULES:
        print(f"未知模块: {name}(可用: {', '.join(MODULES)})", file=sys.stderr)
        return 1
    info = MODULES[name]
    d = HERE.parent / info["dir"]  # 模块在 integration/ 的父目录(仓库根)
    cli = d / info["entry"]
    if not cli.exists():
        print(f"模块缺失: {cli}", file=sys.stderr)
        return 1
    cmd = [sys.executable, str(cli)]
    if info.get("args"):
        cmd += info["args"]
    cmd += args
    r = subprocess.run(cmd, cwd=str(d))
    return r.returncode


def run_stress(rounds: int) -> int:
    """总压测: 每模块跑 1 条端到端命令, rounds 轮。"""
    e2e = {
        "v1": ["--backend", "mock", "压测"],
        "v2": ["show", "skill"],
        "v3": ["map"],
        "v4": ["all", "压测问题"],
        "v5": ["--help"],
        "v6": ["demo"],
        "agents-md": ["--dry-run", "--framework", "generic", "--home", "/tmp/stress-c"],
        "hotword": ["--help"],
        "relay": ["--help"],
        "skill-ban": ["--help"],
        "net-burn": ["--help"],
    }
    total = ok = 0
    print(f"=== 总压测: {rounds} 轮 × {len(e2e)} 模块 ===")
    for rnd in range(1, rounds + 1):
        print(f"\n--- 第 {rnd} 轮 ---")
        for name, args in e2e.items():
            total += 1
            rc = run_module(name, args)
            ok += (rc == 0)
            print(f"  {name:10s} {'✓' if rc == 0 else '✗'} (rc={rc})")
    rate = ok / total * 100 if total else 0
    print(f"\n=== 压测结果: {ok}/{total} 通过 ({rate:.1f}%) ===")
    return 0 if ok == total else 1


def main(argv=None) -> int:
    argv = list(argv) if argv else sys.argv[1:]
    if not argv:
        list_all()
        return 0
    if argv[0] == "--list-all":
        list_all()
        return 0
    if argv[0] == "stress":
        rounds = 1
        if len(argv) >= 3 and argv[1] == "--rounds":
            rounds = int(argv[2])
        return run_stress(rounds)
    return run_module(argv[0], argv[1:])


if __name__ == "__main__":
    sys.exit(main())
