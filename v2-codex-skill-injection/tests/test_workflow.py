# -*- coding: utf-8 -*-
"""lib/workflow.py 单元测试：激活匹配 / 自读 / 六段链 / 输出规范

全离线。跑法：python3 tests/test_workflow.py
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from lib import workflow as W  # noqa: E402
from lib import injector as I  # noqa: E402


# ---------------------------------------------------------------- 归一化
class TestNormalize(unittest.TestCase):
    def test_fullwidth_to_halfwidth(self):
        self.assertEqual(W.normalize("ＣＯＬＤ　ＢＲＥＷ"), "coldbrew")

    def test_case_insensitive(self):
        self.assertEqual(W.normalize("ColdBrew"), "coldbrew")

    def test_strip_spaces_and_punct(self):
        self.assertEqual(W.normalize("cold brew"), "coldbrew")
        self.assertEqual(W.normalize("cold-brew"), "coldbrew")
        self.assertEqual(W.normalize("冷咖啡！"), "冷咖啡")

    def test_empty(self):
        self.assertEqual(W.normalize(None), "")
        self.assertEqual(W.normalize(""), "")

    def test_chinese_punct(self):
        self.assertEqual(W.normalize("「冷咖啡」"), "冷咖啡")


# ---------------------------------------------------------------- 激活匹配
class TestActivation(unittest.TestCase):
    def setUp(self):
        self.m = W.ActivationMatcher()

    def test_primary_triggers(self):
        for u in ("冷咖啡", "cold brew", "coldbrew", "ColdBrew",
                  "cold-brew", "veni-coldbrew", "冷咖啡模式"):
            r = self.m.match(u)
            self.assertEqual(r["decision"], "trigger", u)
            self.assertGreaterEqual(r["score"], W.THRESHOLD, u)

    def test_fullwidth_trigger(self):
        self.assertTrue(self.m.would_trigger("ＣＯＬＤ　ＢＲＥＷ"))

    def test_embedded_in_sentence(self):
        self.assertTrue(self.m.would_trigger("我要用冷咖啡看看这个 app"))

    def test_non_trigger(self):
        for u in ("帮我看看这个 app", "今天天气不错", "ls -la", ""):
            self.assertEqual(self.m.match(u)["decision"], "no", u)

    def test_weak_signal(self):
        """「咖啡」太泛，单独出现不足以触发。"""
        r = self.m.match("咖啡")
        self.assertEqual(r["decision"], "weak")
        self.assertLess(r["score"], W.THRESHOLD)
        self.assertIn("可能仍会触发", r["reason"])

    def test_negation_suppresses(self):
        for u in ("不要冷咖啡", "别用冷咖啡", "取消冷咖啡模式",
                  "no coldbrew", "disable cold brew"):
            r = self.m.match(u)
            self.assertEqual(r["decision"], "no", u)
            self.assertIn("否定", r["reason"])

    def test_negation_keeps_score_visible(self):
        """被否定时分值仍要能看到 —— 否则不知道是被压制还是没命中。"""
        r = self.m.match("不要冷咖啡")
        self.assertGreater(r["score"], 0)
        self.assertEqual(r["decision"], "no")

    def test_reason_is_informative(self):
        r = self.m.match("冷咖啡")
        self.assertIn("冷咖啡", r["reason"])
        self.assertIn("阈值", r["reason"])

    def test_candidates_sorted_desc(self):
        r = self.m.match("冷咖啡模式")
        scores = [c["score"] for c in r["candidates"]]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_custom_trigger(self):
        m = W.ActivationMatcher(triggers={"测试词": 1.0})
        self.assertTrue(m.would_trigger("测试词"))
        self.assertFalse(m.would_trigger("冷咖啡"))

    def test_custom_threshold(self):
        m = W.ActivationMatcher(threshold=0.99)
        self.assertFalse(m.would_trigger("冷咖啡模式"))  # 0.869 < 0.99


# ---------------------------------------------------------------- 自读
class TestSelfRead(unittest.TestCase):
    def test_powershell_command(self):
        c = W.self_read_command("/x/SKILL.md", "powershell")
        self.assertIn("Get-Content", c)
        self.assertIn("/x/SKILL.md", c)

    def test_posix_command(self):
        c = W.self_read_command("/x/SKILL.md", "posix")
        self.assertTrue(c.startswith("cat "))
        self.assertIn("/x/SKILL.md", c)

    def test_default_platform(self):
        c = W.self_read_command("/x/SKILL.md")
        self.assertTrue(c)

    def test_verify_hit(self):
        ok, _ = W.verify_self_read("自读探针：VCP-ABC12345", "VCP-ABC12345")
        self.assertTrue(ok)

    def test_verify_miss(self):
        ok, _ = W.verify_self_read("VCP-DEADBEEF", "VCP-ABC12345")
        self.assertFalse(ok)


# ---------------------------------------------------------------- 六段链
class TestChain(unittest.TestCase):
    def test_six_stages(self):
        for pf in ("posix", "powershell"):
            c = W.render_chain("/opt/app", "/tmp/out", platform=pf)
            self.assertEqual(len(c["stages"]), 6, pf)
            self.assertEqual([s["index"] for s in c["stages"]],
                             [1, 2, 3, 4, 5, 6])
            self.assertEqual([s["key"] for s in c["stages"]],
                             [k for k, _, _ in W.STAGES])

    def test_every_stage_has_command_and_desc(self):
        c = W.render_chain("/opt/app", "/tmp/out")
        for s in c["stages"]:
            self.assertTrue(s["command"].strip(), s["key"])
            self.assertTrue(s["label"], s["key"])
            self.assertTrue(s["desc"], s["key"])

    def test_powershell_uses_literalpath(self):
        """视频里的链全程 -LiteralPath —— 不用 -Path，避免通配符踩坑。"""
        c = W.render_chain("/opt/app", "/tmp/out", platform="powershell")
        txt = W.render_chain_text(c)
        self.assertIn("-LiteralPath", txt)
        self.assertIn("$ErrorActionPreference", txt)

    def test_toolchain_then_strict(self):
        """先 SilentlyContinue（工具链可能没装），再 Stop（路径必须存在）。"""
        c = W.render_chain("/opt/app", "/tmp/out", platform="powershell")
        by_key = {s["key"]: s["command"] for s in c["stages"]}
        self.assertIn("SilentlyContinue", by_key["toolchain"])
        self.assertIn("Stop", by_key["asar"])

    def test_no_cracking_verbs(self):
        """生成的链里不能出现破解/去卡密类动作。"""
        for pf in ("posix", "powershell"):
            txt = W.render_chain_text(
                W.render_chain("/opt/app", "/tmp/out", platform=pf)).lower()
            for bad in ("crack", "patch", "注册机", "激活码", "去卡密"):
                self.assertNotIn(bad, txt, "%s / %s" % (pf, bad))

    def test_tail_only_inspect(self):
        """收尾只调 list/info/extract，不做 pack/写回。"""
        c = W.render_chain("/opt/app", "/tmp/out")
        tail = " ".join(c["tail"])
        for act in ("info", "list", "extract"):
            self.assertIn(act, tail)
        self.assertNotIn("pack", tail.replace("package", ""))

    def test_custom_asar_rel(self):
        c = W.render_chain("/opt/app", "/tmp/out", platform="posix",
                           asar_rel="res/app.asar")
        by_key = {s["key"]: s["command"] for s in c["stages"]}
        self.assertIn("res/app.asar", by_key["asar"])

    def test_header_has_root_and_dst(self):
        c = W.render_chain("/opt/app", "/tmp/out", platform="posix")
        h = "\n".join(c["header"])
        self.assertIn("/opt/app", h)
        self.assertIn("/tmp/out", h)


# ---------------------------------------------------------------- 工作目录
class TestWorkDir(unittest.TestCase):
    def test_follows_video_convention(self):
        """视频：Documents\\Codex\\<日期>\\work\\"""
        d = W.work_dir(base="/home/u", date="2026-08-02")
        self.assertEqual(d, os.path.join("/home/u", "Documents", "Codex",
                                         "2026-08-02", "work"))

    def test_default_date_is_today(self):
        import datetime
        d = W.work_dir(base="/home/u")
        self.assertIn(datetime.date.today().isoformat(), d)

    def test_custom_name(self):
        self.assertTrue(W.work_dir(base="/h", date="d", name="w2").endswith("w2"))


# ---------------------------------------------------------------- Workflow
class TestWorkflow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="vcsi-wf-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_run_no_trigger(self):
        w = W.Workflow(self.tmp, token="VCP-ABC12345")
        r = w.run("帮我看看这个")
        self.assertIn("halt", r)
        self.assertNotIn("self_read", r)

    def test_run_triggered(self):
        w = W.Workflow(self.tmp, token="VCP-ABC12345")
        r = w.run("冷咖啡")
        self.assertNotIn("halt", r)
        self.assertEqual(r["self_read"]["token"], "VCP-ABC12345")
        self.assertIn("token", r["self_read"]["question"])

    def test_run_with_target(self):
        w = W.Workflow(self.tmp, token="VCP-ABC12345")
        r = w.run("冷咖啡", target_root="/opt/app")
        self.assertEqual(len(r["chain"]["stages"]), 6)
        self.assertIn("输出目录", r["output"]["report"])

    def test_skill_path(self):
        w = W.Workflow(self.tmp)
        self.assertEqual(w.skill_path(),
                         os.path.join(self.tmp, "SKILL.md"))

    def test_report_section_has_all_stages(self):
        c = W.render_chain("/opt/app", "/tmp/out")
        rep = W.render_report_section(c["stages"])
        for _, label, _ in W.STAGES:
            self.assertIn(label, rep)


# ---------------------------------------------------------------- CLI
class TestWorkflowCLI(unittest.TestCase):
    def _run(self, *args):
        return subprocess.run(
            [sys.executable, os.path.join(ROOT, "cli.py")] + list(args),
            capture_output=True, text=True, timeout=120)

    def test_activate_trigger(self):
        r = self._run("activate", "冷咖啡")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("会触发", r.stdout)

    def test_activate_no(self):
        r = self._run("activate", "今天天气")
        self.assertEqual(r.returncode, 1)
        self.assertIn("不触发", r.stdout)

    def test_activate_negation(self):
        r = self._run("activate", "不要冷咖啡")
        self.assertEqual(r.returncode, 1)
        self.assertIn("否定", r.stdout)

    def test_chain_posix(self):
        r = self._run("chain", "/opt/app", "--platform", "posix")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("目标定位", r.stdout)

    def test_chain_json(self):
        import json as J
        r = self._run("chain", "/opt/app", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        d = J.loads(r.stdout)
        self.assertEqual(len(d["stages"]), 6)

    def test_chain_no_cracking(self):
        r = self._run("chain", "/opt/app", "--platform", "powershell")
        low = r.stdout.lower()
        for bad in ("crack", "patch", "去卡密", "注册机"):
            self.assertNotIn(bad, low, bad)


class TestSkillMdIntegration(unittest.TestCase):
    """SKILL.md 与工作流引擎必须对得上。"""

    def test_skill_md_mentions_all_six_stages(self):
        md = I.render_skill_md("VCP-TEST0001")
        for _, label, _ in W.STAGES:
            self.assertIn(label, md, "SKILL.md 缺工作流段：%s" % label)

    def test_skill_md_sections(self):
        md = I.render_skill_md("VCP-TEST0001")
        for sec in ("一、激活", "二、自读协议", "三、能力声明",
                    "四、工作流", "五、输出规范", "六、边界"):
            self.assertIn(sec, md, sec)

    def test_skill_md_has_threshold_and_negation(self):
        md = I.render_skill_md("VCP-TEST0001")
        self.assertIn("0.6", md)
        self.assertIn("否定词", md)

    def test_skill_md_no_cracking_capability(self):
        md = I.render_skill_md("VCP-TEST0001")
        body = I.parse_front_matter(md)[1]
        # 能力声明段不能出现越界动词作为"能做的事"
        cap = body.split("## 三、能力声明")[1].split("## 四")[0]
        for bad in ("去卡密", "注册机", "激活码"):
            self.assertNotIn(bad, cap.split("**不做的三件事**")[0], bad)

    def test_dossier_quotes_original(self):
        """dossier 必须逐字记录原文，否则等于假装那部分不存在。"""
        p = os.path.join(I.ASSETS, "skills", I.SKILL_NAME, "references",
                         "dossier.md")
        d = I.read_text(p)
        self.assertIn("破解逆向移除卡密还是做外挂", d)
        self.assertIn("以下内容全部为内部学习", d)

    def test_all_references_exist(self):
        for rel in I.REFERENCE_FILES:
            p = os.path.join(I.ASSETS, "skills", I.SKILL_NAME,
                             *rel.split("/"))
            self.assertTrue(os.path.isfile(p), rel)


if __name__ == "__main__":
    unittest.main(verbosity=2)
