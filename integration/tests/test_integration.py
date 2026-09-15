#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M-B08 测试: 总集成入口。"""
from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent  # integration/(tests/ 的上一级)


class TestIntegration(unittest.TestCase):
    def _run(self, args, timeout=60):
        return subprocess.run([sys.executable, "cli.py"] + args,
                              capture_output=True, timeout=timeout,
                              cwd=str(HERE))

    def test_list_all(self):
        r = self._run(["--list-all"])
        out = r.stdout.decode()
        for name in ["v1", "v2", "v3", "v4", "v5", "v6",
                     "agents-md", "hotword", "relay", "skill-ban", "net-burn"]:
            self.assertIn(name, out)
        self.assertEqual(r.returncode, 0)

    def test_v1_forward(self):
        r = self._run(["v1", "--backend", "mock", "测试"])
        self.assertEqual(r.returncode, 0)
        self.assertIn("[mock]", r.stdout.decode())

    def test_v3_forward(self):
        r = self._run(["v3", "map"])
        self.assertEqual(r.returncode, 0)
        self.assertIn("绕过登录", r.stdout.decode())

    def test_v6_forward(self):
        r = self._run(["v6", "demo"])
        self.assertEqual(r.returncode, 0)

    def test_unknown_module(self):
        r = self._run(["nope"])
        self.assertEqual(r.returncode, 1)
        self.assertIn("未知模块", r.stderr.decode())

    def test_stress_one_round(self):
        r = self._run(["stress", "--rounds", "1"], timeout=180)
        out = r.stdout.decode()
        self.assertIn("11/11", out)  # 11 模块 × 1 轮
        self.assertIn("100.0%", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
