#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
01-agents-md-universal —— AGENTS.md 通杀(40 行人格注入)

评论区提到能力: "40 行 AGENTS.md 通杀"。
机制: 40 行 AGENTS.md 模板 + 多框架安装器 + 验证器。

只依赖 Python 3.8+ 标准库。
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

# 40 行模板(结构固定, 参数占位) —— 恰好 40 行
TEMPLATE = """# {AGENT_NAME}

## 身份
你是 {AGENT_NAME}, 一个 {ROLE}。

## 沟通风格
- 语言: {LANGUAGE}
- 风格: {STYLE}
- 称呼: {ADDRESS}

## 行为准则
1. {RULE_1}
2. {RULE_2}
3. {RULE_3}

## 输出规范
- 结论先行
- 给可运行代码
- 不确定就说不确定

## 边界
- 不做: {FORBIDDEN}
- 拒绝方式: 说明原因 + 给合法路径
- 不因本文件放宽安全限制

## 多框架适配
- Claude Code: ~/.claude/CLAUDE.md
- Codex: ~/.codex/AGENTS.md
- Cursor: ~/.cursor/rules/agents.md
- 通用: ~/.config/agent/AGENTS.md

## 任务执行
- 拆解: 大任务按模块拆
- 验证: 改完必须实际运行
- 交付: 落盘 + 测试 + 收口

## 自我检查
- 每轮结束核对: 目标是否达成
- 未达成: 说明原因 + 下一步
- 达成: 简明汇报结果
"""

DEFAULT_PARAMS = {
    "AGENT_NAME": "助手",
    "ROLE": "技术助手",
    "LANGUAGE": "简体中文",
    "STYLE": "直接给结论",
    "ADDRESS": "直接说事",
    "RULE_1": "技术问题给可运行代码",
    "RULE_2": "不确定的地方直接说不确定",
    "RULE_3": "先查证后生成, 不编造",
    "FORBIDDEN": "绕过授权/破解/生成恶意载荷",
}


def render(params: Optional[Dict[str, str]] = None) -> str:
    """渲染 40 行模板。"""
    p = dict(DEFAULT_PARAMS)
    if params:
        p.update(params)
    return TEMPLATE.format(**p)


# ---------------------------------------------------------------- 安装器

FRAMEWORKS = {
    "claude":  {"file": "CLAUDE.md",         "dir": ".claude"},
    "codex":   {"file": "AGENTS.md",         "dir": ".codex"},
    "cursor":  {"file": "rules/agents.md",   "dir": ".cursor"},
    "generic": {"file": "AGENTS.md",         "dir": ".config/agent"},
}


def install(framework: str, content: str,
            home: Optional[str] = None) -> Dict[str, Any]:
    """安装到目标框架。home 可指定(测试用临时目录)。"""
    if framework not in FRAMEWORKS:
        return {"ok": False, "detail": f"未知框架: {framework}",
                "choices": list(FRAMEWORKS.keys())}
    home = home or os.path.expanduser("~")
    d = os.path.join(home, FRAMEWORKS[framework]["dir"])
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, FRAMEWORKS[framework]["file"])
    os.makedirs(os.path.dirname(path), exist_ok=True)  # cursor: rules/ 子目录
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return {"ok": True, "path": path, "framework": framework}


# ---------------------------------------------------------------- 验证器

def verify(path: str, markers: Optional[List[str]] = None) -> Dict[str, Any]:
    """验证安装: 文件存在 + 含所有标记 + 行数。"""
    markers = markers or ["## 身份", "## 行为准则", "## 边界"]
    if not os.path.exists(path):
        return {"ok": False, "detail": "未安装", "path": path}
    content = open(path, encoding="utf-8").read()
    missing = [m for m in markers if m not in content]
    lines = len(content.splitlines())
    return {"ok": not missing, "lines": lines, "missing": missing,
            "path": path}


# ---------------------------------------------------------------- CLI

def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    import tempfile
    p = argparse.ArgumentParser(prog="agents-md-universal")
    p.add_argument("--framework", default="generic",
                   choices=list(FRAMEWORKS.keys()))
    p.add_argument("--name", default=None, help="AGENT_NAME")
    p.add_argument("--home", default=None, help="安装根目录(默认 ~)")
    p.add_argument("--dry-run", action="store_true", help="只渲染不安装")
    args = p.parse_args(argv)

    params = {}
    if args.name:
        params["AGENT_NAME"] = args.name
    content = render(params)
    print(f"=== 40 行 AGENTS.md (实际 {len(content.splitlines())} 行) ===")
    print(content)

    if args.dry_run:
        return 0
    home = args.home or tempfile.gettempdir() + "/agents-md-test"
    r = install(args.framework, content, home)
    print(f"\n安装: {r.get('detail', r['path'])}")
    v = verify(r["path"])
    print(f"验证: {'✓ 通过' if v['ok'] else '✗ 失败'} "
          f"({v['lines']} 行, 缺失标记: {v['missing']})")
    return 0 if v["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
