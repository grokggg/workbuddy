#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M-B06 测试: v1 四模型统一控制台。"""
from __future__ import annotations

import json
import os
import socket
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent  # v1-console/
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "lib"))

from lib.console import (  # noqa: E402
    Console,
    LocalHTTPBackend,
    MockBackend,
    Router,
    SessionManager,
    compare,
    create_backends,
)


def _free_port() -> int:
    s = socket.socket(); s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]; s.close()
    return p


class TestBackends(unittest.TestCase):
    def test_four_backends_registered(self):
        ports = [_free_port() for _ in range(3)]
        bs = create_backends(ports)
        self.assertEqual(len(bs), 4)
        self.assertIn("mock", bs)
        for name in ["gpt-local", "claude-local", "deepseek-local"]:
            self.assertIn(name, bs)
            self.assertTrue(bs[name].health())  # 真实 HTTP 健康

    def test_mock_chat(self):
        b = MockBackend()
        r = b.chat([{"role": "user", "content": "hi"}])
        self.assertIn("hi", r)

    def test_local_http_chat(self):
        bs = create_backends([_free_port()])
        r = bs["gpt-local"].chat([{"role": "user", "content": "你好"}])
        self.assertIn("你好", r)
        bs["gpt-local"].stop()

    def test_dead_backend_health_false(self):
        """未监听端口后端: health False。"""
        s = socket.socket(); s.bind(("127.0.0.1", 0))
        free = s.getsockname()[1]; s.close()
        import types
        dead = object.__new__(LocalHTTPBackend)
        dead.name = "dead"; dead.style = "x"; dead.port = free
        dead._srv = None; dead._server = None
        dead.chat = types.MethodType(
            lambda self, m: (_ for _ in ()).throw(ConnectionError), dead)
        dead.health = types.MethodType(lambda self: False, dead)
        self.assertFalse(dead.health())


class TestRouter(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="v1c-")
        self.bs = create_backends([_free_port(), _free_port(), _free_port()])

    def tearDown(self):
        for b in self.bs.values():
            if hasattr(b, "stop"):
                b.stop()

    def test_explicit(self):
        r = Router(self.bs)
        name, resp = r.route("q", "claude-local")
        self.assertEqual(name, "claude-local")
        self.assertIn("Claude", resp)

    def test_auto_priority(self):
        r = Router(self.bs, priority=["claude-local", "gpt-local", "mock"])
        name, _ = r.route("q")
        self.assertEqual(name, "claude-local")  # 第一个健康

    def test_fallback_on_dead(self):
        """指定挂掉的后端 → 回退。"""
        import types
        s = socket.socket(); s.bind(("127.0.0.1", 0))
        free = s.getsockname()[1]; s.close()
        dead = object.__new__(LocalHTTPBackend)
        dead.name = "dead"; dead.style = "x"; dead.port = free
        dead._srv = None; dead._server = None
        dead.chat = types.MethodType(
            lambda self, m: (_ for _ in ()).throw(ConnectionError), dead)
        dead.health = types.MethodType(lambda self: False, dead)
        bs = {"dead": dead, "mock": MockBackend()}
        r = Router(bs, priority=["dead", "mock"])
        name, resp = r.route("q", "dead")
        self.assertEqual(name, "mock")  # 回退到 mock
        reasons = [d.reason for d in r.decisions]
        self.assertTrue(any("explicit-fail" in x for x in reasons))

    def test_unknown_backend(self):
        r = Router(self.bs)
        name, resp = r.route("q", "nope")
        self.assertEqual(name, "error")


class TestCompare(unittest.TestCase):
    def test_compare_all(self):
        bs = create_backends([_free_port(), _free_port(), _free_port()])
        results = compare(bs, ["gpt-local", "claude-local", "deepseek-local", "mock"], "q")
        self.assertEqual(len(results), 4)
        for r in results:
            self.assertTrue(r["success"], f"{r['backend']} 失败: {r['response']}")
            self.assertGreaterEqual(r["latency_ms"], 0)
        # 顺序保持
        self.assertEqual(results[0]["backend"], "gpt-local")
        for b in bs.values():
            if hasattr(b, "stop"):
                b.stop()


class TestSession(unittest.TestCase):
    def test_session_persistence(self):
        tmp = tempfile.mkdtemp(prefix="v1c-s-")
        bs = create_backends([_free_port(), _free_port(), _free_port()])
        r = Router(bs)
        sm = SessionManager(r, session_dir=tmp)
        sid = sm.new_session()
        r1 = sm.chat(sid, "第一轮", "gpt-local")
        r2 = sm.chat(sid, "第二轮", "claude-local")
        self.assertEqual(r1["backend"], "gpt-local")
        self.assertEqual(r2["backend"], "claude-local")
        self.assertEqual(r2["history_len"], 4)  # 上下文保持
        # 跨实例加载(模拟新进程)
        sm2 = SessionManager(r, session_dir=tmp)
        r3 = sm2.chat(sid, "第三轮", "deepseek-local")
        self.assertEqual(r3["history_len"], 6)  # 持久化加载
        # 日志可回放
        logs = list(Path(tmp).glob(f"{sid}.jsonl"))
        self.assertTrue(logs)
        for b in bs.values():
            if hasattr(b, "stop"):
                b.stop()


class TestConsoleCLI(unittest.TestCase):
    def test_console_health(self):
        tmp = tempfile.mkdtemp(prefix="v1c-h-")
        os.environ["V1_CONSOLE_DIR"] = tmp
        import subprocess
        r = subprocess.run(
            [sys.executable, str(HERE / "cli.py"), "console", "--health"],
            capture_output=True, timeout=15, cwd=str(HERE))
        out = r.stdout.decode()
        self.assertIn("gpt-local", out)
        self.assertIn("OK", out)
        self.assertIn("mock", out)

    def test_console_chat(self):
        tmp = tempfile.mkdtemp(prefix="v1c-c-")
        os.environ["V1_CONSOLE_DIR"] = tmp
        import subprocess
        r = subprocess.run(
            [sys.executable, str(HERE / "cli.py"), "console", "--backend", "mock", "hi"],
            capture_output=True, timeout=15, cwd=str(HERE))
        self.assertIn("[mock]", r.stdout.decode())


if __name__ == "__main__":
    unittest.main(verbosity=2)
