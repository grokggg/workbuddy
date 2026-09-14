#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v6-skill-router 单元测试

覆盖:
  - 路由表加载
  - 归一化
  - 路由决策(命中/冲突消解/兜底)
  - iv8 引擎接口 mock 后端行为契约
  - 案例回血(写案例 + 更新 taxonomy)

跑法: python3 tests/test_router.py
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "lib"))

from lib.router import (  # noqa: E402
    CaseRegen,
    MockIV8Backend,
    create_backend,
    load_router_table,
    normalize_text,
    route,
)

TABLE = HERE / "router_table.yaml"


class TestNormalize(unittest.TestCase):
    def test_nfkc_lower(self):
        self.assertEqual(normalize_text("ＣＯＬＤ　ＢＲＥＷ"), "coldbrew")

    def test_strip_punct(self):
        self.assertEqual(normalize_text("极验 GT4 滑块,走 gt4!"), "极验gt4滑块走gt4")

    def test_empty(self):
        self.assertEqual(normalize_text(""), "")


class TestLoadTable(unittest.TestCase):
    def test_load(self):
        t = load_router_table(TABLE)
        self.assertIn("skills", t)
        self.assertEqual(t.get("version"), 6)

    def test_missing_file(self):
        from lib.router import RouterTableError
        with self.assertRaises(RouterTableError):
            load_router_table("/nonexistent.yaml")


class TestRoute(unittest.TestCase):
    def setUp(self):
        self.table = load_router_table(TABLE)

    def test_iv8_route(self):
        d = route("用 iv8 补环境, 生成紧凑 Python 脚本回放请求", self.table)
        self.assertEqual(d.winner, "v8-web-reverse")

    def test_find_entry(self):
        d = route("帮我定位 sign 参数的加密入口", self.table)
        self.assertEqual(d.winner, "find-crypto-entry")

    def test_rs(self):
        d = route("瑞数 412, 走 rs-reverse", self.table)
        self.assertEqual(d.winner, "rs-reverse")

    def test_ast(self):
        d = route("AST 解混淆 obfuscator.io 脚本", self.table)
        self.assertEqual(d.winner, "ast-deobfuscate")

    def test_gt4_priority(self):
        # 极验同时带 iv8 词, 应路由到专项 gt4(优先级更高)
        d = route("极验 GT4 滑块用 iv8 补环境", self.table)
        self.assertEqual(d.winner, "gt4-protocol-reverse")

    def test_fallback(self):
        d = route("今天天气怎么样", self.table)
        self.assertEqual(d.winner, "skill-creator")

    def test_default_empty(self):
        d = route("", self.table)
        self.assertEqual(d.winner, "skill-creator")


class TestMockBackend(unittest.TestCase):
    def test_contract(self):
        with MockIV8Backend() as be:
            ua = be.eval("navigator.userAgent")
            self.assertTrue(ua.startswith("Mozilla/5.0"))
            be.load_page("http://x/",
                         "<html><script>document.cookie='__sign=zzz'</script></html>")
            be.advance(3000)
            self.assertIn("zzz", be.get_cookie())
            self.assertGreaterEqual(len(be.netlog()), 1)
            self.assertTrue(be.trusted_input("pointerdown", clientX=1, clientY=2))

    def test_factory_auto_falls_back_to_mock(self):
        # 无 iv8 环境 -> auto 应落到 mock
        be = create_backend("auto")
        self.assertEqual(be.name, "mock")


class TestCaseRegen(unittest.TestCase):
    def test_write_and_taxonomy(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "v8-web-reverse"
            (root / "references").mkdir(parents=True)
            regen = CaseRegen(root)
            out = regen.sync("js-challenges", "test-case",
                             "def main():\n    pass\n", "测试案例",
                             {"source": "unittest"})
            self.assertTrue(Path(out["case"]).exists())
            self.assertTrue(Path(out["taxonomy"]).exists())
            self.assertIn("test-case",
                          Path(out["taxonomy"]).read_text(encoding="utf-8"))

    def test_bad_category(self):
        with tempfile.TemporaryDirectory() as td:
            regen = CaseRegen(Path(td))
            with self.assertRaises(ValueError):
                regen.write_case("hacks", "x", "code")

    def test_bad_slug(self):
        with tempfile.TemporaryDirectory() as td:
            regen = CaseRegen(Path(td))
            with self.assertRaises(ValueError):
                regen.write_case("captcha", "BAD SLUG!!", "code")


if __name__ == "__main__":
    unittest.main(verbosity=2)
