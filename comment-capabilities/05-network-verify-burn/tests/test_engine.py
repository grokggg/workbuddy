#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""05-network-verify-burn 单元测试(签发/验证/烧毁/过期/重复使用拒绝/审计)。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "lib"))

from lib.engine import ACTIVE, BURNED, BurnError, BurnServer  # noqa: E402


class _FakeClock:
    """可手动拨动的假时钟。"""

    def __init__(self, t: float = 1000.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


class _FakeStore(dict):
    """注入存储层(验证可注入性): 记录每次对顶层键的写入。"""

    def __init__(self) -> None:
        super().__init__({"tokens": {}, "contents": {}})
        self.writes = 0

    def __setitem__(self, k, v):
        self.writes += 1
        return super().__setitem__(k, v)


class TestIssueToken(unittest.TestCase):
    def test_issue_token_returns_token_and_expiry(self):
        s = BurnServer()
        r = s.issue_token("k1", content="payload-1")
        self.assertTrue(r["ok"])
        self.assertTrue(r["token"])
        self.assertEqual(r["key"], "k1")
        self.assertGreater(r["expires_at"], r["issued_at"])

    def test_issue_token_default_ttl_applied(self):
        clock = _FakeClock(5000.0)
        s = BurnServer(now_fn=clock, ttl=60.0)
        r = s.issue_token("k1", content="x")
        self.assertAlmostEqual(r["expires_at"] - r["issued_at"], 60.0)

    def test_issue_token_custom_ttl(self):
        s = BurnServer(now_fn=_FakeClock(0.0))
        r = s.issue_token("k1", ttl=7.0, content="x")
        self.assertAlmostEqual(r["expires_at"], 7.0)

    def test_issue_token_rejects_empty_key(self):
        s = BurnServer()
        with self.assertRaises(BurnError):
            s.issue_token("", content="x")
        with self.assertRaises(BurnError):
            s.issue_token(None, content="x")

    def test_issue_token_no_content_defers_load(self):
        calls = []
        s = BurnServer(loader=lambda key: calls.append(key) or "L:" + key)
        s.issue_token("k1")  # 未提供内容 -> 不加载, 也不入缓存
        self.assertEqual(calls, [])
        self.assertNotIn("k1", s._contents())
        v = s.verify(s.active_tokens()[0])
        self.assertTrue(v["ok"])
        self.assertEqual(calls, ["k1"])  # 按需加载恰好一次
        self.assertEqual(v["content"], "L:k1")


class TestVerify(unittest.TestCase):
    def test_verify_success_with_content(self):
        s = BurnServer()
        r = s.issue_token("k1", content="payload-1")
        v = s.verify(r["token"])
        self.assertTrue(v["ok"])
        self.assertEqual(v["content"], "payload-1")
        self.assertEqual(v["key"], "k1")

    def test_verify_unknown_token_rejected(self):
        s = BurnServer()
        v = s.verify("no-such-token")
        self.assertFalse(v["ok"])
        self.assertEqual(v["reason"], "not_found")

    def test_verify_after_burn_rejected(self):
        s = BurnServer()
        t = s.issue_token("k1", content="x")["token"]
        self.assertTrue(s.burn(t)["ok"])
        v = s.verify(t)
        self.assertFalse(v["ok"])
        self.assertEqual(v["reason"], "burned")

    def test_verify_expired_token_rejected(self):
        clock = _FakeClock(1000.0)
        s = BurnServer(now_fn=clock)
        t = s.issue_token("k1", ttl=10.0, content="x")["token"]
        clock.advance(10.1)  # 超时
        v = s.verify(t)
        self.assertFalse(v["ok"])
        self.assertEqual(v["reason"], "expired")

    def test_verify_expired_then_unknown_after_burn(self):
        clock = _FakeClock(1000.0)
        s = BurnServer(now_fn=clock)
        t = s.issue_token("k1", ttl=10.0, content="x")["token"]
        clock.advance(11.0)
        self.assertEqual(s.verify(t)["reason"], "expired")
        s.burn(t)  # 过期后仍可烧毁清理
        self.assertEqual(s.verify(t)["reason"], "burned")

    def test_verify_reuse_rejected(self):
        s = BurnServer()
        t = s.issue_token("k1", content="x")["token"]
        self.assertTrue(s.verify(t)["ok"])
        # 一次性: 第二次使用被拒绝
        v = s.verify(t)
        self.assertFalse(v["ok"])
        self.assertEqual(v["reason"], "already_used")

    def test_verify_load_failure_reported(self):
        def boom(key):
            raise RuntimeError("backend down")

        s = BurnServer(loader=boom)
        t = s.issue_token("k1")["token"]
        v = s.verify(t)
        self.assertFalse(v["ok"])
        self.assertEqual(v["reason"], "load_failed")

    def test_verify_without_loader_no_content(self):
        s = BurnServer()  # 无 loader, 且签发时未提供内容
        t = s.issue_token("k1")["token"]
        v = s.verify(t)
        self.assertFalse(v["ok"])
        self.assertEqual(v["reason"], "no_content")


class TestBurn(unittest.TestCase):
    def test_burn_invalidates_token_and_deletes_content(self):
        s = BurnServer()
        t = s.issue_token("k1", content="payload-1")["token"]
        b = s.burn(t)
        self.assertTrue(b["ok"])
        self.assertTrue(b["content_deleted"])
        self.assertNotIn("k1", s._contents())  # 用完即删
        # 烧毁后验证被拒 + 审计进入已烧毁
        self.assertEqual(s.verify(t)["reason"], "burned")
        self.assertEqual(s.audit()["burned_count"], 1)

    def test_burn_unknown_token(self):
        s = BurnServer()
        b = s.burn("no-such-token")
        self.assertFalse(b["ok"])
        self.assertEqual(b["reason"], "not_found")

    def test_burn_already_burned(self):
        s = BurnServer()
        t = s.issue_token("k1", content="x")["token"]
        self.assertTrue(s.burn(t)["ok"])
        b = s.burn(t)  # 重复烧毁
        self.assertFalse(b["ok"])
        self.assertEqual(b["reason"], "already_burned")


class TestAudit(unittest.TestCase):
    def test_audit_lists_active_and_burned(self):
        s = BurnServer()
        t1 = s.issue_token("k1", content="x")["token"]
        t2 = s.issue_token("k2", content="y")["token"]
        s.burn(t2)
        a = s.audit()
        self.assertEqual(a["active_count"], 1)
        self.assertEqual(a["burned_count"], 1)
        self.assertEqual([x["key"] for x in a["active"]], ["k1"])
        self.assertEqual([x["key"] for x in a["burned"]], ["k2"])
        self.assertEqual(s.active_tokens(), [t1])
        self.assertEqual(s.burned_tokens(), [t2])

    def test_audit_after_reuse_still_active_until_burn(self):
        s = BurnServer()
        t = s.issue_token("k1", content="x")["token"]
        s.verify(t)  # 已使用, 但尚未烧毁
        a = s.audit()
        self.assertEqual(a["active_count"], 1)
        self.assertEqual(a["active"][0]["uses"], 1)


class TestStorageInjection(unittest.TestCase):
    def test_injectable_store_layer(self):
        store = _FakeStore()
        s = BurnServer(store=store, loader=lambda k: "L:" + k)
        self.assertIs(s._store, store)  # 注入的存储层被直接使用
        r = s.issue_token("k1")  # 不传内容 -> 验证时按需加载
        self.assertEqual(s.verify(r["token"])["content"], "L:k1")
        self.assertIn("k1", store["contents"])  # 加载结果写入注入存储
        self.assertEqual(s.burn(r["token"])["ok"], True)
        self.assertEqual(store["tokens"][r["token"]]["status"], BURNED)
        self.assertNotIn("k1", store["contents"])  # 用完即删, 落在外层存储


if __name__ == "__main__":
    unittest.main(verbosity=2)
