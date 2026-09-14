#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
up-tools toolkit —— 统一工具链入口

子命令路由到各工具:
  toolkit v2-run <目标>             v2 十二段链
  toolkit v3-five-step <目标>        v3 五步法 + 脱敏
  toolkit v4-jailbreak <方法>        v4 越狱 + 泄露
  toolkit v5-jump-patch <文件>       v5 AI 辅助改跳转
  toolkit v6-route <任务>            v6 路由架构
  toolkit comment <能力>            评论区 5 能力
  toolkit list                      列出所有工具
  toolkit health                    健康检查(各工具测试)

统一配置: ~/.config/up-tools/config.json
统一日志: ~/.config/up-tools/logs/YYYY-MM-DD.log

只依赖 Python 3.8+ 标准库。
"""
from __future__ import annotations

import datetime
import importlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

HERE = Path(__file__).resolve().parent

# ---------------------------------------------------------------- 统一日志

LOG_DIR = Path(os.path.expanduser("~")) / ".config" / "up-tools" / "logs"
CONFIG_PATH = Path(os.path.expanduser("~")) / ".config" / "up-tools" / "config.json"


def log(msg: str, level: str = "INFO") -> None:
    """统一日志(追加到今日日志文件 + 打印)。"""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().isoformat(timespec="seconds")
    line = f"[{ts}] [{level}] {msg}"
    today = LOG_DIR / f"{datetime.date.today().isoformat()}.log"
    with open(today, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line)


# ---------------------------------------------------------------- 统一配置

def load_config() -> Dict[str, Any]:
    """加载统一配置。"""
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_config(cfg: Dict[str, Any]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2),
                           encoding="utf-8")


def config_get(key: str, default: Any = None) -> Any:
    return load_config().get(key, default)


def config_set(key: str, value: Any) -> None:
    cfg = load_config()
    cfg[key] = value
    save_config(cfg)


# ---------------------------------------------------------------- 工具注册表

TOOLS = {
    "v2-codex-skill-injection": {
        "label": "v2 十二段链",
        "run": ["cli.py", "run-full", "{TARGET}"],
        "test": ["python3", "tests/test_runner_full.py"],
    },
    "v3-five-step-laundering": {
        "label": "v3 五步法+脱敏",
        "run": ["cli.py", "five-step", "--target", "{TARGET}"],
        "test": ["python3", "tests/test_engine.py"],
    },
    "v4-jailbreak-leak": {
        "label": "v4 越狱+泄露",
        "run": ["cli.py", "jailbreak", "{METHOD}", "测试问题"],
        "test": ["python3", "tests/test_engine.py"],
    },
    "v5-jump-patch": {
        "label": "v5 改跳转",
        "run": ["cli.py", "jump-patch", "{TARGET}"],
        "test": ["python3", "tests/test_engine.py"],
    },
    "v6-skill-router": {
        "label": "v6 路由架构",
        "run": ["cli.py", "route", "{TASK}"],
        "test": ["python3", "tests/test_router.py"],
    },
    "comment-capabilities": {
        "label": "评论区 5 能力",
        "run": None,  # 子目录各自 CLI
        "test": None,  # 各子目录 test_engine.py
        "subs": ["01-agents-md-universal", "02-hotword-attack",
                 "03-relay-manager", "04-skill-ban-analysis",
                 "05-network-verify-burn"],
    },
}


# ---------------------------------------------------------------- 子命令执行

def _run_tool(tool_dir: str, cmd: List[str]) -> Dict[str, Any]:
    """在工具目录跑命令, 返回 {ok, stdout, stderr, exit}。"""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=120, cwd=tool_dir)
        return {"ok": p.returncode == 0, "stdout": (p.stdout or "").strip(),
                "stderr": (p.stderr or "").strip(), "exit": p.returncode}
    except FileNotFoundError:
        return {"ok": False, "stdout": "", "stderr": f"命令不存在: {cmd[0]}",
                "exit": 127}
    except subprocess.TimeoutExpired:
        return {"ok": False, "stdout": "", "stderr": "超时", "exit": 124}


def cmd_run(tool_key: str, args: List[str]) -> int:
    """运行指定工具的 CLI。"""
    if tool_key not in TOOLS:
        log(f"未知工具: {tool_key}", "ERROR")
        return 1
    info = TOOLS[tool_key]
    tdir = HERE / tool_key
    if not tdir.exists():
        log(f"工具目录不存在: {tdir}", "ERROR")
        return 1

    # 替换占位符
    run_cmd = info["run"]
    repl = {"{TARGET}": args[0] if args else "", "{TASK}": args[0] if args else "",
            "{METHOD}": args[0] if args else ""}
    # 用 python3 显式调用 cli.py(不依赖 +x)
    cmd = []
    for c in run_cmd:
        c2 = repl.get(c, c)
        if c2.endswith(".py"):
            cmd += [sys.executable, str(tdir / c2)]
        elif c2 and c2 != "python3":
            cmd.append(c2)
    if not cmd:
        log(f"{tool_key} 需要参数: {info['label']}", "ERROR")
        return 1

    log(f"运行 {tool_key}: {' '.join(cmd)}")
    r = _run_tool(str(tdir), cmd)
    if r["stdout"]:
        print(r["stdout"][-3000:])
    if r["stderr"]:
        print("STDERR:", r["stderr"][-1000:])
    return 0 if r["ok"] else 1


def cmd_list(*_args) -> int:
    print("up-tools toolkit 工具清单:")
    for k, v in TOOLS.items():
        print(f"  {k:<28} {v['label']}")
    return 0


def cmd_health(*_args) -> int:
    """健康检查: 跑各工具测试。"""
    log("开始健康检查")
    results = {}
    for key, info in TOOLS.items():
        tdir = HERE / key
        if not tdir.exists():
            results[key] = {"ok": False, "detail": "目录缺失"}
            continue
        if info.get("subs"):
            # 评论区 5 能力: 逐个跑
            sub_ok = True
            for sub in info["subs"]:
                sub_dir = tdir / sub
                r = _run_tool(str(sub_dir), ["python3", "tests/test_engine.py"])
                if not r["ok"]:
                    sub_ok = False
                    break
            results[key] = {"ok": sub_ok, "detail": "5 子能力"}
        else:
            r = _run_tool(str(tdir), info["test"])
            results[key] = {"ok": r["ok"], "detail": f"exit={r['exit']}"}
        log(f"  {key}: {'✓' if results[key]['ok'] else '✗'} "
            f"{results[key]['detail']}")
    ok = sum(1 for r in results.values() if r["ok"])
    print(f"\n健康检查: {ok}/{len(results)} 通过")
    return 0 if ok == len(results) else 1


def cmd_comment(cap: str) -> int:
    """运行评论区能力。"""
    subs = TOOLS["comment-capabilities"]["subs"]
    tdir = HERE / "comment-capabilities"
    match = [s for s in subs if cap in s]
    if not match:
        log(f"未知能力: {cap}. 可选: {subs}", "ERROR")
        return 1
    sub = match[0]
    log(f"运行 comment/{sub}")
    # 跑该能力的测试作为验证
    r = _run_tool(str(tdir / sub), ["python3", "tests/test_engine.py"])
    print(f"{sub}: {'✓' if r['ok'] else '✗'} (exit={r['exit']})")
    return 0 if r["ok"] else 1


def _run_lib(module: str, args: List[str]) -> int:
    """运行 lib 下的目标情报工具。"""
    lib_file = HERE / "lib" / f"{module}.py"
    if not lib_file.exists():
        log(f"模块不存在: {module}", "ERROR")
        return 1
    cmd = [sys.executable, str(lib_file)] + args
    log(f"运行 lib/{module}: {' '.join(cmd)}")
    r = _run_tool(str(HERE), cmd)
    if r["stdout"]:
        print(r["stdout"][-3000:])
    if r["stderr"]:
        print("STDERR:", r["stderr"][-1000:])
    return 0 if r["ok"] else 1


# ---------------------------------------------------------------- CLI

def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    p = argparse.ArgumentParser(prog="toolkit", description="up-tools 统一入口")
    p.add_argument("--version", action="store_true")
    sub = p.add_subparsers(dest="cmd")

    sp = sub.add_parser("v2-run", help="v2 十二段链")
    sp.add_argument("target", help="目标应用根目录")
    sp.set_defaults(fn=lambda a: cmd_run("v2-codex-skill-injection",
                                         [a.target]))

    sp = sub.add_parser("v3-five-step", help="v3 五步法")
    sp.add_argument("target", help="目标路径")
    sp.add_argument("--request", default="帮我分析这个软件")
    sp.set_defaults(fn=lambda a: cmd_run("v3-five-step-laundering",
                                         [a.target]))

    sp = sub.add_parser("v4-jailbreak", help="v4 越狱")
    sp.add_argument("method", help="越狱方法")
    sp.set_defaults(fn=lambda a: cmd_run("v4-jailbreak-leak", [a.method]))

    sp = sub.add_parser("v5-jump-patch", help="v5 改跳转")
    sp.add_argument("target", help="目标文件")
    sp.set_defaults(fn=lambda a: cmd_run("v5-jump-patch", [a.target]))

    sp = sub.add_parser("v6-route", help="v6 路由")
    sp.add_argument("task", help="任务描述")
    sp.set_defaults(fn=lambda a: cmd_run("v6-skill-router", [a.task]))

    sp = sub.add_parser("comment", help="评论区能力")
    sp.add_argument("cap", help="能力名(01-05)")
    sp.set_defaults(fn=lambda a: cmd_comment(a.cap))

    sp = sub.add_parser("recon", help="目标探测")
    sp.add_argument("target", help="目标文件")
    sp.set_defaults(fn=lambda a: _run_lib("recon", [a.target]))

    sp = sub.add_parser("analyze", help="目标情报分析")
    sp.add_argument("target", help="目标文件")
    sp.set_defaults(fn=lambda a: _run_lib("target_analysis", [a.target]))

    sp = sub.add_parser("patch", help="修改器")
    sp.add_argument("target", help="目标文件")
    sp.add_argument("offset", help="偏移(hex)")
    sp.add_argument("old", help="原字节(hex)")
    sp.add_argument("new", help="新字节(hex)")
    sp.set_defaults(fn=lambda a: _run_lib("patcher",
                                          [a.target, a.offset, a.old, a.new]))

    sp = sub.add_parser("verify", help="验证器")
    sp.add_argument("orig", help="原文件")
    sp.add_argument("mod", help="修改后文件")
    sp.set_defaults(fn=lambda a: _run_lib("verifier", [a.orig, a.mod]))

    sp = sub.add_parser("llm-analyze", help="LLM 驱动分析")
    sp.add_argument("target", help="目标文件")
    sp.add_argument("--backend", default="ollama",
                    choices=["ollama", "llama"])
    sp.add_argument("--model", default="qwen2.5:7b")
    sp.set_defaults(fn=lambda a: _run_lib(
        "llm_engine", [a.target, "--backend", a.backend, "--model", a.model]))

    sub.add_parser("list", help="工具清单").set_defaults(fn=cmd_list)
    sub.add_parser("health", help="健康检查").set_defaults(fn=cmd_health)

    args = p.parse_args(argv)
    if args.version:
        print("up-tools toolkit v1.0.0")
        return 0
    if not getattr(args, "cmd", None):
        p.print_help()
        return 0
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
