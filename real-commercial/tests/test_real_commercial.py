#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M40 测试: 真实商业软件保护机制识别(防御视角)。"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent  # real-commercial/
sys.path.insert(0, str(HERE.parent / "lib"))

from recon_v2 import ReconV2  # noqa: E402


class TestRealCommercial(unittest.TestCase):
    def test_rar_recon(self):
        p = HERE / "rar"
        if not os.path.exists(p):
            self.skipTest("rar 不存在")
        r = ReconV2(str(p)).report()
        self.assertEqual(r.get("format", {}).get("file_type"), "ELF")

    def test_rar_antivm(self):
        p = HERE / "rar"
        if not os.path.exists(p):
            self.skipTest("rar 不存在")
        r = ReconV2(str(p)).report()
        avm = r.get("antivm") or {}
        detected = avm.get("detected") if isinstance(avm, dict) else []
        self.assertIn("CPUID 指令", detected)

    def test_sublime_recon(self):
        p = HERE / "sublime_text"
        if not os.path.exists(p):
            self.skipTest("sublime_text 不存在")
        r = ReconV2(str(p)).report()
        self.assertEqual(r.get("format", {}).get("file_type"), "ELF")

    def test_rar_hash(self):
        p = HERE / "rar"
        if not os.path.exists(p):
            self.skipTest("rar 不存在")
        h = hashlib.sha256(open(p, "rb").read()).hexdigest()
        self.assertEqual(h, "56c3c4fd46faa7a9f52264d30cb96813e19ec7c4587d9f18424d7e909cf78555")

    def test_sublime_hash(self):
        p = HERE / "sublime_text"
        if not os.path.exists(p):
            self.skipTest("sublime_text 不存在")
        h = hashlib.sha256(open(p, "rb").read()).hexdigest()
        self.assertEqual(h, "7d924cb0b03961174d68e46380ba83c9bfa56f76c704001ac4419b2464452e52")

    def test_analysis_logs(self):
        d = HERE / "analysis_logs"
        self.assertTrue(d.exists())
        files = sorted(f.name for f in d.glob("*.json"))
        self.assertIn("rar.json", files)
        self.assertIn("sublime_text.json", files)


if __name__ == "__main__":
    unittest.main(verbosity=2)
