#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lib/recon_v3.py 单元测试"""
from __future__ import annotations

import os
import shutil
import struct
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "lib"))

from lib.recon_v3 import ReconV3  # noqa: E402


def _make_elf(path: str) -> None:
    """构造最小 ELF64(可被 pyelftools 解析)。"""
    code = bytes([
        0xB8, 0x3C, 0x00, 0x00, 0x00,  # mov eax, 60
        0xBF, 0x00, 0x00, 0x00, 0x00,  # mov edi, 0
        0x0F, 0x05,                    # syscall
    ])
    ph_off = 0x40
    code_off = ph_off + 56
    entry = 0x400000 + code_off
    ident = b'\x7fELF' + bytes([2, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    eh = struct.pack('<16sHHIQQQIHHHHHH',
        ident, 2, 0x3E, 1, entry, ph_off, 0, 0, 64, 56, 1, 0, 0, 0)
    ph = struct.pack('<IIQQQQQQ',
        1, 5, 0, 0x400000, 0, code_off + len(code), code_off + len(code), 0x1000)
    with open(path, "wb") as f:
        f.write(eh + ph + b'\x00' * (code_off - (ph_off + 56)) + code)


class TestReconV3(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="r3-")
        self.elf = os.path.join(self.tmp, "min.elf")
        _make_elf(self.elf)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_load(self):
        r = ReconV3(self.elf)
        self.assertTrue(r.load())

    def test_load_missing(self):
        r = ReconV3("/nonexistent")
        self.assertFalse(r.load())

    def test_detect_elf(self):
        r = ReconV3(self.elf)
        r.load()
        fmt = r.detect_format()
        self.assertEqual(fmt["type"], "ELF")
        self.assertEqual(fmt["bits"], 64)

    def test_elf_parse(self):
        r = ReconV3(self.elf)
        r.load()
        e = r.elf_parse()
        self.assertIn("machine", e)
        self.assertEqual(e["type"], "ET_EXEC")

    def test_elf_sections(self):
        r = ReconV3(self.elf)
        r.load()
        e = r.elf_parse()
        self.assertIn("sections", e)

    def test_disassemble(self):
        r = ReconV3(self.elf)
        r.load()
        insns = r.disassemble(bytes([0xB8, 0x3C, 0, 0, 0, 0x0F, 0x05]), count=5)
        self.assertGreaterEqual(len(insns), 1)
        self.assertIn("mnemonic", insns[0])

    def test_entry_disasm(self):
        r = ReconV3(self.elf)
        r.load()
        d = r.entry_disasm(count=5)
        self.assertIn("insns", d)
        self.assertGreaterEqual(len(d["insns"]), 1)

    def test_report(self):
        r = ReconV3(self.elf)
        rep = r.report()
        self.assertEqual(rep["format"]["type"], "ELF")
        self.assertIn("elf", rep)


if __name__ == "__main__":
    unittest.main(verbosity=2)
