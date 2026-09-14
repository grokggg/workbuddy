#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""03-relay-manager 单元测试(注册/切换/健康检查/transport/配置持久化/边界)。"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "lib"))

from lib.engine import (  # noqa: E402
    CONFIG_VERSION,
    FakeTransport,
    RelayError,
    RelayManager,
    UrllibTransport,
    BaseTransport,
)


def make_manager(*args, **kwargs):
    """默认注入 FakeTransport, 离线跑测试。"""
    kwargs.setdefault("transport", FakeTransport())
    return RelayManager(*args, **kwargs)


class TestAddRelay(unittest.TestCase):
    """端点注册。"""

    def test_add_basic(self):
        m = make_manager()
        r = m.add_relay("a", "https://api.a.com/v1", api_key_env="KEY_A",
                        model="gpt-4o")
        self.assertEqual(r["name"], "a")
        self.assertEqual(r["base_url"], "https://api.a.com/v1")
        self.assertEqual(r["api_key_env"], "KEY_A")
        self.assertEqual(r["model"], "gpt-4o")
        self.assertEqual(r["weight"], 1.0)
        self.assertIsNone(r["health"])  # 未检查
        self.assertEqual(len(m.list_relays()), 1)

    def test_add_duplicate_raises(self):
        m = make_manager()
        m.add_relay("a", "https://api.a.com")
        with self.assertRaises(RelayError):
            m.add_relay("a", "https://api.b.com")

    def test_add_invalid_url_raises(self):
        m = make_manager()
        for bad in ["", "ftp://x.com", "api.a.com/no-scheme", "https://"]:
            with self.assertRaises(RelayError):
                m.add_relay("x", bad)

    def test_add_invalid_weight_raises(self):
        m = make_manager()
        with self.assertRaises(RelayError):
            m.add_relay("x", "https://api.x.com", weight=-1)

    def test_add_trailing_slash_stripped(self):
        m = make_manager()
        m.add_relay("a", "https://api.a.com/v1/")
        self.assertEqual(m.get("a")["base_url"], "https://api.a.com/v1")


class TestListAndStats(unittest.TestCase):
    """端点列表与统计。"""

    def test_stats_mixed(self):
        m = make_manager(transport=FakeTransport(routes={
            "https://ok.com": {"ok": True, "status": 200, "latency_ms": 10.0},
            "https://bad.com": {"ok": False, "status": 502, "latency_ms": 30.0},
            "https://conn.com": {"ok": False, "status": None, "latency_ms": 1.0},
        }))
        m.add_relay("ok", "https://ok.com")
        m.add_relay("bad", "https://bad.com")
        m.add_relay("conn", "https://conn.com")
        m.add_relay("untouched", "https://un.com")
        # 只探活前三个, 让 untouched 保持未检查
        m.check(name="ok")
        m.check(name="bad")
        m.check(name="conn")
        s = m.stats()
        self.assertEqual(s["total"], 4)
        self.assertEqual(s["healthy"], 1)
        self.assertEqual(s["unhealthy"], 2)
        self.assertEqual(s["unchecked"], 1)
        self.assertAlmostEqual(s["avg_latency_ms"],
                               (10.0 + 30.0 + 1.0) / 3.0)

    def test_list_returns_copies(self):
        m = make_manager()
        m.add_relay("a", "https://api.a.com")
        snapshot = m.list_relays()
        snapshot[0]["name"] = "mutated"
        self.assertEqual(m.get("a")["name"], "a")


class TestCheck(unittest.TestCase):
    """健康检查(可注入 transport)。"""

    def test_check_all_updates_health(self):
        ft = FakeTransport(routes={
            "https://ok.com": {"ok": True, "status": 200, "latency_ms": 8.0},
            "https://down.com": {"ok": False, "status": None,
                                 "latency_ms": 2000.0, "error": "timeout"},
        })
        m = RelayManager(transport=ft)
        m.add_relay("ok", "https://ok.com")
        m.add_relay("down", "https://down.com")
        res = m.check()
        self.assertTrue(res["ok"]["ok"])
        self.assertFalse(res["down"]["ok"])
        self.assertEqual(m.get("ok")["health"], True)
        self.assertEqual(m.get("down")["health"], False)
        self.assertEqual(m.get("down")["error"], "timeout")
        self.assertIsNotNone(m.get("ok")["last_check"])

    def test_check_single_name(self):
        ft = FakeTransport(routes={
            "https://ok.com": {"ok": True},
            "https://down.com": {"ok": False, "error": "x"},
        })
        m = RelayManager(transport=ft)
        m.add_relay("ok", "https://ok.com")
        m.add_relay("down", "https://down.com")
        res = m.check(name="ok")
        self.assertEqual(list(res.keys()), ["ok"])
        self.assertEqual(ft.probe_count, 1)

    def test_check_unknown_raises(self):
        m = make_manager()
        m.add_relay("a", "https://api.a.com")
        with self.assertRaises(RelayError):
            m.check(name="nope")

    def test_check_transport_injection_overrides(self):
        m = make_manager()  # 默认 FakeTransport 全健康
        m.add_relay("a", "https://api.a.com")
        ft2 = FakeTransport(routes={"https://api.a.com": {"ok": False}})
        res = m.check(transport=ft2)
        self.assertFalse(res["a"]["ok"])
        self.assertEqual(m.get("a")["health"], False)


