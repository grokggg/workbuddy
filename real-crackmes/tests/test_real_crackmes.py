#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M27 测试: 5 个 crackme 原始失败 + 破解成功。"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent  # real-crackmes/
sys.path.insert(0, str(HERE))

from process_all import patch_crackme, run  # noqa: E402

CRACKMES = {
    "cm01": "p", "cm02": "o", "cm04": "k", "cm05": "A", "cm09": "Z",
}


class TestRealCrackmes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = Path(HERE)
        cls.cracked = {}
        for name, pwd in CRACKMES.items():
            src = str(cls.dir / name)
            cracked = str(cls.dir / (name + "-cracked"))
            patch_crackme(src, cracked)
            cls.cracked[name] = cracked

    def test_orig_fails_wrong_pwd(self):
        for name in CRACKMES:
            _, rc = run([str(self.dir / name), "x"])
            self.assertNotEqual(rc, 0, f"{name} 错误密码应失败")

    def test_orig_ok_right_pwd(self):
        for name, pwd in CRACKMES.items():
            out, rc = run([str(self.dir / name), pwd])
            self.assertIn("OK", out)
            self.assertEqual(rc, 0, f"{name} 正确密码应成功")

    def test_cracked_ok_wrong_pwd(self):
        for name in CRACKMES:
            out, rc = run([self.cracked[name], "x"])
            self.assertIn("OK", out, f"{name} 破解版应输出 OK")
            self.assertEqual(rc, 0, f"{name} 破解版错误密码应成功")

    def test_cracked_ok_right_pwd(self):
        for name, pwd in CRACKMES.items():
            out, rc = run([self.cracked[name], pwd])
            self.assertIn("OK", out)
            self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
