#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
up-tools regression —— 统一回归

跑全部子工具的测试, 汇总结果, 输出报告。

用法:
  python3 regression.py            # 跑全部 + 输出报告
  python3 regression.py --json     # JSON 报告
  python3 regression.py --summary  # 只输出汇总

只依赖 Python 3.8+ 标准库。
"""
from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

HERE = Path(__file__).resolve().parent

# 每个工具的测试命令(相对 up-tools 根)
SUITES = {
    "v2-codex-skill-injection": {
        "test": ["python3", "tests/test_runner_full.py"],
        "label": "v2 十二段链",
    },
    "v3-five-step-laundering": {
        "test": ["python3", "tests/test_engine.py"],
        "label": "v3 五步法",
    },
    "v4-jailbreak-leak": {
        "test": ["python3", "tests/test_engine.py"],
        "label": "v4 越狱/泄露",
    },
    "v5-jump-patch": {
        "test": ["python3", "tests/test_engine.py"],
        "label": "v5 改跳转",
    },
    "v6-skill-router": {
        "test": ["python3", "tests/test_router.py"],
        "label": "v6 路由",
    },
    "comment-capabilities/01-agents-md-universal": {
        "test": ["python3", "tests/test_engine.py"],
        "label": "评论01 AGENTS通杀",
    },
    "comment-capabilities/02-hotword-attack": {
        "test": ["python3", "tests/test_engine.py"],
        "label": "评论02 热词",
    },
    "comment-capabilities/03-relay-manager": {
        "test": ["python3", "tests/test_engine.py"],
        "label": "评论03 中转站",
    },
    "comment-capabilities/04-skill-ban-analysis": {
        "test": ["python3", "tests/test_engine.py"],
        "label": "评论04 封号分析",
    },
    "comment-capabilities/05-network-verify-burn": {
        "test": ["python3", "tests/test_engine.py"],
        "label": "评论05 用完即焚",
    },
    "toolkit": {
        "test": ["python3", "tests/test_toolkit.py"],
        "label": "toolkit 统一入口",
        "root": HERE,  # toolkit 测试在 up-tools 根
    },
    "config-util": {
        "test": ["python3", "tests/test_config_util.py"],
        "label": "统一配置",
        "root": HERE,
    },
    "recon": {
        "test": ["python3", "tests/test_recon.py"],
        "label": "目标探测",
        "root": HERE,
    },
    "static-analysis": {
        "test": ["python3", "tests/test_static_analysis.py"],
        "label": "静态分析",
        "root": HERE,
    },
    "dynamic-debug": {
        "test": ["python3", "tests/test_dynamic_debug.py"],
        "label": "动态调试",
        "root": HERE,
    },
    "patcher": {
        "test": ["python3", "tests/test_patcher.py"],
        "label": "修改器",
        "root": HERE,
    },
    "verifier": {
        "test": ["python3", "tests/test_verifier.py"],
        "label": "验证器",
        "root": HERE,
    },
    "target-analysis": {
        "test": ["python3", "tests/test_target_analysis.py"],
        "label": "目标情报集成",
        "root": HERE,
    },
    "recon-v2": {
        "test": ["python3", "tests/test_recon_v2.py"],
        "label": "探测v2(保护机制)",
        "root": HERE,
    },
    "analysis-v2": {
        "test": ["python3", "tests/test_analysis_v2.py"],
        "label": "分析v2",
        "root": HERE,
    },
    "countermeasure": {
        "test": ["python3", "tests/test_countermeasure.py"],
        "label": "应对模块",
        "root": HERE,
    },
    "llm-engine": {
        "test": ["python3", "tests/test_llm_engine.py"],
        "label": "LLM 分析引擎",
        "root": HERE,
    },
    "recon-v3": {
        "test": ["python3", "tests/test_recon_v3.py"],
        "label": "探测v3(库增强)",
        "root": HERE,
    },
    "real-binaries": {
        "test": ["python3", "real-binaries/tests/test_real_binaries.py"],
        "label": "真实编译二进制",
        "root": HERE,
    },
    "crackme-e2e": {
        "test": ["python3", "crackme-e2e/tests/test_crackme_e2e.py"],
        "label": "Crackme 端到端",
        "root": HERE,
    },
    "orchestrator": {
        "test": ["python3", "orchestrator/tests/test_orchestrator.py"],
        "label": "沙箱编排/卸载",
        "root": HERE,
    },
    "unified-analysis": {
        "test": ["python3", "unified-analysis/tests/test_unified_analysis.py"],
        "label": "统一分析入口",
        "root": HERE,
    },
    "dynamic-crackmes": {
        "test": ["python3", "dynamic-crackmes/tests/test_dynamic_crackmes.py"],
        "label": "反调试/多校验点",
        "root": HERE,
    },
    "protected-crackmes": {
        "test": ["python3", "protected-crackmes/tests/test_protected_crackmes.py"],
        "label": "带保护Crackme批量",
        "root": HERE,
    },
    "real-crackmes": {
        "test": ["python3", "real-crackmes/tests/test_real_crackmes.py"],
        "label": "真实 Crackme 批量",
        "root": HERE,
    },
}


def _run(tool_dir: str, cmd: List[str], timeout: int = 180) -> Dict[str, Any]:
    """在工具目录跑测试命令。"""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout, cwd=tool_dir)
        out = (p.stdout or "") + "\n" + (p.stderr or "")
        # 提取测试数: "Ran N tests"
        import re
        m = re.search(r"Ran (\d+) tests", out)
        n = int(m.group(1)) if m else 0
        ok = "OK" in out and "FAILED" not in out
        return {"ok": ok, "tests": n, "exit": p.returncode,
                "tail": "\n".join(out.strip().splitlines()[-3:])}
    except FileNotFoundError:
        return {"ok": False, "tests": 0, "exit": 127, "tail": "命令不存在"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "tests": 0, "exit": 124, "tail": "超时"}


def run_all() -> Dict[str, Any]:
    """跑全部套件, 汇总。"""
    results = {}
    for key, info in SUITES.items():
        tdir = info.get("root", HERE / key)
        if not tdir.exists():
            results[key] = {"ok": False, "tests": 0, "tail": "目录缺失",
                            "label": info["label"]}
            continue
        r = _run(str(tdir), info["test"])
        r["label"] = info["label"]
        results[key] = r
    total = sum(r["tests"] for r in results.values())
    ok_count = sum(1 for r in results.values() if r["ok"])
    return {
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "suites": len(SUITES),
        "passed": ok_count,
        "total_tests": total,
        "results": results,
    }


def report_text(report: Dict[str, Any]) -> str:
    lines = []
    lines.append("=" * 60)
    lines.append(f"up-tools 统一回归报告 {report['timestamp']}")
    lines.append("=" * 60)
    for key, r in report["results"].items():
        status = "✓" if r["ok"] else "✗"
        lines.append(f"  {status} {key:<50} {r['label']} "
                     f"({r['tests']} tests)")
        if not r["ok"]:
            for t in r["tail"].splitlines():
                lines.append(f"       {t}")
    lines.append("-" * 60)
    lines.append(f"套件 {report['passed']}/{report['suites']} 通过, "
                 f"共 {report['total_tests']} 个测试")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    p = argparse.ArgumentParser(prog="regression")
    p.add_argument("--json", action="store_true")
    p.add_argument("--summary", action="store_true")
    args = p.parse_args(argv)

    report = run_all()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(report_text(report))
    return 0 if report["passed"] == report["suites"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
