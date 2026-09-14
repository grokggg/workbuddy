#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lib/target_analysis.py 单元测试"""
from __future__ import annotations

import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "lib"))

from lib.target_analysis import TargetAnalyzer  # noqa: E402


def _make_pe(path: str) -> None:
    data = bytearray(b"MZ" + b"\x00" * 0x3A)
    data += struct.pack("<I", 0x40)
    data += b"\x00" * (0x40 - len(data))
    data += b"PE\x00\x00"
    data += struct.pack("<H", 0x14C)
    data += struct.pack("<H", 0xE0)
    data += b"\x00" * (0x100 - len(data))
    data += bytes([0xB8, 0x40, 0xE2, 0x01, 0x00])  # mov eax, 123456
    data += bytes([0x83, 0xF8, 0x40])              # cmp eax, 0x40
    data += bytes([0x74, 0x05])                    # JE
    data += b"\x00" * (0x140 - len(data))
    data += b"password\x00license\x00"
    open(path, "wb").write(data)


class TestTargetAnalyzer(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ta-")
        self.pe = os.path.join(self.tmp, "demo.exe")
        _make_pe(self.pe)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_analyze_full(self):
        a = TargetAnalyzer(self.pe)
        r = a.analyze()
        self.assertIn("recon", r)
        self.assertIn("static", r)
        self.assertIn("suggestions", r)

    def test_recon_fields(self):
        a = TargetAnalyzer(self.pe)
        r = a.analyze()["recon"]
        self.assertEqual(r["file_type"], "PE")
        self.assertEqual(r["arch"], "x86")

    def test_suggestions_nonempty(self):
        a = TargetAnalyzer(self.pe)
        r = a.analyze()
        self.assertGreater(len(r["suggestions"]), 0)

    def test_suggestion_has_priority(self):
        a = TargetAnalyzer(self.pe)
        r = a.analyze()
        for s in r["suggestions"]:
            self.assertIn("priority", s)
            self.assertIn("action", s)

    def test_report_text(self):
        a = TargetAnalyzer(self.pe)
        txt = a.report_text()
        self.assertIn("目标情报分析", txt)
        self.assertIn("修改建议", txt)


if __name__ == "__main__":
    unittest.main(verbosity=2)
