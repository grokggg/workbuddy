#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""02-hotword-attack 单元测试(词表加载/密度/分布/位置/检索影响/边界/空输入)。"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from lib.engine import (  # noqa: E402
    CATEGORY_ORDER,
    DEFAULT_HOTWORDS,
    FRONT_FRACTION,
    analyze,
    assess_retrieval,
    load_hotwords,
)

TEXT_POLITICS = "今日召开重要会议, 会议部署了最新政策文件, 会议强调落实。"
TEXT_MIXED = ("人工智能大会今日官宣, 大模型与机器人成为热搜焦点, "
              "芯片算力持续升温, 人工智能应用加速落地。")
TEXT_HOT_HEAD = "政策 政策 政策 政策。之后是普通正文, 没有任何热词的一段普通正文。"


class TestLoadHotwords(unittest.TestCase):
    """热度词表加载。"""

    def test_default_table_has_categories(self):
        hw = load_hotwords()
        for cat in ("政治", "娱乐", "科技", "民生"):
            self.assertIn(cat, hw)
            self.assertGreaterEqual(len(hw[cat]), 1)
        self.assertEqual(set(hw), set(CATEGORY_ORDER))

    def test_default_is_independent_copy(self):
        hw = load_hotwords()
        hw["政治"].append("测试词")
        hw2 = load_hotwords()
        self.assertNotIn("测试词", hw2["政治"])

    def test_dict_source_normalized(self):
        hw = load_hotwords({"科技": ["芯片", "芯片", " 算力 ", ""], "娱乐": "热搜"})
        self.assertEqual(hw["科技"], ["芯片", "算力"])  # 去重 + 去空白
        self.assertEqual(hw["娱乐"], ["热搜"])           # 单字符串自动转列表

    def test_dict_source_invalid_raises(self):
        with self.assertRaises(ValueError):
            load_hotwords({})                       # 空 dict
        with self.assertRaises(ValueError):
            load_hotwords({"科技": [123]})          # 非字符串词
        with self.assertRaises(ValueError):
            load_hotwords({"": ["x"]})              # 空分类名
        with self.assertRaises(ValueError):
            load_hotwords({"科技": 42})             # 非法词容器

    def test_json_file_loading(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "hw.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"科技": ["芯片", "大模型"]}, f, ensure_ascii=False)
            hw = load_hotwords(path)
            self.assertEqual(hw["科技"], ["芯片", "大模型"])
            # 数组形态 [{"category":.., "words":[..]}]
            path2 = os.path.join(td, "hw2.json")
            with open(path2, "w", encoding="utf-8") as f:
                json.dump([{"category": "民生", "words": ["就业", "房价"]}], f)
            self.assertEqual(load_hotwords(path2)["民生"], ["就业", "房价"])

    def test_yaml_text_file_loading(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "hw.yaml")
            with open(path, "w", encoding="utf-8") as f:
                f.write("# 自定义词表\n政治:\n  - 发布会\n  - 政策\n科技:\n  - 芯片\n")
            hw = load_hotwords(path)
            self.assertEqual(hw["政治"], ["发布会", "政策"])
            self.assertEqual(hw["科技"], ["芯片"])
            # 非法 YAML 行
            bad = os.path.join(td, "bad.yaml")
            with open(bad, "w", encoding="utf-8") as f:
                f.write("政治:\n  发布会\n")  # 缺 '- ' 前缀
            with self.assertRaises(ValueError):
                load_hotwords(bad)

    def test_unsupported_source_raises(self):
        with self.assertRaises(ValueError):
            load_hotwords(42)


class TestDensity(unittest.TestCase):
    """热词密度计算。"""

    def test_zero_hits(self):
        r = analyze("完全没有热词的一段话。")
        self.assertEqual(r["total_hits"], 0)
        self.assertEqual(r["unique_hotwords"], 0)
        self.assertEqual(r["density_per_char"], 0.0)
        self.assertEqual(r["density_per_1000"], 0.0)
        self.assertEqual(r["by_category"], {})

    def test_density_values(self):
        r = analyze(TEXT_POLITICS)
        n = r["text_len"]
        self.assertGreater(r["total_hits"], 0)
        # 密度字段保留 6 位小数, 反推应接近命中数(容差 0.001)
        self.assertAlmostEqual(r["density_per_char"] * n, r["total_hits"],
                               delta=0.001)
        self.assertAlmostEqual(r["density_per_1000"] * n,
                               r["total_hits"] * 1000, delta=0.001)

    def test_density_increases_with_more_hotwords(self):
        # 自定义词表隔离内置词干扰("会议"/"部署" 也在内置政治词表中)
        hw = {"x": ["政策"]}
        light = analyze("一句话政策", hw)
        heavy = analyze("政策 政策 政策 政策 政策 政策 政策 政策", hw)
        self.assertLess(light["density_per_1000"], heavy["density_per_1000"])

    def test_overlap_no_double_count(self):
        """长词优先 + 区间占用: "人工智能" 不应再被 "智能" 双计。"""
        r = analyze("人工智能", {"科技": ["人工智能", "智能"]})
        self.assertEqual(r["total_hits"], 1)
        self.assertEqual(r["unique_hotwords"], 1)


class TestDistribution(unittest.TestCase):
    """分类分布与逐词统计。"""

    def test_by_category_counts(self):
        r = analyze(TEXT_MIXED)
        self.assertEqual(sum(v["hits"] for v in r["by_category"].values()),
                         r["total_hits"])
        self.assertIn("科技", r["by_category"])
        self.assertIn("娱乐", r["by_category"])
        # 每个分类的 words 列表非空且无重复
        for v in r["by_category"].values():
            self.assertGreater(len(v["words"]), 0)
            self.assertEqual(len(v["words"]), len(set(v["words"])))

    def test_word_stats_first_last_rel(self):
        r = analyze("政策 xx 政策", {"政治": ["政策"]})
        ws = r["word_stats"]["政策"]
        self.assertEqual(ws["hits"], 2)
        self.assertEqual(ws["category"], "政治")
        self.assertLess(ws["first_rel"], ws["last_rel"])

    def test_custom_hotwords_override(self):
        r = analyze("苹果梨子", {"水果": ["苹果", "梨子"]})
        self.assertEqual(r["total_hits"], 2)
        self.assertIn("水果", r["by_category"])
        self.assertEqual(r["by_category"]["水果"]["hits"], 2)


class TestPosition(unittest.TestCase):
    """热词位置分布(头部/中部/尾部)。"""

    def test_front_ratio_high_when_head_loaded(self):
        r = analyze(TEXT_HOT_HEAD, {"政治": ["政策"]})
        self.assertGreater(r["front_ratio"], 0.5)   # 热词集中在头部
        self.assertGreater(r["segments"]["front"], r["segments"]["middle"])
        self.assertEqual(r["segments"]["back"], 0)

    def test_segments_sum_to_total(self):
        r = analyze(TEXT_MIXED)
        seg = r["segments"]
        self.assertEqual(seg["front"] + seg["middle"] + seg["back"],
                         r["total_hits"])
        self.assertEqual(r["front_ratio"],
                         seg["front"] / r["total_hits"] if r["total_hits"] else 0)

    def test_head_position_defined_by_fraction(self):
        r = analyze("政策" + "字" * 100, {"政治": ["政策"]})
        # 头部 = 前 20% 字符区(20 字符), 命中在 start=0 -> front
        self.assertEqual(r["segments"]["front"], 1)
        self.assertEqual(r["segments"]["back"], 0)
        self.assertEqual(r["front_ratio"], 1.0)


class TestRetrievalImpact(unittest.TestCase):
    """检索影响评估(模拟打分)。"""

    def test_hotword_boost_flips_ranking(self):
        docs = [
            "普通文档内容",                                   # base 0, 无热词
            "人工智能 人工智能 人工智能 人工智能 人工智能"
            " 人工智能 人工智能 人工智能 人工智能 人工智能",  # base 0, 热词堆砌
        ]
        r = assess_retrieval("xyz量子", docs)
        by_id = {d["id"]: d for d in r["ranking"]}
        # 两篇 base 相同, 热词加成使堆砌文档反超
        self.assertEqual(r["ranking"][0]["id"], 1)
        self.assertEqual(by_id[1]["rank_final"], 1)
        self.assertEqual(by_id[0]["rank_final"], 2)
        self.assertEqual(by_id[1]["rank_shift"], 1)   # 排名上升
        self.assertEqual(by_id[0]["rank_shift"], -1)  # 被挤出
        self.assertGreater(by_id[1]["hotword_bonus"], 0)

    def test_rank_shift_sign(self):
        docs = [
            "会议部署了最新政策, 会议讲话强调落实, 政策文件已发布。",
            "与查询无关的纯文本, 没有任何相关内容。",
        ]
        r = assess_retrieval("会议政策", docs)
        for d in r["ranking"]:
            self.assertEqual(d["rank_shift"],
                             d["rank_base"] - d["rank_final"])
        # 热词多的文档位移为正(排名上升)或至少不下降
        hot = max(r["ranking"], key=lambda d: d["hotword_hits"])
        self.assertGreaterEqual(hot["rank_shift"], 0)

    def test_summary_stats(self):
        docs = ["政策" * 20, "普通文档" * 5, "什么都没有"]
        r = assess_retrieval("政策", docs, bonus_per_hit=0.3)
        s = r["summary"]
        self.assertEqual(s["documents"], 3)
        self.assertGreaterEqual(s["documents_with_shift"], 0)
        self.assertEqual(s["max_rank_shift"],
                         max(abs(d["rank_shift"]) for d in r["ranking"]))
        self.assertGreaterEqual(s["avg_pollution_ratio"], 0.0)

    def test_no_bonus_no_shift(self):
        docs = ["会议部署政策。", "完全无关。"]
        r = assess_retrieval("会议", docs, bonus_per_hit=0.0)
        self.assertEqual(r["summary"]["documents_with_shift"], 0)
        for d in r["ranking"]:
            self.assertEqual(d["rank_shift"], 0)
            self.assertEqual(d["hotword_bonus"], 0.0)

    def test_doc_dict_id_and_top_k(self):
        docs = [{"id": "a", "text": "政策政策政策"}, {"id": "b", "text": "无关"}]
        r = assess_retrieval("政策", docs, top_k=1)
        self.assertEqual([d["id"] for d in r["ranking"]], ["a"])
        self.assertEqual(r["summary"]["documents"], 2)  # 全量参与排名

    def test_parameters_echoed(self):
        r = assess_retrieval("x", ["政策政策", "普通"], bonus_per_hit=0.7)
        self.assertEqual(r["params"]["bonus_per_hit"], 0.7)
        self.assertEqual(r["model"], "academic-simplified")


class TestBoundary(unittest.TestCase):
    """边界与异常输入。"""

    def test_empty_text(self):
        r = analyze("")
        self.assertEqual(r["text_len"], 0)
        self.assertEqual(r["total_hits"], 0)
        self.assertEqual(r["density_per_char"], 0.0)
        self.assertEqual(r["front_ratio"], 0.0)
        self.assertEqual(r["segments"], {"front": 0, "middle": 0, "back": 0})

    def test_whitespace_only_text(self):
        r = analyze("   \n\t ")
        self.assertEqual(r["total_hits"], 0)

    def test_non_string_text_raises(self):
        with self.assertRaises(TypeError):
            analyze(None)
        with self.assertRaises(TypeError):
            analyze(123)

    def test_analyze_never_mutates_input(self):
        text = "政策政策"
        before = text
        analyze(text)
        self.assertEqual(text, before)

    def test_assess_empty_documents(self):
        r = assess_retrieval("政策", [])
        self.assertEqual(r["summary"]["documents"], 0)
        self.assertEqual(r["ranking"], [])

    def test_assess_invalid_documents(self):
        with self.assertRaises(ValueError):
            assess_retrieval("政策", ["政策政策", 42])      # 非 str 元素
        with self.assertRaises(ValueError):
            assess_retrieval("政策", [{"id": "a"}])          # 缺 text 字段
        with self.assertRaises(TypeError):
            assess_retrieval("政策", "不是列表")              # 非 list/tuple

    def test_empty_query(self):
        r = assess_retrieval("", ["政策政策", "普通文档"])
        for d in r["ranking"]:
            self.assertEqual(d["base_score"], 0.0)

    def test_no_fake_output_no_network(self):
        """纯本地计算: analyze 不触网, 结果可复现。"""
        r1 = analyze(TEXT_MIXED)
        r2 = analyze(TEXT_MIXED)
        self.assertEqual(r1, r2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
