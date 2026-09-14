#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M29 测试: 带保护 crackme 批量破解。"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent  # protected-crackmes/
sys.path.insert(0, str(HERE))

import process_real as _pr
sys.path.insert(0, str(HERE))
UPX_EXISTS = os.path.exists(_pr.UPX)

TARGETS = ["cm-upx1", "cm-upx6", "cm-upx9", "cm-base"]


def run_bin(exe, inp="abc\n"):
    r = subprocess.run([exe], input=inp.encode(), capture_output=True,
                       timeout=10)
    return r.stdout.decode(errors="ignore"), r.returncode


class TestProtectedCrackmes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = Path(HERE)
        cls.cracked = {}
        for name in TARGETS:
            src = cls.dir / name
            if not src.exists():
                continue
            # 带壳先脱壳(UPX 可用时)或复用已有 unpacked
            if name.startswith("cm-upx"):
                unpacked = cls.dir / (name + "-unpacked")
                if UPX_EXISTS and not unpacked.exists():
                    ok, _ = _pr.unpck(str(src), str(unpacked))
                    if not ok:
                        continue
                if not unpacked.exists():
                    continue
                patch_src = unpacked
            else:
                patch_src = src
            cracked = cls.dir / (name + "-cracked")
            ok, msg = _pr.find_and_patch_jne(str(patch_src), str(cracked))
            if ok:
                cls.cracked[name] = str(cracked)

    def test_at_least_3_cracked(self):
        self.assertGreaterEqual(len(self.cracked), 3)

    def test_cracked_succeeds(self):
        for name, cracked in self.cracked.items():
            out, rc = run_bin(cracked)
            self.assertIn("Congratulations", out, f"{name} 破解版应成功")
            self.assertEqual(rc, 0)

    def test_packed_orig_has_shell(self):
        """加壳目标应检出 UPX 特征(节表少/入口 stub)。"""
        from lib.recon_v3 import ReconV3
        sys.path.insert(0, str(HERE.parent))
        sys.path.insert(0, str(HERE.parent / "lib"))
        for name in ["cm-upx1", "cm-upx9"]:
            src = str(self.dir / name)
            if not os.path.exists(src):
                continue
            r = ReconV3(src)
            rep = r.report()
            if "elf" in rep and "sections" in rep["elf"]:
                self.assertLess(len(rep["elf"]["sections"]), 5,
                                f"{name} 加壳后节表应大幅减少")


if __name__ == "__main__":
    unittest.main(verbosity=2)
