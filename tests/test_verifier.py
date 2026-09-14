#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lib/verifier.py 单元测试"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "lib"))

from lib.verifier import Verifier  # noqa: E402


class TestVerifier(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="veri-")
        self.script = os.path.join(self.tmp, "demo.py")
        open(self.script, "w").write("print('hello')\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_run_isolated(self):
        v = Verifier(self.tmp)
        r = v.run_isolated("python3", [self.script])
        self.assertTrue(r["ok"])
        self.assertIn("hello", r["stdout"])

    def test_run_missing(self):
        v = Verifier(self.tmp)
        r = v.run_isolated("/nonexistent")
        self.assertFalse(r["ok"])

    def test_compare_same(self):
        v = Verifier(self.tmp)
        r = v.compare(0, 0, "a", "a")
        self.assertFalse(r["behavior_changed"])

    def test_compare_diff_exit(self):
        v = Verifier(self.tmp)
        r = v.compare(0, 1, "a", "a")
        self.assertTrue(r["behavior_changed"])
        self.assertIn("退出码", r["diffs"][0])

    def test_compare_diff_out(self):
        v = Verifier(self.tmp)
        r = v.compare(0, 0, "a", "b")
        self.assertTrue(r["behavior_changed"])

    def test_integrity(self):
        v = Verifier(self.tmp)
        f1 = os.path.join(self.tmp, "a.bin")
        f2 = os.path.join(self.tmp, "b.bin")
        open(f1, "wb").write(b"aaa")
        open(f2, "wb").write(b"bbb")
        r = v.integrity(f1, f2)
        self.assertTrue(r["different"])

    def test_report(self):
        v = Verifier(self.tmp)
        r1 = v.run_isolated("python3", [self.script])
        r2 = v.run_isolated("python3", [self.script])
        rep = v.report(self.script, self.script, r1, r2)
        self.assertIn("integrity", rep)
        self.assertIn("compare", rep)


if __name__ == "__main__":
    unittest.main(verbosity=2)
