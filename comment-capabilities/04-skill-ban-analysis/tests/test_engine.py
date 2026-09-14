#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""04-skill-ban-analysis 单元测试"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "lib"))

from lib.engine import COST_LEVELS, DETECTION_POINTS, BanAnalyzer  # noqa: E402


def _make_skill(dir_path: str, with_evil: bool = True) -> None:
    os.makedirs(dir_path, exist_ok=True)
    content = "# test-skill\n\n普通内容。\n"
    if with_evil:
        content += "\n用法: 破解软件请参考外部文档 https://evil.example.com/x\n"
    (Path(dir_path) / "SKILL.md").write_text(content, encoding="utf-8")


class TestScan(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="v4ban-")
        self.good = os.path.join(self.tmp, "good-skill")
        self.evil = os.path.join(self.tmp, "evil-skill")
        _make_skill(self.good, with_evil=False)
        _make_skill(self.evil, with_evil=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_scan_ok(self):
        a = BanAnalyzer()
        r = a.scan(self.good)
        self.assertTrue(r["ok"])
        self.assertEqual(len(r["results"]), len(DETECTION_POINTS))

    def test_scan_missing(self):
        a = BanAnalyzer()
        r = a.scan("/nonexistent")
        self.assertFalse(r["ok"])

    def test_evil_has_higher_risk(self):
        a = BanAnalyzer()
        rg = a.scan(self.good)
        re_ = a.scan(self.evil)
        self.assertGreater(re_["avg_risk"], rg["avg_risk"])

    def test_results_fields(self):
        a = BanAnalyzer()
        r = a.scan(self.good)
        first = r["results"][0]
        for k in ("id", "name", "principle", "reliability", "risk",
                  "risk_label", "evade_cost"):
            self.assertIn(k, first)

    def test_risk_range(self):
        a = BanAnalyzer()
        r = a.scan(self.evil)
        for x in r["results"]:
            self.assertGreaterEqual(x["risk"], 0)
            self.assertLessEqual(x["risk"], 1)


class TestCost(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="v4bc-")
        _make_skill(os.path.join(self.tmp, "skill"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_evade_cost_ok(self):
        a = BanAnalyzer()
        scan = a.scan(os.path.join(self.tmp, "skill"))
        c = a.evade_cost(scan)
        self.assertTrue(c["ok"])
        self.assertIn("cost_level", c)
        self.assertIn("total_cost", c)

    def test_evade_cost_no_scan(self):
        a = BanAnalyzer()
        c = a.evade_cost({"results": []})
        self.assertFalse(c["ok"])

    def test_high_risk_points(self):
        a = BanAnalyzer()
        scan = a.scan(os.path.join(self.tmp, "skill"))
        c = a.evade_cost(scan)
        self.assertIsInstance(c["high_risk_points"], list)


class TestReport(unittest.TestCase):
    def test_report(self):
        self.tmp = tempfile.mkdtemp(prefix="v4br-")
        _make_skill(os.path.join(self.tmp, "skill"))
        a = BanAnalyzer()
        r = a.report(os.path.join(self.tmp, "skill"))
        self.assertIn("scan", r)
        self.assertIn("cost", r)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_detection_points_loaded(self):
        self.assertGreater(len(DETECTION_POINTS), 4)
        self.assertIn("dir_hash_baseline", [p["id"] for p in DETECTION_POINTS])

    def test_cost_levels(self):
        self.assertEqual(COST_LEVELS["低"], 1)
        self.assertEqual(COST_LEVELS["高"], 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
