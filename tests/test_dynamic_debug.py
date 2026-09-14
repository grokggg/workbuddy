#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lib/dynamic_debug.py 单元测试"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "lib"))

from lib.dynamic_debug import DynamicDebugger  # noqa: E402


class TestDynamicDebugger(unittest.TestCase):
    def test_attach_mock(self):
        dbg = DynamicDebugger()
        r = dbg.attach(pid=9999)  # 不存在进程 -> mock
        self.assertTrue(r["ok"])
        self.assertEqual(r["mode"], "mock")

    def test_breakpoint(self):
        dbg = DynamicDebugger()
        dbg.attach(pid=9999)
        r = dbg.set_breakpoint(0x401000)
        self.assertTrue(r["ok"])
        self.assertIn(0x401000, dbg.breakpoints)

    def test_remove_breakpoint(self):
        dbg = DynamicDebugger()
        dbg.attach(pid=9999)
        dbg.set_breakpoint(0x401000)
        r = dbg.remove_breakpoint(0x401000)
        self.assertTrue(r["ok"])
        self.assertEqual(dbg.breakpoints, {})

    def test_remove_missing(self):
        dbg = DynamicDebugger()
        r = dbg.remove_breakpoint(0x123)
        self.assertFalse(r["ok"])

    def test_single_step(self):
        dbg = DynamicDebugger()
        dbg.attach(pid=9999)
        r = dbg.single_step()
        self.assertTrue(r["ok"])

    def test_read_mem(self):
        dbg = DynamicDebugger()
        dbg.attach(pid=9999)
        r = dbg.read_mem(0x401000)
        self.assertTrue(r["ok"])
        self.assertIn("mock", r["detail"])

    def test_write_mem(self):
        dbg = DynamicDebugger()
        dbg.attach(pid=9999)
        r = dbg.write_mem(0x401000, 0x90)
        self.assertTrue(r["ok"])

    def test_get_regs(self):
        dbg = DynamicDebugger()
        dbg.attach(pid=9999)
        r = dbg.get_regs()
        self.assertTrue(r["ok"])
        self.assertIn("rip", r["regs"])

    def test_detach(self):
        dbg = DynamicDebugger()
        dbg.attach(pid=9999)
        r = dbg.detach()
        self.assertTrue(r["ok"])
        self.assertFalse(dbg.attached)


if __name__ == "__main__":
    unittest.main(verbosity=2)
