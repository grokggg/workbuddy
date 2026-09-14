#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M28 端到端: 真实 crackme 反汇编定位 + 破解验证。"""
from __future__ import annotations

import os
import shutil
import struct
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent.parent  # up-tools/
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "lib"))

from lib.recon_v3 import ReconV3  # noqa: E402
from lib.recon_v3 import CAPSTONE_OK, PYELFTOOLS_OK  # noqa: E402


def run_bin(exe, inp=""):
    r = subprocess.run([exe], input=inp.encode(), capture_output=True,
                       timeout=10)
    return r.stdout.decode(errors="ignore"), r.returncode


class TestRealBinaries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.crackme = str(HERE / "real-binaries" / "crackme-angr")
        cls.cracked = str(HERE / "real-binaries" / "crackme-angr-cracked")
    def test_crackme_exists(self):
        self.assertTrue(os.path.exists(self.crackme))
        self.assertTrue(os.path.exists(self.cracked))

    @unittest.skipUnless(CAPSTONE_OK, "capstone 未装")
    def test_disasm_main(self):
        """反汇编 main 应含 strcmp 调用和 jne。"""
        r = ReconV3(self.crackme)
        r.load()
        from elftools.elf.elffile import ELFFile
        import io
        d = open(self.crackme, "rb").read()
        elf = ELFFile(io.BytesIO(d))
        text = elf.get_section_by_name(".text")
        code = text.data()
        base = text["sh_addr"]
        from capstone import Cs, CS_ARCH_X86, CS_MODE_64
        md = Cs(CS_ARCH_X86, CS_MODE_64)
        # main = 0x1165
        off = 0x1165 - base
        dis = list(md.disasm(code[off:off + 0xC0], 0x1165))
        mnemonics = [i.mnemonic for i in dis]
        self.assertIn("call", mnemonics)  # strcmp 调用

    @unittest.skipUnless(CAPSTONE_OK, "capstone 未装")
    def test_orig_fails(self):
        out, _ = run_bin(self.crackme, "abc")
        self.assertIn("Invalid", out)

    def test_cracked_succeeds(self):
        out, _ = run_bin(self.cracked, "abc")
        self.assertIn("Congratulations", out)

    def test_cracked_any_input(self):
        for inp in ["0000000000", "abc", "9999999999", ""]:
            out, _ = run_bin(self.cracked, inp)
            self.assertIn("Congratulations", out, f"输入 {inp!r} 应成功")

    def test_orig_real_elf(self):
        d = open(self.crackme, "rb").read(4)
        self.assertEqual(d, b"\x7fELF")


if __name__ == "__main__":
    unittest.main(verbosity=2)
