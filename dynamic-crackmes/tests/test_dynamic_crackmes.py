#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M30 测试: 反调试/多校验点 crackme 破解。"""
from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent  # dynamic-crackmes/
sys.path.insert(0, str(HERE))

from process_dynamic import disasm_binary, patch_antidebug, patch_all_jcc  # noqa: E402

TARGETS = {
    "ad1": "p", "ad2": "o", "mc1": "k", "mc2": "A",
}


def run_bin(exe, inp="x"):
    r = subprocess.run([exe, inp], capture_output=True, timeout=10)
    return r.stdout.decode(errors="ignore"), r.returncode


class TestDynamicCrackmes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cracked = {}
        for name in TARGETS:
            src = HERE / name
            if not src.exists():
                continue
            d = bytearray(open(src, "rb").read())
            try:
                insns, off, base = disasm_binary(str(src))
            except Exception:
                continue
            has_ad = any("0x65" in i.op_str for i in insns
                         if i.mnemonic == "mov")
            ad_patched = patch_antidebug(insns, off, base, d) if has_ad else []
            skip = set(p[0] if isinstance(p, tuple) else p for p in ad_patched)
            jcc = patch_all_jcc(insns, off, base, d, skip_addrs=skip)
            cracked = HERE / (name + "-cracked")
            with open(cracked, "wb") as f:
                f.write(d)
            os.chmod(cracked, 0o755)
            cls.cracked[name] = str(cracked)

    def test_all_4_cracked(self):
        self.assertEqual(len(self.cracked), 4)

    def test_cracked_ok_wrong_pwd(self):
        for name, cracked in self.cracked.items():
            out, rc = run_bin(cracked, "x")
            self.assertIn("OK", out, f"{name} 破解版错误密码应 OK")
            self.assertEqual(rc, 0)

    def test_orig_behaves(self):
        for name, pwd in TARGETS.items():
            src = str(HERE / name)
            # 正确密码应 OK(除反调试目标在沙箱 rc=9)
            _, rc_ok = run_bin(src, pwd)
            # 反调试目标沙箱里 rc=9(ptrace 被禁), 其他 rc=0
            if name.startswith("ad"):
                self.assertEqual(rc_ok, 9)
            else:
                self.assertEqual(rc_ok, 0)

    def test_antidebug_detected(self):
        """ad 目标应检出 ptrace 特征。"""
        for name in ["ad1", "ad2"]:
            src = HERE / name
            if not src.exists():
                continue
            insns, _, _ = disasm_binary(str(src))
            has_ad = any("0x65" in i.op_str for i in insns
                         if i.mnemonic == "mov")
            self.assertTrue(has_ad, f"{name} 应检出 ptrace")


if __name__ == "__main__":
    unittest.main(verbosity=2)
