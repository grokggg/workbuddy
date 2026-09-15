#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""06-context-injection 测试(评论区 SOURCE.md 行 2-3)。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODULE_DIR = HERE.parent  # 06-context-injection/
sys.path.insert(0, str(MODULE_DIR))
sys.path.insert(0, str(HERE))

import importlib.util  # noqa: E402


def _load_cli():
    import sys as _sys
    spec = importlib.util.spec_from_file_location("ci_cli", MODULE_DIR / "cli.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    _sys.modules["ci_cli"] = mod
    spec.loader.exec_module(mod)
    return mod


ci = _load_cli()
ContextInjectionEngine = ci.ContextInjectionEngine


class TestContextInjection(unittest.TestCase):
    def setUp(self):
        self.eng = ContextInjectionEngine()

    def test_global_persona(self):
        b = self.eng.global_persona("助手", "你是助手")
        self.assertEqual(b.scope, "global")
        self.assertEqual(b.source_line, 2)  # SOURCE.md 行 2

    def test_project_sample(self):
        b = self.eng.project_sample("样例", "输入→输出")
        self.assertEqual(b.scope, "project")
        self.assertEqual(b.source_line, 2)

    def test_render_contains_both(self):
        blocks = [
            self.eng.global_persona("助手", "你是助手"),
            self.eng.project_sample("样例", "输入→输出"),
        ]
        text = self.eng.render(blocks)
        self.assertIn("(global)", text)
        self.assertIn("(project)", text)

    def test_write_dry_run(self):
        blocks = [self.eng.global_persona("助手", "你是助手")]
        r = self.eng.write(blocks, dry=True)
        self.assertTrue(r["dry"])
        self.assertEqual(r["blocks"], 1)

    def test_write_real(self):
        import tempfile
        tmp = tempfile.mkdtemp(prefix="ci-")
        blocks = [self.eng.global_persona("助手", "你是助手")]
        r = self.eng.write(blocks, path=str(Path(tmp) / "AGENTS.md"), dry=False)
        self.assertFalse(r["dry"])
        self.assertTrue(Path(r["path"]).exists())


if __name__ == "__main__":
    unittest.main()
