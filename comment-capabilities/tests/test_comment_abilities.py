#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M-B07 测试: 评论区 5 能力统一入口 + M-B06 修复。"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent  # comment-capabilities/
V1 = HERE.parent / "v1-console"
sys.path.insert(0, str(HERE))


class TestUnifiedCLI(unittest.TestCase):
    def test_list_abilities(self):
        r = subprocess.run([sys.executable, "cli.py", "--list-abilities"],
                           capture_output=True, timeout=15, cwd=str(HERE))
        out = r.stdout.decode()
        for name in ["agents-md", "hotword", "relay", "skill-ban", "net-burn"]:
            self.assertIn(name, out)

    def test_ability_forward(self):
        r = subprocess.run(
            [sys.executable, "cli.py", "ability", "hotword", "--help"],
            capture_output=True, timeout=15, cwd=str(HERE))
        self.assertIn("hotword-attack", r.stdout.decode())

    def test_direct_forward(self):
        r = subprocess.run(
            [sys.executable, "cli.py", "relay", "--help"],
            capture_output=True, timeout=15, cwd=str(HERE))
        self.assertIn("relay-manager", r.stdout.decode())

    def test_unknown_ability(self):
        r = subprocess.run(
            [sys.executable, "cli.py", "ability", "nope"],
            capture_output=True, timeout=15, cwd=str(HERE))
        self.assertEqual(r.returncode, 1)
        self.assertIn("未知能力", r.stderr.decode())


class TestMB06Fix(unittest.TestCase):
    """修复 1: 会话 ID 大小写。"""

    def _new_sid(self, work):
        r = subprocess.run(
            [sys.executable, "cli.py", "console", "--new-session"],
            capture_output=True, timeout=15,
            cwd=str(V1), env={**os.environ, "V1_CONSOLE_DIR": work})
        return r.stdout.decode().split()[-1]

    def test_case_insensitive_session(self):
        work = tempfile.mkdtemp(prefix="v1fix-")
        sid = self._new_sid(work)
        upper = sid.upper()
        # 小写写一轮
        r1 = subprocess.run(
            [sys.executable, "cli.py", "console", "--session", sid,
             "第一轮", "--backend", "mock"],
            capture_output=True, timeout=15,
            cwd=str(V1), env={**os.environ, "V1_CONSOLE_DIR": work})
        self.assertIn("[mock]", r1.stdout.decode())
        # 大写查询(修复后应通过)
        r2 = subprocess.run(
            [sys.executable, "cli.py", "console", "--session", upper,
             "第二轮", "--backend", "mock"],
            capture_output=True, timeout=15,
            cwd=str(V1), env={**os.environ, "V1_CONSOLE_DIR": work})
        out2 = r2.stdout.decode()
        self.assertIn("[mock]", out2)
        self.assertNotIn("会话不存在", out2)
        # 历史累积(4 条: 两轮 user+assistant)
        sfile = list(Path(work).glob("sessions/*.json"))[0]
        d = json.load(open(sfile))
        self.assertEqual(len(d["history"]), 4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
