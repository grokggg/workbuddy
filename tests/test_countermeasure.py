#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lib/countermeasure.py 单元测试"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "lib"))

from lib.countermeasure import COUNTERMEASURES, Countermeasure  # noqa: E402


class TestCountermeasure(unittest.TestCase):
    def test_knowledge_base(self):
        self.assertGreaterEqual(len(COUNTERMEASURES), 6)

    def test_no_protection(self):
        cm = Countermeasure({})
        r = cm.plan()
        self.assertTrue(r["ok"])
        self.assertEqual(r["categories"], [])

    def test_packer_detected(self):
        cm = Countermeasure({"packer": {"packed": True, "verdict": "加壳",
                                        "markers": ["UPX"]}})
        r = cm.plan()
        self.assertIn("加壳(UPX)", r["categories"])

    def test_vmp_detected(self):
        cm = Countermeasure({"packer": {"packed": True, "verdict": "加壳",
                                        "markers": ["VMProtect"]}})
        r = cm.plan()
        self.assertIn("加壳(VMProtect/Themida)", r["categories"])

    def test_antidebug_detected(self):
        cm = Countermeasure({"antidebug": {"detected": ["IsDebuggerPresent"]}})
        r = cm.plan()
        self.assertIn("反调试", r["categories"])

    def test_antivm_detected(self):
        cm = Countermeasure({"antivm": {"detected": ["CPUID 指令"]}})
        r = cm.plan()
        self.assertIn("反VM", r["categories"])

    def test_integrity_detected(self):
        cm = Countermeasure({"integrity": {"detected": ["字符串:checksum"]}})
        r = cm.plan()
        self.assertIn("完整性校验", r["categories"])

    def test_anti_repack_detected(self):
        cm = Countermeasure({"anti_repack": {"detected": ["app.asar"]}})
        r = cm.plan()
        self.assertIn("反重打包", r["categories"])

    def test_plan_has_options(self):
        cm = Countermeasure({"packer": {"packed": True, "verdict": "加壳",
                                        "markers": ["UPX"]}})
        r = cm.plan()
        self.assertGreaterEqual(len(r["plans"][0]["options"]), 1)

    def test_plan_text(self):
        cm = Countermeasure({"packer": {"packed": True, "verdict": "加壳",
                                        "markers": ["UPX"]}})
        txt = cm.plan_text()
        self.assertIn("应对计划", txt)
        self.assertIn("UPX", txt)


if __name__ == "__main__":
    unittest.main(verbosity=2)
