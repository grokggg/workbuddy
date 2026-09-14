#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M26 端到端测试: 构造 crackme -> 破解 -> 验证。"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent  # crackme-e2e/
sys.path.insert(0, str(HERE))

from build_crackme import build, build_elf  # noqa: E402


def run(exe: str, args) -> tuple:
    r = subprocess.run([exe] + args, capture_output=True, timeout=10)
    return r.stdout.decode(), r.returncode


class TestCrackmeE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="m26-")
        cls.crackme = os.path.join(cls.dir, "crackme")
        elf = build_elf(build())
        with open(cls.crackme, "wb") as f:
            f.write(elf)
        os.chmod(cls.crackme, 0o755)
        cls.data = bytearray(elf)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)

    def test_original_ok(self):
        out, rc = run(self.crackme, ["k"])
        self.assertIn("OK", out)
        self.assertEqual(rc, 0)

    def test_original_no(self):
        out, rc = run(self.crackme, ["x"])
        self.assertIn("NO", out)
        self.assertEqual(rc, 1)

    def test_original_noarg(self):
        _, rc = run(self.crackme, [])
        self.assertEqual(rc, 1)

    def test_patch_key_je_triggers_integrity(self):
        """patch 卡密 je(74->EB) 应触发完整性 BAD。"""
        d = bytearray(self.data)
        # 找卡密 je: cmp eax,0x6B(3d 6b 00 00 00) + je(74)
        key_cmp = bytes(d).find(b"\x3d\x6b\x00\x00\x00\x74")
        self.assertNotEqual(key_cmp, -1)
        d[key_cmp + 5] = 0xEB
        p = os.path.join(self.dir, "p1")
        open(p, "wb").write(d)
        os.chmod(p, 0o755)
        out, rc = run(p, ["x"])
        self.assertIn("BAD", out)
        self.assertEqual(rc, 2)

    def test_full_crack(self):
        """双 patch(卡密 + 完整性)应破解成功。"""
        d = bytearray(self.data)
        key_cmp = bytes(d).find(b"\x3d\x6b\x00\x00\x00\x74")
        d[key_cmp + 5] = 0xEB
        # 找完整性 je: cmp eax, XX(非6b) + je
        import re
        m = None
        for mm in re.finditer(rb"\x3d(.)\x00\x00\x00\x74", bytes(d)):
            if mm.group(1) != b"\x6b":
                m = mm
                break
        self.assertIsNotNone(m)
        d[m.start() + 5] = 0xEB
        p = os.path.join(self.dir, "cracked")
        open(p, "wb").write(d)
        os.chmod(p, 0o755)
        out, rc = run(p, ["x"])
        self.assertIn("OK", out)
        self.assertEqual(rc, 0)

    def test_integrity_check(self):
        """篡改任意代码字节应触发 BAD(完整性防护)。"""
        d = bytearray(self.data)
        # 改卡密 cmp 立即数(6b -> 6c)
        d[bytes(d).find(b"\x3d\x6b\x00\x00\x00") + 1] = 0x6C
        p = os.path.join(self.dir, "tamper")
        open(p, "wb").write(d)
        os.chmod(p, 0o755)
        out, rc = run(p, ["k"])
        self.assertIn("BAD", out)
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