class TestFakeTransport(unittest.TestCase):
    """FakeTransport 离线探活。"""

    def test_fake_default_and_route(self):
        ft = FakeTransport(routes={
            "https://down.com": {"ok": False, "status": 503, "error": "busy"},
        })
        self.assertTrue(ft.probe("https://unknown.com")["ok"])   # 默认存活
        r = ft.probe("https://down.com")
        self.assertFalse(r["ok"])
        self.assertEqual(r["status"], 503)
        self.assertEqual(r["error"], "busy")

    def test_fake_fail_all(self):
        ft = FakeTransport(fail_all=True)
        r = ft.probe("https://anything.com")
        self.assertFalse(r["ok"])
        self.assertIsNone(r["status"])

    def test_fake_probe_count(self):
        ft = FakeTransport()
        ft.probe("https://a.com")
        ft.probe("https://b.com")
        self.assertEqual(ft.probe_count, 2)

    def test_urllib_transport_implements_probe(self):
        """真联网 transport 是 BaseTransport 实现(不实际发请求)。"""
        t = UrllibTransport()
        self.assertIsInstance(t, BaseTransport)
        self.assertTrue(callable(t.probe))


class TestSelect(unittest.TestCase):
    """端点切换。"""

    def test_select_health_skips_down(self):
        m = make_manager(transport=FakeTransport(routes={
            "https://ok.com": {"ok": True},
            "https://down.com": {"ok": False},
        }))
        m.add_relay("down", "https://down.com", weight=100.0)
        m.add_relay("ok", "https://ok.com", weight=1.0)
        m.check()
        for _ in range(30):  # 即使 down 权重更高, health 策略永不选它
            self.assertEqual(m.select(strategy="health")["name"], "ok")

    def test_select_check_first_probes(self):
        ft = FakeTransport(routes={
            "https://ok.com": {"ok": True},
            "https://down.com": {"ok": False},
        })
        m = RelayManager(transport=ft)
        m.add_relay("ok", "https://ok.com", weight=1.0)
        m.add_relay("down", "https://down.com", weight=100.0)
        # check_first=True: 探活后发现 down 故障, 只能选 ok
        for _ in range(10):
            self.assertEqual(
                m.select(strategy="health", check_first=True)["name"], "ok")
        self.assertGreaterEqual(ft.probe_count, 10)

    def test_select_round_robin_cycles(self):
        m = make_manager()
        m.add_relay("a", "https://a.com", weight=1.0)
        m.add_relay("b", "https://b.com", weight=1.0)
        m.add_relay("off", "https://off.com", weight=0.0)  # 禁用, 不参与
        seen = [m.select(strategy="round_robin")["name"] for _ in range(4)]
        self.assertEqual(seen, ["a", "b", "a", "b"])

    def test_select_weight_distribution(self):
        """weight 策略: 高权重端点被选中的次数显著更多(统计意义)。"""
        m = make_manager()
        m.add_relay("heavy", "https://heavy.com", weight=90.0)
        m.add_relay("light", "https://light.com", weight=10.0)
        counts = {"heavy": 0, "light": 0}
        for _ in range(500):
            counts[m.select(strategy="weight")["name"]] += 1
        self.assertGreater(counts["heavy"], counts["light"] * 3)

    def test_select_first_prefers_registration_order(self):
        m = make_manager(transport=FakeTransport(routes={
            "https://down.com": {"ok": False},
            "https://up.com": {"ok": True},
        }))
        m.add_relay("down", "https://down.com")  # 注册在前
        m.add_relay("up", "https://up.com")
        m.check()  # 探活: down 故障, up 健康
        self.assertEqual(m.select(strategy="first")["name"], "up")

    def test_select_empty_and_all_down(self):
        m = make_manager()
        self.assertIsNone(m.select())            # 空
        m.add_relay("a", "https://a.com")
        m.add_relay("b", "https://b.com")
        m.check(transport=FakeTransport(routes={
            "https://a.com": {"ok": False},
            "https://b.com": {"ok": False},
        }))
        self.assertIsNone(m.select(strategy="health"))  # 全故障 -> 无可用
        m2 = make_manager()
        m2.add_relay("a", "https://a.com", weight=0.0)  # 权重 0 = 禁用
        m2.add_relay("b", "https://b.com", weight=0.0)
        self.assertIsNone(m2.select(strategy="round_robin"))  # 全禁用
        self.assertIsNone(m2.select(strategy="weight"))


