#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v5-jump-patch 单元测试

覆盖:
  - Analyzer: 分析文件/PE 检测/字符串/条件跳转扫描
  - Patcher: 副本复制/NOP 修改/字节验证
  - Verifier: 真实运行
  - 全流程: 分析->定位->修改->验证
  - 边界: 只改副本, 原件不动

跑法: python3 tests/test_engine.py
"""
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

from lib.engine import (  # noqa: E402
    Analyzer,
    JumpPatchEngine,
    Patcher,
    Verifier,
)


def _make_mock_exe(path: str) -> None:
    """造一个含条件跳转的 mock 可执行文件(PE 头 + 跳转指令)。"""
    # 构造: MZ 头 + 0x3C 偏移的 PE 头 + 一些字节 + 条件跳转
    data = bytearray(b"MZ" + b"\x00" * 0x3A)
    data += struct.pack("<I", 0x40)  # PE 偏移 = 0x40
    data += b"\x00" * (0x40 - len(data))
    data += b"PE\x00\x00"  # PE 签名
    data += struct.pack("<H", 0x14C)  # x86 machine
    # 填充到 0x100
    data += b"\x00" * (0x100 - len(data))
    # 条件跳转区
    data += bytes([0x74, 0x05])  # JE short @ 0x100
    data += b"\x90\x90\x90\x90\x90"
    data += bytes([0x75, 0x03])  # JNE short @ 0x107
    data += b"\x90\x90\x90"
    data += bytes([0x0F, 0x84, 0x00, 0x00, 0x00, 0x00])  # JE near @ 0x10E
    # 字符串
    data += b"password_check\x00login\x00admin\x00"
    with open(path, "wb") as f:
        f.write(data)


class TestAnalyzer(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="v5-")
        self.exe = os.path.join(self.tmp, "demo.exe")
        _make_mock_exe(self.exe)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_analyze_ok(self):
        a = Analyzer(self.exe)
        r = a.analyze()
        self.assertTrue(r["ok"])
        self.assertTrue(r["is_pe"])
        self.assertEqual(r["machine"], "x86")

    def test_analyze_missing(self):
        a = Analyzer("/nonexistent")
        r = a.analyze()
        self.assertFalse(r["ok"])

    def test_strings(self):
        a = Analyzer(self.exe)
        r = a.analyze()
        self.assertTrue(any("password_check" in s for s in r["strings"]))

    def test_scan_jumps(self):
        a = Analyzer(self.exe)
        r = a.analyze()
        jumps = r["jump_hits"]
        self.assertGreaterEqual(len(jumps), 3)  # JE short + JNE short + JE near
        self.assertEqual(jumps[0]["mnemonic"], "JE/JZ (short)")
        self.assertEqual(jumps[0]["offset"], 0x100)

    def test_scan_jumps_near(self):
        a = Analyzer(self.exe)
        r = a.analyze()
        jumps = r["jump_hits"]
        near = [j for j in jumps if j["type"] == "near"]
        self.assertEqual(len(near), 1)
        self.assertEqual(near[0]["offset"], 0x10C)  # 0x74@0x100 + 2 + 5 + 0x75@0x107 + 2 + 3


class TestPatcher(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="v5p-")
        self.exe = os.path.join(self.tmp, "demo.exe")
        _make_mock_exe(self.exe)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_make_copy(self):
        p = Patcher(self.exe, os.path.join(self.tmp, "work"))
        copy = p.make_copy()
        self.assertTrue(os.path.exists(copy))
        self.assertEqual(os.path.getsize(copy), os.path.getsize(self.exe))
        # 原件不动
        self.assertEqual(os.path.getsize(self.exe), os.path.getsize(copy))

    def test_nop_jump(self):
        p = Patcher(self.exe, os.path.join(self.tmp, "work"))
        p.make_copy()
        r = p.nop_jump(0x100, 2)
        self.assertTrue(r["ok"])
        self.assertEqual(r["orig"], "7405")
        self.assertEqual(r["patched"], "9090")

    def test_verify_bytes(self):
        p = Patcher(self.exe, os.path.join(self.tmp, "work"))
        p.make_copy()
        p.nop_jump(0x100, 2)
        self.assertTrue(p.verify_bytes(0x100, 2, b"\x90\x90"))
        # 原件仍是 JE
        with open(self.exe, "rb") as f:
            f.seek(0x100)
            self.assertEqual(f.read(1), b"\x74")

    def test_original_untouched(self):
        """边界: 只改副本, 原件字节不变。"""
        p = Patcher(self.exe, os.path.join(self.tmp, "work"))
        p.make_copy()
        p.nop_jump(0x100, 2)
        with open(self.exe, "rb") as f:
            f.seek(0x100)
            self.assertEqual(f.read(2), b"\x74\x05")  # 原件未动


class TestVerifier(unittest.TestCase):
    def test_run(self):
        v = Verifier(tempfile.mkdtemp())
        r = v.run(["python3", "-c", "print('hi')"])
        self.assertTrue(r["ok"])
        self.assertIn("hi", r["stdout"])

    def test_run_missing(self):
        v = Verifier(tempfile.mkdtemp())
        r = v.run(["/nonexistent_cmd"])
        self.assertFalse(r["ok"])

    def test_verify_patch(self):
        tmp = tempfile.mkdtemp()
        exe = os.path.join(tmp, "demo.exe")
        _make_mock_exe(exe)
        p = Patcher(exe, os.path.join(tmp, "work"))
        copy = p.make_copy()
        p.nop_jump(0x100, 2)
        v = Verifier(tmp)
        r = v.verify_patch(copy, 0x100, 2)
        self.assertTrue(r["ok"])


class TestEngine(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="v5e-")
        self.exe = os.path.join(self.tmp, "demo.exe")
        _make_mock_exe(self.exe)
        self.work = os.path.join(self.tmp, "work")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_full_flow(self):
        eng = JumpPatchEngine(self.exe, self.work)
        steps = eng.run_all(jump_index=0)
        self.assertEqual(len(steps), 4)
        ok = sum(1 for s in steps if s["ok"])
        self.assertEqual(ok, 4)  # 分析/定位/修改/验证全过

    def test_full_flow_with_run(self):
        eng = JumpPatchEngine(self.exe, self.work)
        steps = eng.run_all(jump_index=0,
                            verify_cmd=["python3", "-c", "print('ok')"])
        self.assertEqual(len(steps), 4)
        self.assertTrue(all(s["ok"] for s in steps))

    def test_locate_oob(self):
        eng = JumpPatchEngine(self.exe, self.work)
        eng.run_analyze()
        r = eng.run_locate(jump_index=999)
        self.assertFalse(r["ok"])

    def test_modify_without_locate(self):
        eng = JumpPatchEngine(self.exe, self.work)
        r = eng.run_modify()
        self.assertFalse(r["ok"])

    def test_log_text(self):
        eng = JumpPatchEngine(self.exe, self.work)
        eng.run_all(jump_index=0)
        txt = eng.log_text()
        self.assertIn("[1/4]", txt)
        self.assertIn("[4/4]", txt)
        self.assertIn("通过", txt)


if __name__ == "__main__":
    unittest.main(verbosity=2)
