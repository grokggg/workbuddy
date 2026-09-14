#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lib/analysis_v2.py 单元测试"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "lib"))

from lib.analysis_v2 import AnalysisV2  # noqa: E402


def _make_bin(path: str) -> None:
    data = bytearray()
    data += bytes([0xB8, 0x40, 0xE2, 0x01, 0x00])  # mov eax, const
    data += bytes([0x3B, 0xC8])                     # cmp ecx, eax
    data += bytes([0x74, 0x05])                     # JE
    data += b"IsDebuggerPresent\x00GetTickCount\x00"
    data += b"checksum\x00"
    open(path, "wb").write(data)


class TestAnalysisV2(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="av2-")
        self.bin = os.path.join(self.tmp, "demo.bin")
        _make_bin(self.bin)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_static_scan(self):
        a = AnalysisV2(self.bin)
        r = a.static_scan()
        self.assertGreaterEqual(r["count"], 1)

    def test_api_scan(self):
        a = AnalysisV2(self.bin)
        r = a.api_scan()
        apis = [x["api"] for x in r["apis"]]
        self.assertIn("IsDebuggerPresent", apis)

    def test_behavior_antidebug(self):
        a = AnalysisV2(self.bin)
        r = a.behavior_model()
        names = [b["behavior"] for b in r["behaviors"]]
        self.assertIn("anti-debug", names)

    def test_behavior_timing(self):
        a = AnalysisV2(self.bin)
        r = a.behavior_model()
        names = [b["behavior"] for b in r["behaviors"]]
        self.assertIn("timing-check", names)

    def test_behavior_plain(self):
        tmp = tempfile.mkdtemp()
        f = os.path.join(tmp, "plain.bin")
        open(f, "wb").write(b"\x90" * 100)
        a = AnalysisV2(f)
        r = a.behavior_model()
        names = [b["behavior"] for b in r["behaviors"]]
        self.assertIn("plain", names)

    def test_missing_file(self):
        a = AnalysisV2("/nonexistent")
        self.assertEqual(a.data, b"")

    def test_report(self):
        a = AnalysisV2(self.bin)
        rep = a.report()
        for k in ("static", "apis", "behavior", "elf_sections"):
            self.assertIn(k, rep)


if __name__ == "__main__":
    unittest.main(verbosity=2)
