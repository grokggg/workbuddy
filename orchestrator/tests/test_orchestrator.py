#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M33 测试: 编排器 + 纯 Python 替代 + 扩展攻击面 + LLM 推理。"""
from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent  # orchestrator/
sys.path.insert(0, str(HERE))


class TestOrchestrator(unittest.TestCase):
    def test_workflow_exists(self):
        self.assertTrue((HERE / "analyze.yml").exists())

    def test_trigger_script(self):
        import trigger_workflow
        self.assertTrue(hasattr(trigger_workflow, "trigger"))

    def test_poll_script(self):
        import poll_workflow
        self.assertTrue(hasattr(poll_workflow, "poll"))

    def test_symbolic_solves_cm01(self):
        """纯 Python 符号执行求解 cm01 密码。"""
        from pure_python_symbolic import SymbolicEngine
        cm = HERE.parent / "real-crackmes" / "cm01"
        if not cm.exists():
            self.skipTest("cm01 不存在")
        eng = SymbolicEngine(str(cm))
        rep = eng.report()
        s = rep["solve"]
        self.assertTrue(s.get("solvable"))
        self.assertEqual(s.get("password"), "p")

    def test_symbolic_solves_cm09(self):
        """cm09 密码 Z。"""
        from pure_python_symbolic import SymbolicEngine
        cm = HERE.parent / "real-crackmes" / "cm09"
        if not cm.exists():
            self.skipTest("cm09 不存在")
        eng = SymbolicEngine(str(cm))
        s = eng.report()["solve"]
        self.assertTrue(s.get("solvable"))
        self.assertEqual(s.get("password"), "Z")

    def test_llm_symbolic_solves_2(self):
        """LLM 推理引擎求解 ≥2 个 crackme。"""
        from llm_symbolic import disasm_target, rule_reason
        solved = 0
        for name, expect in [("cm01", "p"), ("cm02", "o"), ("cm09", "Z")]:
            cm = HERE.parent / "real-crackmes" / name
            if not cm.exists():
                continue
            d = disasm_target(str(cm))
            rs = rule_reason(d)
            if rs and rs[0].get("密码") == expect:
                solved += 1
        self.assertGreaterEqual(solved, 2)

    def test_pyc_roundtrip(self):
        """pyc 生成 + 反编译 + patch 验证。"""
        import marshal
        import tempfile
        work = tempfile.mkdtemp(prefix="m33-pyc-")
        pyc = os.path.join(work, "t.pyc")
        code = compile("def check(k):\n    return k == 'abc123'\n",
                       "t", "exec")
        with open(pyc, "wb") as f:
            f.write(b"\x00" * 16)
            f.write(marshal.dumps(code))
        # 反编译
        d = open(pyc, "rb").read()
        c = marshal.loads(d[16:])
        # patch: 改常量(递归处理嵌套函数)
        import types as _types

        def patch_code(c):
            new_consts = []
            for const in c.co_consts:
                if isinstance(const, str) and const == "abc123":
                    new_consts.append("x")
                else:
                    new_consts.append(const)
                if isinstance(const, _types.CodeType):
                    new_consts[-1] = patch_code(const)
            return c.replace(co_consts=tuple(new_consts))
        nc = patch_code(c)
        out = os.path.join(work, "t_patched.pyc")
        with open(out, "wb") as f:
            f.write(b"\x00" * 16)
            f.write(marshal.dumps(nc))
        # 验证
        d2 = open(out, "rb").read()
        c2 = marshal.loads(d2[16:])
        ns = {}
        exec(c2, ns)
        self.assertTrue(ns["check"]("x"))
        self.assertFalse(ns["check"]("abc123"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
