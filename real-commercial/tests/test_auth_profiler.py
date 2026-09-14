#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M40C 测试: 授权机制分析框架(auth_profiler)。"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent  # real-commercial/
sys.path.insert(0, str(HERE))

from auth_profiler import profile  # noqa: E402


class TestAuthProfiler(unittest.TestCase):
    def test_rar_string_stripped(self):
        """WinRAR rar: 字符串剥离型。"""
        p = HERE / "rar"
        if not os.path.exists(p):
            self.skipTest("rar 不存在")
        r = profile(str(p))
        self.assertTrue(any("剥离" in t for t in r["auth_type"]))

    def test_sublime_sig_type(self):
        """Sublime Text: 签名验证型。"""
        p = HERE / "sublime_text"
        if not os.path.exists(p):
            self.skipTest("sublime_text 不存在")
        r = profile(str(p))
        self.assertTrue(any("签名验证" in t for t in r["auth_type"]))
        self.assertEqual(r["strength"], "高")

    def test_micro_binary(self):
        """极小机器码: 教学分类, 非商业。"""
        import tempfile
        tmp = tempfile.mktemp()
        with open(tmp, "wb") as f:
            f.write(b"\x7fELF" + b"\x00" * 200)
        r = profile(tmp)
        self.assertIn("教学/微型二进制", r["auth_type"][0])
        os.unlink(tmp)

    def test_rar_strings_zero(self):
        """WinRAR rar 授权字符串确实极少(真实观察)。"""
        p = HERE / "rar"
        if not os.path.exists(p):
            self.skipTest("rar 不存在")
        r = profile(str(p))
        self.assertEqual(r["string_counts"]["license_key"], 0)
        self.assertLess(r["string_counts"]["registration"], 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
