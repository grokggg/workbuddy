#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lib/llm_engine.py 单元测试"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "lib"))

from lib.llm_engine import BYPASS_KB, LLMAnalyzer, LLMClient  # noqa: E402


class TestLLMClient(unittest.TestCase):
    def test_backend_defaults(self):
        c = LLMClient()
        self.assertEqual(c.backend, "ollama")
        self.assertIn("11434", c.base_url)

    def test_llama_backend(self):
        c = LLMClient(backend="llama")
        self.assertEqual(c.backend, "llama")
        self.assertIn("8080", c.base_url)

    def test_available_false_no_server(self):
        # 无本地服务 -> False(不抛异常)
        c = LLMClient()
        self.assertFalse(c.available())


class TestLLMAnalyzer(unittest.TestCase):
    def setUp(self):
        self.ana = LLMAnalyzer(LLMClient())
        self.ana.llm_available = False  # 强制规则推理

    def test_extract_protections_upx(self):
        recon = {"packer": {"packed": True, "verdict": "加壳",
                            "markers": ["UPX"]}}
        cats = self.ana._extract_protections(recon)
        self.assertIn("加壳(UPX)", cats)

    def test_extract_protections_vmp(self):
        recon = {"packer": {"packed": True, "verdict": "加壳",
                            "markers": ["VMProtect"]}}
        cats = self.ana._extract_protections(recon)
        self.assertIn("加壳(VMProtect/Themida)", cats)

    def test_extract_protections_multi(self):
        recon = {
            "packer": {"packed": True, "verdict": "加壳", "markers": ["UPX"]},
            "antidebug": {"detected": ["IsDebuggerPresent"]},
            "antivm": {"detected": ["CPUID 指令"]},
            "integrity": {"detected": ["checksum"]},
            "anti_repack": {"detected": ["asar"]},
        }
        cats = self.ana._extract_protections(recon)
        self.assertEqual(len(cats), 5)

    def test_rule_reason_sorted(self):
        recon = {
            "packer": {"packed": True, "verdict": "加壳", "markers": ["UPX"]},
            "antidebug": {"detected": ["IsDebuggerPresent"]},
            "antivm": {"detected": ["CPUID 指令"]},
        }
        cats = self.ana._extract_protections(recon)
        strategies = self.ana._rule_reason(cats)
        # 按可行性降序
        feas = [s["可行性"] for s in strategies]
        self.assertEqual(feas, sorted(feas, reverse=True))
        # UPX 0.9 应排最前
        self.assertEqual(strategies[0]["protection"], "加壳(UPX)")

    def test_rule_reason_has_fields(self):
        cats = ["反调试"]
        strategies = self.ana._rule_reason(cats)
        s = strategies[0]
        for k in ("protection", "思路", "伪代码", "可行性", "工具链", "理由"):
            self.assertIn(k, s)
        self.assertEqual(s["来源"], "规则推理")

    def test_analyze_no_llm(self):
        recon = {"packer": {"packed": True, "verdict": "加壳",
                            "markers": ["UPX"]}}
        rep = self.ana.analyze(recon, target="test.exe")
        self.assertIn("规则推理", rep["engine"])
        self.assertIn("strategies", rep)
        self.assertIn("script_skeleton", rep)
        self.assertIn("UPX", rep["script_skeleton"])

    def test_analyze_empty(self):
        rep = self.ana.analyze({}, target="x")
        self.assertEqual(rep["protections"], [])
        self.assertEqual(rep["strategies"], [])

    def test_script_skeleton_structure(self):
        recon = {"packer": {"packed": True, "verdict": "加壳",
                            "markers": ["UPX"]}}
        rep = self.ana.analyze(recon, target="demo.exe")
        sk = rep["script_skeleton"]
        self.assertIn("#!/usr/bin/env python3", sk)
        self.assertIn("def strategy_1", sk)
        self.assertIn("TARGET = \"demo.exe\"", sk)

    def test_kb_coverage(self):
        """知识库应覆盖 5 类主要保护。"""
        self.assertIn("加壳(UPX)", BYPASS_KB)
        self.assertIn("加壳(VMProtect/Themida)", BYPASS_KB)
        self.assertIn("反调试", BYPASS_KB)
        self.assertIn("反VM", BYPASS_KB)
        self.assertIn("完整性校验", BYPASS_KB)
        self.assertIn("反重打包", BYPASS_KB)


if __name__ == "__main__":
    unittest.main(verbosity=2)
