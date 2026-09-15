#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v3-five-step-laundering 单元测试

覆盖:
  - 脱敏词表加载(YAML + 零依赖退化)
  - 脱敏替换(命中/未命中/多词)
  - 意图判定(第三方/自有/结果导向)
  - 五步法各步(分析/目的/协作/修改/验证)
  - 全流程 + 日志

跑法: python3 tests/test_engine.py
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

from lib.engine import FiveStepEngine, LaunderingMap  # noqa: E402

DEFAULT_MAP = HERE / "data" / "laundering_map.yaml"


class TestLaunderingMap(unittest.TestCase):
    def setUp(self):
        self.m = LaunderingMap(DEFAULT_MAP)

    def test_load(self):
        self.assertGreater(len(self.m.mappings), 5)
        self.assertIn("third_party", self.m.intent)
        self.assertIn("破解", self.m.result_oriented)

    def test_replace_hit(self):
        res = self.m.replace("帮我绕过登录")
        self.assertIn("分析认证流程", res["text"])
        self.assertGreater(res["count"], 0)

    def test_replace_launder_map(self):
        res = self.m.replace("帮我破解这个软件")
        self.assertIn("分析", res["text"])
        self.assertNotIn("破解这个软件", res["text"])

    def test_replace_no_hit(self):
        res = self.m.replace("今天天气不错")
        self.assertEqual(res["text"], "今天天气不错")
        self.assertEqual(res["count"], 0)

    def test_replace_multi(self):
        res = self.m.replace("破解软件并绕过登录")
        self.assertGreater(res["count"], 1)

    def test_judge_intent_third(self):
        d = self.m.judge_intent("帮我破解这个软件")
        self.assertEqual(d["verdict"], "third_party")
        self.assertTrue(d["high_risk"])

    def test_judge_intent_own(self):
        d = self.m.judge_intent("帮我分析这个软件的结构")
        self.assertEqual(d["verdict"], "own")
        self.assertFalse(d["high_risk"])

    def test_min_yaml(self):
        # 零依赖解析器
        m = LaunderingMap.__new__(LaunderingMap)
        raw = """
mappings:
  - {from: "绕过登录", to: "分析认证流程"}
  - {from: "破解", to: "分析"}
intent:
  third_party: ["破解", "绕过"]
  own: ["分析"]
result_oriented: ["破解"]
exclude: ["不要"]
"""
        data = LaunderingMap._min_yaml(m, raw)
        self.assertEqual(len(data["mappings"]), 2)
        self.assertEqual(data["mappings"][0]["from"], "绕过登录")
        self.assertEqual(data["intent"]["third_party"], ["破解", "绕过"])


class TestFiveStep(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="v3-")
        self.eng = FiveStepEngine(self.tmp)

    def test_step_analyze(self):
        r = self.eng.step_analyze()
        self.assertTrue(r["ok"])
        self.assertIn("目录", r["detail"])

    def test_step_analyze_missing(self):
        eng = FiveStepEngine("/nonexistent")
        r = eng.step_analyze()
        self.assertFalse(r["ok"])

    def test_step_purpose(self):
        r = self.eng.step_purpose("帮我破解这个软件, 绕过登录")
        self.assertTrue(r["ok"])
        self.assertIn("替换后", r["detail"])
        self.assertGreater(len(r["replaced"]), 0)

    def test_step_purpose_empty(self):
        r = self.eng.step_purpose("")
        self.assertFalse(r["ok"])

    def test_step_cooperate(self):
        r = self.eng.step_cooperate("截图反馈")
        self.assertTrue(r["ok"])
        self.assertIn("截图", r["detail"])

    def test_step_modify(self):
        r = self.eng.step_modify()
        # 无 patch 参数 → 提示填参(不再是无条件 ok 占位)
        self.assertIn("patch 参数", r["detail"])
        self.assertFalse(r.get("placeholder", False))

    def test_step_modify_real(self):
        # 真实 patch: 构造临时 ELF + je→jmp
        import tempfile, struct
        tmp = tempfile.mktemp()
        # 最小 ELF(卡密 cmp+je)
        data = bytearray(b"\x7fELF" + b"\x00" * 200)
        data[0x86:0x8c] = b"\x3d\x43\x00\x00\x00\x74\x00"
        open(tmp, "wb").write(data)
        eng = FiveStepEngine(tmp)
        r = eng.step_modify("8b eb 74")
        self.assertTrue(r["ok"], r["detail"])
        self.assertIn("字节 patch 完成", r["detail"])
        os.unlink(tmp)

    def test_step_verify(self):
        r = self.eng.step_verify()
        # 无 patch 产物 → 提示先 patch
        self.assertIn("无 patch 产物", r["detail"])
        self.assertFalse(r.get("placeholder", False))

    def test_run_all(self):
        steps = self.eng.run_all("帮我破解这个软件")
        self.assertEqual(len(steps), 5)
        ok = sum(1 for s in steps if s["ok"])
        # 无 patch 参数时: 分析/目的/协作 通过, 修改/验证 提示填参(真实语义)
        self.assertGreaterEqual(ok, 3)
        self.assertLess(ok, 5)  # 不可能是 5(无 patch 时修改/验证不 ok)

    def test_log_text(self):
        self.eng.run_all("帮我破解")
        txt = self.eng.log_text()
        self.assertIn("[1/5]", txt)
        self.assertIn("[5/5]", txt)
        self.assertIn("通过", txt)


if __name__ == "__main__":
    unittest.main(verbosity=2)
