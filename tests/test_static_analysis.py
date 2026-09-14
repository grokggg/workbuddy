#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lib/static_analysis.py 单元测试"""
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

from lib.static_analysis import StaticAnalyzer  # noqa: E402


def _make_bin(path: str) -> None:
    data = bytearray()
    data += bytes([0xB8, 0x40, 0xE2, 0x01, 0x00])  # mov eax, 123456
    data += bytes([0x83, 0xF8, 0x40])              # cmp eax, 0x40
    data += bytes([0x74, 0x05])                    # JE +5
    data += bytes([0x90] * 4)
    data += bytes([0xE9, 0x00, 0x00, 0x00, 0x00])  # jmp rel32
    data += bytes([0xC3])                          # ret
    data += b"password_check\x00license_key\x00" + "卡密验证".encode()
    open(path, "wb").write(data)


class TestStaticAnalyzer(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="sa-")
        self.bin = os.path.join(self.tmp, "demo.bin")
        _make_bin(self.bin)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_locate_keywords(self):
        a = StaticAnalyzer(self.bin)
        r = a.locate_key_functions()
        self.assertGreater(r["count"], 0)

    def test_locate_password(self):
        a = StaticAnalyzer(self.bin, ["password"])
        r = a.locate_key_functions()
        self.assertGreaterEqual(r["count"], 1)

    def test_instruction_sequence(self):
        a = StaticAnalyzer(self.bin)
        seq = a.instruction_sequence(0, 5)
        self.assertGreaterEqual(len(seq), 3)
        self.assertEqual(seq[0]["mnemonic"], "mov eax, imm32")

    def test_jump_graph(self):
        a = StaticAnalyzer(self.bin)
        jg = a.jump_graph()
        self.assertGreaterEqual(jg["count"], 2)  # JE + JMP

    def test_identify_checks(self):
        a = StaticAnalyzer(self.bin)
        chk = a.identify_checks()
        self.assertGreaterEqual(chk["count"], 1)

    def test_missing_file(self):
        a = StaticAnalyzer("/nonexistent")
        self.assertEqual(a.data, b"")


if __name__ == "__main__":
    unittest.main(verbosity=2)