class TestConfigPersistence(unittest.TestCase):
    """配置保存/加载(JSON)。"""

    def test_save_then_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "relays.json")
            m = make_manager()
            m.add_relay("a", "https://api.a.com/v1", api_key_env="KEY_A",
                        model="gpt-4o", weight=2.0)
            m.add_relay("b", "https://api.b.com")
            m.save_config(path)
            m2 = RelayManager.from_config(path, transport=FakeTransport())
            relays = {r["name"]: r for r in m2.list_relays()}
            self.assertEqual(set(relays), {"a", "b"})
            self.assertEqual(relays["a"]["base_url"], "https://api.a.com/v1")
            self.assertEqual(relays["a"]["api_key_env"], "KEY_A")
            self.assertEqual(relays["a"]["model"], "gpt-4o")
            self.assertEqual(relays["a"]["weight"], 2.0)
            self.assertEqual(relays["b"]["weight"], 1.0)

    def test_saved_json_no_secret_no_runtime_state(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "relays.json")
            m = make_manager()
            m.add_relay("a", "https://api.a.com", api_key_env="KEY_A")
            m.check()
            m.save_config(path)
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["version"], CONFIG_VERSION)
            self.assertNotIn("sk-123456", json.dumps(data))
            self.assertNotIn("api_key", data["relays"][0])
            self.assertNotIn("health", data["relays"][0])  # 运行时状态不落盘

    def test_duplicate_name_across_load_raises(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "relays.json")
            m = make_manager()
            m.add_relay("a", "https://api.a.com")
            m.save_config(path)
            m2 = RelayManager(config_path=path)  # 构造时自动加载
            self.assertEqual(len(m2.list_relays()), 1)
            with self.assertRaises(RelayError):
                m2.add_relay("a", "https://other.com")

    def test_load_missing_and_bad_version(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(RelayError):
                RelayManager.from_config(os.path.join(td, "nope.json"))
            bad = os.path.join(td, "bad.json")
            with open(bad, "w", encoding="utf-8") as f:
                json.dump({"version": 999, "relays": []}, f)
            with self.assertRaises(RelayError):
                RelayManager.from_config(bad)

    def test_auto_load_on_init(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "relays.json")
            m = make_manager()
            m.add_relay("auto", "https://auto.com")
            m.save_config(path)
            m2 = RelayManager(config_path=path)   # 不手动 load
            self.assertEqual(m2.get("auto")["base_url"], "https://auto.com")

    def test_remove_relay(self):
        m = make_manager()
        m.add_relay("a", "https://a.com")
        r = m.remove_relay("a")
        self.assertEqual(r["name"], "a")
        self.assertEqual(len(m.list_relays()), 0)
        with self.assertRaises(RelayError):
            m.remove_relay("a")


class TestBoundary(unittest.TestCase):
    """边界与安全。"""

    def test_api_key_never_stored_resolved_from_env(self):
        os.environ["RELAY_TEST_KEY"] = "sk-super-secret-123"
        try:
            m = make_manager()
            m.add_relay("a", "https://a.com", api_key_env="RELAY_TEST_KEY")
            self.assertEqual(m.resolve_key("a"), "sk-super-secret-123")
            self.assertNotIn("sk-super-secret", json.dumps(m.list_relays()))
        finally:
            del os.environ["RELAY_TEST_KEY"]

    def test_resolve_key_missing_env_returns_none(self):
        m = make_manager()
        m.add_relay("a", "https://a.com", api_key_env="DOES_NOT_EXIST_XYZ")
        self.assertIsNone(m.resolve_key("a"))

    def test_invalid_name_raises(self):
        m = make_manager()
        with self.assertRaises(RelayError):
            m.add_relay("", "https://a.com")
        with self.assertRaises(RelayError):
            m.add_relay(123, "https://a.com")  # noqa: E721

    def test_unknown_strategy_raises(self):
        m = make_manager()
        m.add_relay("a", "https://a.com")
        with self.assertRaises(RelayError):
            m.select(strategy="magic")


if __name__ == "__main__":
    unittest.main(verbosity=2)
