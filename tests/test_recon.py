#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lib/recon.py 单元测试"""
from __future__ import annotations

import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent  # up-tools 根
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "lib"))

from lib.recon import Recon, _entropy  # noqa: E402


def _make_pe(path: str) -> None:
    data = bytearray(b"MZ" + b"\x00" * 0x3A)
    data += struct.pack("<I", 0x40)
    data += b"\x00" * (0x40 - len(data))
    data += b"PE\x00\x00"
    data += struct.pack("<H", 0x14C)  # x86
    data += struct.pack("<H", 0xE0)   # optional header size
    data += b"\x00" * (0x100 - len(data))
    data += bytes([0xB8, 0x40, 0xE2, 0x01, 0x00])  # mov eax,123456
    data += bytes([0x74, 0x05])                    # JE
    data += b"\x00" * (0x140 - len(data))
    data += b"password\x00license\x00key\x00"
    data += b"LoadLibrary\x00GetProcAddress\x00"
    data += b"UPX"  # 壳特征
    open(path, "wb").write(data)


def _make_elf(path: str) -> None:
    data = bytearray(b"\x7fELF")
    data += bytes([2])  # 64-bit
    data += b"\x00" * 15
    data += struct.pack("<Q", 0x401000)  # e_entry
    data += b"\x00" * (0x40 - len(data))
    open(path, "wb").write(data)


class TestEntropy(unittest.TestCase):
    def test_uniform(self):
        self.assertAlmostEqual(_entropy(b"\x00" * 100), 0.0, places=2)

    def test_random(self):
        import random
        random.seed(1)
        d = bytes(random.randrange(256) for _ in range(1000))
        self.assertGreater(_entropy(d), 6.0)


class TestRecon(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="recon-")
        self.pe = os.path.join(self.tmp, "demo.exe")
        self.elf = os.path.join(self.tmp, "demo.elf")
        _make_pe(self.pe)
        _make_elf(self.elf)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_load(self):
        r = Recon(self.pe)
        self.assertTrue(r.load())
        self.assertGreater(r.info["size"], 0)

    def test_load_missing(self):
        r = Recon("/nonexistent")
        self.assertFalse(r.load())
        self.assertIn("error", r.info)

    def test_file_type_pe(self):
        r = Recon(self.pe)
        r.load()
        self.assertEqual(r.file_type(), "PE")

    def test_file_type_elf(self):
        r = Recon(self.elf)
        r.load()
        self.assertEqual(r.file_type(), "ELF")

    def test_arch_pe_x86(self):
        r = Recon(self.pe)
        r.load()
        self.assertEqual(r.arch(), "x86")

    def test_arch_elf_x64(self):
        r = Recon(self.elf)
        r.load()
        self.assertEqual(r.arch(), "x64")

    def test_packed_detection(self):
        r = Recon(self.pe)
        r.load()
        p = r.packed()
        self.assertIn("UPX", p["markers"])  # 特征命中

    def test_strings_sensitive(self):
        r = Recon(self.pe)
        r.load()
        s = r.strings()
        self.assertGreater(s["total"], 0)
        self.assertTrue(any("password" in x for x in s["sensitive"]))

    def test_imports(self):
        r = Recon(self.pe)
        r.load()
        imp = r.imports()
        self.assertIn("LoadLibrary", imp["apis"])

    def test_sections(self):
        r = Recon(self.pe)
        r.load()
        s = r.sections()
        self.assertIn("sections", s)

    def test_entry_point_pe(self):
        r = Recon(self.pe)
        r.load()
        ep = r.entry_point()
        self.assertIn("ep", ep)

    def test_report_full(self):
        r = Recon(self.pe)
        rep = r.report()
        for k in ("file_type", "arch", "packed", "strings", "imports",
                  "sections", "entry_point"):
            self.assertIn(k, rep)


if __name__ == "__main__":
    unittest.main(verbosity=2)
