#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
05-network-verify-burn CLI —— 一次性令牌: 签发 / 验证 / 烧毁 / 审计

用法示例:
  python3 cli.py issue --key note.md            # 签发(内容按需加载)
  python3 cli.py issue --key note.md --content '机密'   # 签发(内容直给)
  python3 cli.py verify <TOKEN>                 # 验证 + 返回临时加载内容
  python3 cli.py burn <TOKEN>                   # 用完即焚
  python3 cli.py audit                          # 状态审计

注: 模拟服务端仅内存存储, 进程退出即清零。
"""
from __future__ import annotations

import argparse
import sys
from typing import List, Optional

sys.path.insert(0, __file__.rsplit("/", 1)[0])

from lib.engine import BurnServer  # noqa: E402


def _parse(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="network-verify-burn",
                                description="网络验证 + 用完即焚(模拟服务端)")
    p.add_argument("--ttl", type=float, default=300.0,
                   help="令牌有效秒数(默认 300)")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_issue = sub.add_parser("issue", help="签发一次性令牌")
    p_issue.add_argument("--key", required=True, help="内容标识(加载键)")
    p_issue.add_argument("--content", default=None, help="直给内容(否则按需加载)")
    p_issue.add_argument("--ttl", type=float, default=None, help="本次有效期(秒)")

    p_verify = sub.add_parser("verify", help="验证令牌 + 返回临时加载内容")
    p_verify.add_argument("token", help="令牌")

    p_burn = sub.add_parser("burn", help="使用后立即烧毁")
    p_burn.add_argument("token", help="令牌")

    p_audit = sub.add_parser("audit", help="状态审计")

    p_demo = sub.add_parser(
        "demo",
        help="单进程完整生命周期演示(签发->验证->烧毁->审计)",
    )
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse(argv)
    srv = BurnServer()  # 默认 TTL 300; issue 子命令可用 --ttl 覆盖

    if args.cmd == "issue":
        r = srv.issue_token(args.key, ttl=args.ttl, content=args.content)
        print(f"[issue] ok={r['ok']}")
        print(f"  token     : {r['token']}")
        print(f"  key       : {r['key']}")
        print(f"  issued_at : {r['issued_at']:.3f}")
        print(f"  expires_at: {r['expires_at']:.3f}")
        return 0

    if args.cmd == "verify":
        v = srv.verify(args.token)
        if not v["ok"]:
            print(f"[verify] 拒绝: {v['reason']}")
            return 1
        print(f"[verify] 通过 token={v['token']} key={v['key']}")
        print(f"  content: {v['content']}")
        print("  (一次性: 再次 verify 将被拒绝, 记得 burn)")
        return 0

    if args.cmd == "burn":
        b = srv.burn(args.token)
        if not b["ok"]:
            print(f"[burn] 失败: {b['reason']}")
            return 1
        print(f"[burn] 已烧毁 token={b['token']} key={b['key']} "
              f"content_deleted={b['content_deleted']}")
        return 0

    if args.cmd == "audit":
        a = srv.audit()
        print(f"[audit] 活跃 {a['active_count']} / 已烧毁 {a['burned_count']}")
        for r in a["active"]:
            print(f"  [活跃] {r['token']} key={r['key']} uses={r['uses']} "
                  f"expires={r['expires_at']:.3f}")
        for r in a["burned"]:
            print(f"  [烧毁] {r['token']} key={r['key']} "
                  f"burned_at={r['burned_at']:.3f}")
        return 0

    if args.cmd == "demo":
        # 单进程完整生命周期: 签发 -> 验证(按需加载) -> 重复使用被拒 -> 烧毁 -> 审计
        r = srv.issue_token("demo.md", content="演示内容")
        print(f"[issue]  token={r['token']} key={r['key']} "
              f"expires_at={r['expires_at']:.3f}")
        v = srv.verify(r["token"])
        print(f"[verify] {'通过' if v['ok'] else '拒绝: ' + v['reason']} "
              f"content={v.get('content')!r}")
        v2 = srv.verify(r["token"])
        print(f"[verify] 第二次使用 -> "
              f"{'通过' if v2['ok'] else '拒绝: ' + v2['reason']} (一次性)")
        b = srv.burn(r["token"])
        print(f"[burn]   {'已烧毁' if b['ok'] else '失败: ' + b['reason']} "
              f"content_deleted={b.get('content_deleted')}")
        v3 = srv.verify(r["token"])
        print(f"[verify] 烧毁后使用 -> "
              f"{'通过' if v3['ok'] else '拒绝: ' + v3['reason']}")
        a = srv.audit()
        print(f"[audit]  活跃 {a['active_count']} / 已烧毁 {a['burned_count']}")
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
