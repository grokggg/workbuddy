#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M41 测试: auth_locator + auth_patcher(合成 + 端到端)。"""
from __future__ import annotations

import os
import struct
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent  # auth-general/
sys.path.insert(0, str(HERE))

from auth_locator import AuthLocator  # noqa: E402
from auth_patcher import PATCH_MODES  # noqa: E402


def build_synth_elf(check_val: int) -> bytes:
    """合成教学 ELF: cmp eax, check_val → je OK / jmp FAIL。"""
    code = bytearray()
    code += b"\x83\x3c\x24\x02"
    jl = len(code); code += b"\x7c\x00"
    code += b"\x48\x8b\x44\x24\x10"
    code += b"\x0f\xb6\x00"
    code += b"\x3d" + struct.pack("<I", check_val)
    je = len(code); code += b"\x74\x00"
    jmpf = len(code); code += b"\xeb\x00"
    ok = len(code)
    code += b"\xb8\x01\x00\x00\x00" + b"\xbf\x01\x00\x00\x00"
    lea_ok = len(code); code += b"\x48\x8d\x35\x00\x00\x00\x00" + b"\xba\x03\x00\x00\x00"
    code += b"\x0f\x05" + b"\xb8\x3c\x00\x00\x00" + b"\x31\xff" + b"\x0f\x05"
    fail = len(code)
    code += b"\xb8\x01\x00\x00\x00" + b"\xbf\x01\x00\x00\x00"
    lea_no = len(code); code += b"\x48\x8d\x35\x00\x00\x00\x00" + b"\xba\x03\x00\x00\x00"
    code += b"\x0f\x05" + b"\xb8\x3c\x00\x00\x00" + b"\xbf\x01\x00\x00\x00" + b"\x0f\x05"
    code[jl+1] = (fail - (jl+2)) & 0xFF
    code[je+1] = (ok - (je+2)) & 0xFF
    code[jmpf+1] = (fail - (jmpf+2)) & 0xFF
    doff = len(code)
    code[lea_ok+3:lea_ok+7] = struct.pack("<i", doff - (lea_ok+7))
    noff = doff + 3
    code[lea_no+3:lea_no+7] = struct.pack("<i", noff - (lea_no+7))
    body = bytes(code) + b"OK\n" + b"NO\n"
    ph_off = 0x40
    code_off = ph_off + 56
    entry = 0x400000 + code_off
    ident = b"\x7fELF" + bytes([2, 1, 1, 0] + [0]*8)
    eh = struct.pack("<16sHHIQQQIHHHHHH", ident, 2, 0x3E, 1, entry, ph_off,
                     0, 0, 64, 56, 1, 0, 0, 0)
    ph = struct.pack("<IIQQQQQQ", 1, 5, 0, 0x400000, 0,
                     code_off + len(body), code_off + len(body), 0x1000)
    return eh + ph + b"\x00" * (code_off - (ph_off + 56)) + body


class TestAuthLocator(unittest.TestCase):
    def setUp(self):
        self.tmp = "/tmp/m41-test.elf"
        with open(self.tmp, "wb") as f:
            f.write(build_synth_elf(0x4B))  # 'K'

    def tearDown(self):
        if os.path.exists(self.tmp):
            os.unlink(self.tmp)

    def test_find_cmp_jcc(self):
        loc = AuthLocator(self.tmp)
        cands = loc.find_cmp_jcc()
        # 应找到 cmp eax, 0x4b → je
        key_cmp = [c for c in cands if "0x4b" in c["cmp"]]
        self.assertTrue(key_cmp, f"未找到 0x4b 比较: {cands}")
        self.assertEqual(key_cmp[0]["jcc"], "je")

    def test_patch_modes_complete(self):
        for k in ["cmp_type", "sig_type", "time_type", "online_type", "integrity_type"]:
            self.assertIn(k, PATCH_MODES)
            self.assertGreaterEqual(PATCH_MODES[k]["min_bytes"], 2)

    def test_integrity_first_rule(self):
        """副作用规则文档: 完整性型必须最先处理。"""
        self.assertIn("必须先", PATCH_MODES["integrity_type"]["side_effects"])


class TestEndToEnd(unittest.TestCase):
    def test_synth_patch_workflow(self):
        """合成 ELF: locator 定位 → patcher 模式 → 实际 patch → 验证。"""
        import tempfile
        tmp = os.path.join(tempfile.mkdtemp(), "synth")
        with open(tmp, "wb") as f:
            f.write(build_synth_elf(0x4B))
        os.chmod(tmp, 0o755)
        # 原始: 'K' OK, 'x' NO
        r1 = subprocess.run([tmp, "K"], capture_output=True, timeout=10)
        r2 = subprocess.run([tmp, "x"], capture_output=True, timeout=10)
        self.assertIn(b"OK", r1.stdout)
        self.assertIn(b"NO", r2.stdout)
        # locator 定位
        loc = AuthLocator(tmp)
        cands = loc.find_cmp_jcc()
        key_cmp = [c for c in cands if "0x4b" in c["cmp"]][0]
        jcc_va = int(key_cmp["jcc_addr"], 16)
        # va → 文件偏移
        off = loc.va_to_off(jcc_va)
        self.assertIsNotNone(off)
        # 按比较型模式 je→EB
        data = bytearray(open(tmp, "rb").read())
        self.assertEqual(data[off], 0x74)  # je
        data[off] = 0xEB
        patched = tmp + "-p"
        with open(patched, "wb") as f:
            f.write(data)
        os.chmod(patched, 0o755)
        # 验证: 任意输入 OK
        r3 = subprocess.run([patched, "x"], capture_output=True, timeout=10)
        self.assertIn(b"OK", r3.stdout)
        self.assertEqual(r3.returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
