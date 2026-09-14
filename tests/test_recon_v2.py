#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lib/recon_v2.py 单元测试"""
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

from lib.recon_v2 import ReconV2, _entropy  # noqa: E402


def _make_pe(path: str, with_upx: bool = False,
             with_antidebug: bool = False, with_antivm: bool = False) -> None:
    data = bytearray(b"MZ" + b"\x00" * 0x3A)
    data += struct.pack("<I", 0x40)
    data += b"\x00" * (0x40 - len(data))
    data += b"PE\x00\x00"
    data += struct.pack("<H", 0x14C)
    data += struct.pack("<H", 0xE0)
    data += b"\x00" * (0x100 - len(data))
    data += bytes([0xB8, 0x40, 0xE2, 0x01, 0x00])
    data += b"\x00" * (0x200 - len(data))
    if with_upx:
        data += b"UPX!"
    if with_antidebug:
        data += b"IsDebuggerPresent" + b"\x64\xa1\x30\x00\x00\x00"
    if with_antivm:
        data += b"VMware" + b"\x0f\xa2"
    data += b"checksum\x00self_check\x00app.asar\x00"
    open(path, "wb").write(data)


class TestEntropyV2(unittest.TestCase):
    def test_uniform(self):
        self.assertAlmostEqual(_entropy(b"\x00" * 100), 0.0, places=2)

    def test_random(self):
        import random
        random.seed(2)
        d = bytes(random.randrange(256) for _ in range(1000))
        self.assertGreater(_entropy(d), 6.0)


class TestReconV2(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="r2-")
        self.normal = os.path.join(self.tmp, "normal.exe")
        self.upx = os.path.join(self.tmp, "upx.exe")
        self.antidebug = os.path.join(self.tmp, "adbg.exe")
        self.antivm = os.path.join(self.tmp, "avm.exe")
        _make_pe(self.normal)
        _make_pe(self.upx, with_upx=True)
        _make_pe(self.antidebug, with_antidebug=True)
        _make_pe(self.antivm, with_antivm=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_load(self):
        r = ReconV2(self.normal)
        self.assertTrue(r.load())

    def test_load_missing(self):
        r = ReconV2("/nonexistent")
        self.assertFalse(r.load())

    def test_format_pe(self):
        r = ReconV2(self.normal)
        r.load()
        fmt = r.format_info()
        self.assertEqual(fmt["file_type"], "PE")
        self.assertEqual(fmt["arch"], "x86")

    def test_detect_upx(self):
        r = ReconV2(self.upx)
        r.load()
        pk = r.detect_packer()
        self.assertTrue(pk["packed"])
        self.assertIn("UPX", pk["markers"])

    def test_detect_normal_not_packed(self):
        r = ReconV2(self.normal)
        r.load()
        pk = r.detect_packer()
        self.assertFalse(pk["packed"])

    def test_detect_antidebug(self):
        r = ReconV2(self.antidebug)
        r.load()
        ad = r.detect_antidebug()
        self.assertIn("IsDebuggerPresent", ad["detected"])

    def test_detect_antivm(self):
        r = ReconV2(self.antivm)
        r.load()
        av = r.detect_antivm()
        self.assertTrue(av["detected"])
        self.assertTrue(any("VMware" in h or "CPUID" in h for h in av["detected"]))

    def test_detect_integrity(self):
        r = ReconV2(self.normal)
        r.load()
        ig = r.detect_integrity()
        self.assertTrue(ig["detected"])

    def test_detect_anti_repack(self):
        r = ReconV2(self.normal)
        r.load()
        ar = r.detect_anti_repack()
        self.assertTrue(ar["detected"])

    def test_report_full(self):
        r = ReconV2(self.upx)
        rep = r.report()
        for k in ("format", "packer", "antidebug", "antivm",
                  "integrity", "anti_repack"):
            self.assertIn(k, rep)

    def test_asar_format(self):
        """M23: asar 格式识别。"""
        import struct as st
        p = os.path.join(self.tmp, "app.asar")
        header = b'{"files":{"main.js":{"size":10}}}'
        pad = (4 - len(header) % 4) % 4
        header += b"\x00" * pad
        with open(p, "wb") as f:
            f.write(st.pack("<I", 4))           # pickle
            f.write(st.pack("<I", len(header)))  # header size
            f.write(st.pack("<I", len(header)))  # json size
            f.write(st.pack("<I", 10))           # data size
            f.write(header)
            f.write(b"x" * 10)
        r = ReconV2(p)
        r.load()
        fmt = r.format_info()
        self.assertEqual(fmt["file_type"], "ASAR")

    def test_platform_mismatch_fp(self):
        """M24: 平台不匹配特征(MPRESS 在 ELF 里)不应命中。"""
        p = os.path.join(self.tmp, "fake.bin")
        open(p, "wb").write(b"\x7fELF" + b"\x00" * 100 + b"MPRESS")
        r = ReconV2(p)
        r.load()
        pk = r.detect_packer()
        # M24 修复: 平台过滤生效, ELF 不检 Windows PE 壳
        self.assertFalse(pk["packed"])
        self.assertEqual(pk["markers"], [])

    def test_pe_packer_only_in_pe(self):
        """M24: PE 独有壳(Themida/ASPack)只在 PE 检出, ELF 不命中。"""
        # ELF 里含 Themida 特征 -> 不命中
        p1 = os.path.join(self.tmp, "elf-themida.bin")
        open(p1, "wb").write(b"\x7fELF" + b"\x00" * 100 + b"Themida")
        r1 = ReconV2(p1)
        r1.load()
        self.assertFalse(r1.detect_packer()["packed"])
        # PE 里含 Themida 特征 -> 命中
        p2 = os.path.join(self.tmp, "pe-themida.exe")
        data = bytearray(b"MZ" + b"\x00" * 0x3A)
        data += __import__("struct").pack("<I", 0x40)
        data += b"\x00" * (0x40 - len(data))
        data += b"PE\x00\x00" + b"\x00" * 100 + b"Themida"
        open(p2, "wb").write(data)
        r2 = ReconV2(p2)
        r2.load()
        pk2 = r2.detect_packer()
        self.assertTrue(pk2["packed"])
        self.assertIn("Themida", pk2["markers"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
