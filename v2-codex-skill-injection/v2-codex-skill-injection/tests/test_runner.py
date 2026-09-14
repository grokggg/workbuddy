#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
runner.py 单元测试 —— 六段链执行引擎

覆盖:
  - 段1 目标定位(存在/不存在/非目录)
  - 段2 根目录探测(空/非空)
  - 段3 版本目录(版本号优先/退化)
  - 段4 工具链检查(node/npm/npx)
  - 段5 asar 定位(存在/缺失)
  - 段6 输出目录(创建)
  - 全链执行与报告

跑法: python3 tests/test_runner.py
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

from lib.runner import ChainRunner, _fmt_size, work_dir  # noqa: E402


class TestFormat(unittest.TestCase):
    def test_fmt_size(self):
        self.assertEqual(_fmt_size(0), "0.0B")
        self.assertEqual(_fmt_size(1023), "1023.0B")
        self.assertEqual(_fmt_size(2048), "2.0KB")
        self.assertEqual(_fmt_size(None), "?")

    def test_work_dir(self):
        d = work_dir(base="/tmp", date="2026-09-14")
        self.assertEqual(d, "/tmp/Documents/Codex/2026-09-14/work")


class TestChain(unittest.TestCase):
    def setUp(self):
        # 造一个假目标: tmp/app/x64/4.2.0/resources/app.asar
        self.tmp = tempfile.mkdtemp(prefix="v2runner-")
        app = Path(self.tmp) / "app"
        ver = app / "x64" / "4.2.0"
        res = ver / "resources"
        res.mkdir(parents=True)
        (res / "app.asar").write_bytes(b"x" * 2048)
        self.app_root = str(app)
        self.ver_dir = str(ver)
        self.asar = str(res / "app.asar")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_locate_ok(self):
        r = ChainRunner(self.app_root)
        s = r.stage_locate()
        self.assertTrue(s["ok"])
        self.assertIn(self.app_root, s["detail"])

    def test_locate_missing(self):
        r = ChainRunner("/nonexistent")
        s = r.stage_locate()
        self.assertFalse(s["ok"])

    def test_locate_not_dir(self):
        f = Path(self.tmp) / "file.txt"
        f.write_text("x")
        r = ChainRunner(str(f))
        s = r.stage_locate()
        self.assertFalse(s["ok"])

    def test_root_lists(self):
        r = ChainRunner(self.app_root)
        s = r.stage_root()
        self.assertTrue(s["ok"])
        self.assertIn("x64", s["detail"])

    def test_version_finds_numeric(self):
        r = ChainRunner(self.app_root)
        s = r.stage_version()
        self.assertTrue(s["ok"])
        self.assertEqual(r.version_dir, self.ver_dir)

    def test_version_fallback(self):
        # 无版本号目录 -> 取首个子目录
        tmp2 = tempfile.mkdtemp(prefix="v2runner2-")
        (Path(tmp2) / "sub").mkdir()
        r = ChainRunner(tmp2)
        s = r.stage_version()
        self.assertTrue(s["ok"])
        self.assertEqual(r.version_dir, str(Path(tmp2) / "sub"))
        import shutil
        shutil.rmtree(tmp2, ignore_errors=True)

    def test_toolchain(self):
        r = ChainRunner(self.app_root)
        s = r.stage_toolchain()
        # node 存在时 ok; 缺 node 也返回结构(不抛)
        self.assertIn("node=", s["detail"])
        self.assertIn("npm=", s["detail"])

    def test_asar_found(self):
        r = ChainRunner(self.app_root)
        r.stage_version()
        s = r.stage_asar()
        self.assertTrue(s["ok"])
        self.assertEqual(r.asar_path, self.asar)
        self.assertIn("2.0KB", s["detail"])

    def test_asar_missing(self):
        tmp2 = tempfile.mkdtemp(prefix="v2runner3-")
        (Path(tmp2) / "app").mkdir()
        r = ChainRunner(str(Path(tmp2) / "app"))
        r.stage_version()
        s = r.stage_asar()
        self.assertFalse(s["ok"])

    def test_output_creates(self):
        out = str(Path(self.tmp) / "out")
        r = ChainRunner(self.app_root, out_dir=out)
        s = r.stage_output()
        self.assertTrue(s["ok"])
        self.assertTrue(os.path.isdir(out))

    def test_run_all(self):
        r = ChainRunner(self.app_root)
        stages = r.run_all()
        self.assertEqual(len(stages), 6)
        ok = sum(1 for s in stages if s["ok"])
        # locate/root/version/output 必过; toolchain 看环境; asar 过
        self.assertGreaterEqual(ok, 4)

    def test_report_text(self):
        r = ChainRunner(self.app_root)
        txt = r.report_text()
        self.assertIn("[1/6]", txt)
        self.assertIn("[6/6]", txt)
        self.assertIn("通过", txt)


if __name__ == "__main__":
    unittest.main(verbosity=2)
