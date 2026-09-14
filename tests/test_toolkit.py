#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""toolkit.py 单元测试"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent  # up-tools 根
sys.path.insert(0, str(HERE))

import toolkit as T  # noqa: E402


class TestLog(unittest.TestCase):
    def test_log_creates_file(self):
        with tempfile.TemporaryDirectory() as td:
            T.LOG_DIR = Path(td) / "logs"
            T.log("test msg")
            files = list(T.LOG_DIR.glob("*.log"))
            self.assertEqual(len(files), 1)
            self.assertIn("test msg", files[0].read_text())


class TestConfig(unittest.TestCase):
    def test_config_set_get(self):
        with tempfile.TemporaryDirectory() as td:
            T.CONFIG_PATH = Path(td) / "config.json"
            T.config_set("key", "value")
            self.assertEqual(T.config_get("key"), "value")
            self.assertEqual(T.config_get("missing", "default"), "default")

    def test_config_load_empty(self):
        with tempfile.TemporaryDirectory() as td:
            T.CONFIG_PATH = Path(td) / "config.json"
            self.assertEqual(T.load_config(), {})


class TestToolsRegistry(unittest.TestCase):
    def test_all_tools_present(self):
        self.assertIn("v2-codex-skill-injection", T.TOOLS)
        self.assertIn("v3-five-step-laundering", T.TOOLS)
        self.assertIn("v4-jailbreak-leak", T.TOOLS)
        self.assertIn("v5-jump-patch", T.TOOLS)
        self.assertIn("v6-skill-router", T.TOOLS)
        self.assertIn("comment-capabilities", T.TOOLS)

    def test_comment_subs(self):
        subs = T.TOOLS["comment-capabilities"]["subs"]
        self.assertEqual(len(subs), 5)


class TestRun(unittest.TestCase):
    def test_run_tool_ok(self):
        r = T._run_tool("/tmp", ["python3", "-c", "print('ok')"])
        self.assertTrue(r["ok"])
        self.assertIn("ok", r["stdout"])

    def test_run_tool_missing(self):
        r = T._run_tool("/tmp", ["/nonexistent"])
        self.assertFalse(r["ok"])


class TestCLI(unittest.TestCase):
    def test_list(self):
        self.assertEqual(T.cmd_list(), 0)

    def test_version(self):
        self.assertEqual(T.main(["--version"]), 0)

    def test_unknown_cmd(self):
        # 无子命令 -> help, 返回 0
        self.assertEqual(T.main([]), 0)

    def test_unknown_tool(self):
        self.assertEqual(T.cmd_run("nope", []), 1)

    def test_comment_unknown(self):
        self.assertEqual(T.cmd_comment("nope"), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
