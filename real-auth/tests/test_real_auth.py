#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M38 测试: 授权校验 crackme 处理。"""
from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent  # real-auth/
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))  # up-tools/


def run_bin(exe, inp):
    r = subprocess.run([exe, inp], capture_output=True, timeout=10)
    return r.stdout.decode(errors="ignore"), r.returncode


class TestRealAuth(unittest.TestCase):
    def test_auth_license_orig(self):
        out, rc = run_bin("real-auth/auth-license", "C")
        self.assertIn("OK", out)
        out2, rc2 = run_bin("real-auth/auth-license", "x")
        self.assertIn("NO", out2)

    def test_auth_license_cracked(self):
        p = "real-auth/auth-license-cracked"
        if not os.path.exists(p):
            self.skipTest("破解版不存在")
        out, rc = run_bin(p, "x")
        self.assertIn("OK", out)
        self.assertEqual(rc, 0)

    def test_auth_trial_cracked(self):
        p = "real-auth/auth-trial-cracked"
        if not os.path.exists(p):
            self.skipTest("破解版不存在")
        out, rc = run_bin(p, "x")
        self.assertEqual(rc, 0)  # LIC

    def test_auth_network_cracked(self):
        p = "real-auth/auth-network-cracked"
        if not os.path.exists(p):
            self.skipTest("破解版不存在")
        out, rc = run_bin(p, "x")
        self.assertIn("OK", out)
        self.assertEqual(rc, 0)

    def test_auth_network_dual_check(self):
        """原始: 双段校验, 单段对也拒绝。"""
        out1, _ = run_bin("real-auth/auth-network", "AZ")
        self.assertIn("OK", out1)
        out2, _ = run_bin("real-auth/auth-network", "Ax")
        self.assertIn("NO", out2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
