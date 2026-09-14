#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lib/patcher.py 单元测试"""
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

from lib.patcher import Patcher  # noqa: E402


def _make_file(path: str) -> None:
    data = bytes([0x74, 0x05]) + b"\x90" * 8 + b"\x75\x03" + b"\x90" * 4
    open(path, "wb").write(data)


class TestPatcher(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="patch-")
        self.target = os.path.join(self.tmp, "demo.bin")
        _make_file(self.target)
        self.p = Patcher(self.target, os.path.join(self.tmp, "work"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_make_copy(self):
        r = self.p.make_copy()
        self.assertTrue(r["ok"])
        self.assertTrue(os.path.exists(self.p.copy_path))

    def test_make_copy_missing(self):
        p = Patcher("/nonexistent", self.tmp)
        r = p.make_copy()
        self.assertFalse(r["ok"])

    def test_apply_ok(self):
        self.p.make_copy()
        r = self.p.apply(0, b"\x74\x05", b"\x90\x90")
        self.assertTrue(r["ok"])
        self.assertEqual(r["old"], "7405")
        self.assertEqual(r["new"], "9090")

    def test_apply_mismatch(self):
        self.p.make_copy()
        r = self.p.apply(0, b"\x75\x03", b"\x90\x90")  # 期望不符
        self.assertFalse(r["ok"])

    def test_verify_ok(self):
        self.p.make_copy()
        self.p.apply(0, b"\x74\x05", b"\x90\x90")
        r = self.p.verify(0, b"\x90\x90")
        self.assertTrue(r["ok"])

    def test_original_intact(self):
        self.p.make_copy()
        self.p.apply(0, b"\x74\x05", b"\x90\x90")
        self.assertTrue(self.p.original_intact())
        # 副本被改, 原件未动
        with open(self.target, "rb") as f:
            self.assertEqual(f.read(2), b"\x74\x05")


if __name__ == "__main__":
    unittest.main(verbosity=2)
