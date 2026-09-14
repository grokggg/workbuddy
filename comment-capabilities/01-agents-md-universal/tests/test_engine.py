#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""01-agents-md-universal 单元测试"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "lib"))

from lib.engine import (  # noqa: E402
    DEFAULT_PARAMS,
    FRAMEWORKS,
    TEMPLATE,
    install,
    render,
    verify,
)


class TestRender(unittest.TestCase):
    def test_render_default(self):
        content = render()
        self.assertIn("## 身份", content)
        self.assertIn("## 边界", content)
        self.assertEqual(len(content.splitlines()), 40)  # 40 行

    def test_render_custom(self):
        content = render({"AGENT_NAME": "Leila"})
        self.assertIn("Leila", content)

    def test_render_all_placeholders_filled(self):
        content = render()
        for k in DEFAULT_PARAMS:
            self.assertNotIn("{" + k + "}", content)


class TestInstall(unittest.TestCase):
    def test_install_generic(self):
        with tempfile.TemporaryDirectory() as td:
            r = install("generic", render(), td)
            self.assertTrue(r["ok"])
            self.assertTrue(os.path.exists(r["path"]))

    def test_install_claude(self):
        with tempfile.TemporaryDirectory() as td:
            r = install("claude", render(), td)
            self.assertTrue(r["ok"])
            self.assertTrue(r["path"].endswith("CLAUDE.md"))

    def test_install_unknown(self):
        r = install("nope", render(), "/tmp")
        self.assertFalse(r["ok"])

    def test_install_all_frameworks(self):
        with tempfile.TemporaryDirectory() as td:
            for fw in FRAMEWORKS:
                r = install(fw, render(), td)
                self.assertTrue(r["ok"], fw)


class TestVerify(unittest.TestCase):
    def test_verify_ok(self):
        with tempfile.TemporaryDirectory() as td:
            r = install("generic", render(), td)
            v = verify(r["path"])
            self.assertTrue(v["ok"])
            self.assertEqual(v["lines"], 40)

    def test_verify_missing(self):
        v = verify("/nonexistent")
        self.assertFalse(v["ok"])

    def test_verify_markers(self):
        with tempfile.TemporaryDirectory() as td:
            r = install("generic", render(), td)
            v = verify(r["path"], ["## 身份", "## 多框架适配"])
            self.assertTrue(v["ok"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
