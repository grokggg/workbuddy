#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v6-skill-router CLI

子命令:
  route <文本>           路由决策(命中的 skill / 冲突消解 / 兜底)
  route-table            打印路由表概览
  backend-test           跑一遍 iv8 引擎接口行为契约(mock 后端)
  regen <category> <slug> <file>  案例回血: 写案例 + 更新 taxonomy
  demo                   端到端演示: 路由 + 后端契约 + 回血

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

from lib.router import (  # noqa: E402
    CaseRegen,
    create_backend,
    load_router_table,
    route,
)

DEFAULT_TABLE = HERE / "router_table.yaml"


def cmd_route(args: argparse.Namespace) -> int:
    table = load_router_table(args.table)
    dec = route(args.text, table)
    print(json.dumps(dec.to_dict(), ensure_ascii=False, indent=2))
    return 0


def cmd_route_table(args: argparse.Namespace) -> int:
    table = load_router_table(args.table)
    skills = table.get("skills", [])
    print(f"路由表: {args.table}  version={table.get('version')}")
    print(f"技能数: {len(skills)}  默认兜底: {table.get('default_skill')}")
    print("-" * 60)
    for s in skills:
        n = len(s.get("triggers", []))
        print(f"  {s.get('id','?'):<28} {s.get('role',''):<12} triggers={n}")
    return 0


def cmd_backend_test(args: argparse.Namespace) -> int:
    """跑 iv8 引擎接口行为契约(mock 后端, 无需真 iv8)。"""
    with create_backend("mock") as be:
        ua = be.eval("navigator.userAgent")
        print(f"[1] UA 指纹      : {ua[:40]}...")
        be.load_page("http://127.0.0.1:8899/",
                     "<html><script>document.cookie='__sign=abc123'</script></html>")
        be.advance(3000)
        cookie = be.get_cookie()
        print(f"[2] cookie       : {cookie}")
        logs = be.netlog()
        print(f"[3] netLog 捕获  : {len(logs)} 条 -> {logs[0]['method']} {logs[0]['url'][:50]}...")
        trusted = be.trusted_input("pointerdown", clientX=100, clientY=150)
        print(f"[4] 可信输入     : isTrusted={trusted}")
    # 断言
    assert ua.startswith("Mozilla/5.0"), "UA 指纹缺失"
    assert "abc123" in cookie, "cookie 未生成"
    assert len(logs) >= 1, "netLog 为空"
    assert trusted is True, "可信输入失败"
    print("\n行为契约 4/4 通过")
    return 0


def cmd_regen(args: argparse.Namespace) -> int:
    regen = CaseRegen(args.skill_root)
    code = Path(args.file).read_text(encoding="utf-8")
    meta = {"source": args.source or "manual"}
    out = regen.sync(args.category, args.slug, code,
                     args.desc or f"案例 {args.slug}", meta)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    """端到端演示: 路由 -> 后端契约 -> 案例回血。"""
    print("=" * 60)
    print("v6-skill-router 端到端演示")
    print("=" * 60)

    table = load_router_table(DEFAULT_TABLE)

    print("\n-- 1. 路由决策 --")
    samples = [
        "用 iv8 补环境, 生成一个紧凑 Python 脚本回放请求",
        "这个站点 sign 参数在哪, 帮我定位加密入口",
        "瑞数 412, 走 rs-reverse",
        "AST 解混淆这个 obfuscator.io 的脚本",
        "帮我写个 SKILL.md",
        "今天天气怎么样",
    ]
    for s in samples:
        d = route(s, table)
        print(f"  {s[:34]:<36} -> {d.winner}")

    print("\n-- 2. iv8 引擎接口(mock 后端) --")
    with create_backend("mock") as be:
        ua = be.eval("navigator.userAgent")
        be.load_page("http://127.0.0.1:8899/", "<html><script>document.cookie='__sign=abc'</script></html>")
        be.advance(1000)
        print(f"  UA: {ua[:30]}... | cookie: {be.get_cookie()} | "
              f"netlog: {len(be.netlog())} 条 | trusted: {be.trusted_input('click')}")

    print("\n-- 3. 案例回血 --")
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "v8-web-reverse"
        (root / "references").mkdir(parents=True)
        regen = CaseRegen(root)
        code = "def main():\n    print('demo case')\n"
        out = regen.sync("js-challenges", "demo-case", code,
                         "端到端演示案例", {"source": "demo"})
        print(f"  案例写入: {out['case']}")
        print(f"  taxonomy: {out['taxonomy']}")
        assert Path(out["case"]).exists()
        assert "demo-case" in Path(out["taxonomy"]).read_text(encoding="utf-8")
        print("  回血验证: 通过")

    print("\n演示完成")
    return 0


def main(argv: Optional[list] = None) -> int:
    p = argparse.ArgumentParser(prog="v6-skill-router",
                                description="技能路由架构 CLI")
    p.add_argument("--table", default=str(DEFAULT_TABLE),
                   help="路由表路径(默认 %(default)s)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("route", help="路由决策")
    sp.add_argument("text", help="输入文本")
    sp.set_defaults(fn=cmd_route)

    sp = sub.add_parser("route-table", help="打印路由表")
    sp.set_defaults(fn=cmd_route_table)

    sp = sub.add_parser("backend-test", help="iv8 引擎接口契约测试")
    sp.set_defaults(fn=cmd_backend_test)

    sp = sub.add_parser("regen", help="案例回血")
    sp.add_argument("category", choices=["signatures", "js-challenges",
                                         "browser-tokens",
                                         "network-hook-signing", "captcha"])
    sp.add_argument("slug", help="稳定短 slug")
    sp.add_argument("file", help="案例代码文件")
    sp.add_argument("--desc", default="")
    sp.add_argument("--source", default="")
    sp.add_argument("--skill-root", default=str(HERE),
                    help="skill 根目录(默认本目录)")
    sp.set_defaults(fn=cmd_regen)

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
