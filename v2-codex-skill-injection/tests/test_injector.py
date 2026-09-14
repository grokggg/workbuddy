# -*- coding: utf-8 -*-
"""v2-codex-skill-injection 单元测试

全离线：不联网、不碰真实 HOME（全部用 tempfile + HOME 覆盖）。
跑法：python3 tests/test_injector.py
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from lib import injector as I  # noqa: E402


class TempHome(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="vcsi-")

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)


# ---------------------------------------------------------------- 1. 路径解析
class TestPaths(TempHome):
    def test_codex_has_two_candidate_roots(self):
        """视频里是 ~/codex/（无点），社区文档写 ~/.codex/ —— 两个都得认。"""
        roots = I.skill_roots("codex", self.home)
        self.assertEqual(len(roots), 2)
        self.assertTrue(any(r.endswith(os.path.join(".codex", "skills"))
                            for r in roots))
        self.assertTrue(any(r.endswith(os.path.join("codex", "skills"))
                            for r in roots))

    def test_expand_replaces_userprofile(self):
        self.assertTrue(I.expand("%USERPROFILE%\\.codex\\skills",
                                 self.home).startswith(self.home))

    def test_detect_prefers_existing(self):
        """两个候选都存在时，选第一个存在的那个。"""
        for r in I.skill_roots("codex", self.home):
            os.makedirs(r)
        self.assertTrue(os.path.isdir(I.detect_root("codex", self.home)))

    def test_detect_none_when_missing(self):
        self.assertIsNone(I.detect_root("codex", self.home, must_exist=True))

    def test_detect_returns_first_when_absent(self):
        r = I.detect_root("codex", self.home, must_exist=False)
        self.assertEqual(r, I.skill_roots("codex", self.home)[0])

    def test_all_frameworks_have_roots_and_profiles(self):
        for k in I.FRAMEWORKS:
            self.assertTrue(I.skill_roots(k, self.home), k)
            self.assertTrue(I.profile_paths(k, self.home), k)

    def test_windows_roots_declared(self):
        for k in I.FRAMEWORKS:
            self.assertTrue(I.FRAMEWORKS[k]["windows_skill_roots"], k)


# ---------------------------------------------------------------- 2. 探针
class TestProbe(unittest.TestCase):
    def test_token_shape(self):
        t = I.make_token()
        self.assertRegex(t, r"^VCP-[0-9A-F]{8}$")

    def test_token_deterministic_with_seed(self):
        self.assertEqual(I.make_token("abc"), I.make_token("abc"))

    def test_token_random_without_seed(self):
        self.assertNotEqual(I.make_token(), I.make_token())

    def test_hit(self):
        t = "VCP-ABC12345"
        ok, _ = I.check_probe_answer("自读探针：%s" % t, t)
        self.assertTrue(ok)

    def test_hit_with_markdown_decoration(self):
        """模型爱加反引号和星号，归一化后仍要能命中。"""
        t = "VCP-ABC12345"
        for ans in ("`%s`" % t, "**%s**" % t, "  %s  " % t,
                    "token 是 %s，读到了" % t):
            ok, _ = I.check_probe_answer(ans, t)
            self.assertTrue(ok, ans)

    def test_miss_other_token(self):
        ok, d = I.check_probe_answer("VCP-DEADBEEF", "VCP-ABC12345")
        self.assertFalse(ok)
        self.assertIn("别的 skill", d)

    def test_miss_file_not_found(self):
        for ans in ("抱歉，我找不到该文件", "No such file or directory",
                    "I cannot find the SKILL.md"):
            ok, d = I.check_probe_answer(ans, "VCP-ABC12345")
            self.assertFalse(ok)
            self.assertIn("没能读到", d)

    def test_miss_empty(self):
        ok, _ = I.check_probe_answer("", "VCP-ABC12345")
        self.assertFalse(ok)

    def test_miss_no_token_installed(self):
        ok, d = I.check_probe_answer("VCP-ABC12345", None)
        self.assertFalse(ok)
        self.assertIn("未安装", d)

    def test_question_mentions_token(self):
        self.assertIn("SKILL.md", I.probe_question())


# ---------------------------------------------------------------- 3. front-matter
class TestFrontMatter(unittest.TestCase):
    def test_parse(self):
        fm, body = I.parse_front_matter(
            "---\nname: x\ndescription: y\n---\n\n# body\n")
        self.assertEqual(fm["name"], "x")
        self.assertEqual(fm["description"], "y")
        self.assertIn("# body", body)

    def test_no_front_matter(self):
        fm, body = I.parse_front_matter("# just body\n")
        self.assertEqual(fm, {})
        self.assertIn("just body", body)

    def test_render_roundtrip(self):
        fm = {"name": "a", "description": "b"}
        txt = I.render_front_matter(fm) + "\nbody\n"
        fm2, _ = I.parse_front_matter(txt)
        self.assertEqual(fm2["name"], "a")
        self.assertEqual(fm2["description"], "b")


# ---------------------------------------------------------------- 4. 渲染
class TestRender(unittest.TestCase):
    def test_skill_md_has_required_parts(self):
        md = I.render_skill_md("VCP-TEST0001")
        fm, body = I.parse_front_matter(md)
        self.assertEqual(fm["name"], "veni-coldbrew")
        self.assertIn("冷咖啡", fm["description"])
        self.assertIn("VCP-TEST0001", md)
        self.assertTrue(I.BOUNDARY_HEADING_RE.search(body),
                        "正文必须有边界类标题")

    def test_boundary_heading_with_number_prefix(self):
        """「## 五、边界」这种带序号的标题不能被误判成没有边界段。"""
        for h in ("## 边界", "## 五、边界", "## 3. Scope",
                  "## Scope & Boundaries", "### 明确不做"):
            self.assertTrue(I.BOUNDARY_HEADING_RE.search(h), h)

    def test_boundary_heading_rejects_body_mention(self):
        """正文里提了「边界」二字但没标题，仍然算没有边界段。"""
        self.assertFalse(I.BOUNDARY_HEADING_RE.search("这段没有边界章节。"))

    def test_skill_md_token_twice(self):
        """token 出现至少两次（中部 + 末尾），用来区分"读了全文"和"只读了开头"。"""
        md = I.render_skill_md("VCP-TEST0001")
        self.assertGreaterEqual(len(re.findall(r"VCP-TEST0001", md)), 2)

    def test_profile_has_block_markers(self):
        p = I.render_profile("VCP-TEST0001", "/x/y")
        self.assertIn(I.BEGIN, p)
        self.assertIn(I.END, p)
        self.assertIn("VCP-TEST0001", p)

    def test_catalog_shape(self):
        cat = I.build_catalog("codex", "/x/y", "VCP-TEST0001", [])
        self.assertEqual(cat["source"], "BV15y3U6oEmt")
        self.assertEqual(cat["skills"][0]["name"], "veni-coldbrew")
        self.assertIn("冷咖啡", cat["skills"][0]["triggers"]["include"])


# ---------------------------------------------------------------- 5. 安装
class TestInstall(TempHome):
    def _install(self, fw="codex", **kw):
        return I.install(fw, home=self.home, **kw)

    def test_install_writes_all(self):
        rep = self._install()
        sd = rep["skill_dir"]
        self.assertTrue(os.path.isfile(os.path.join(sd, "SKILL.md")))
        for rel in ("references/mechanism.md", "references/self-read.md",
                    "cases/README.md"):
            self.assertTrue(os.path.isfile(os.path.join(sd, *rel.split("/"))),
                            rel)
        self.assertTrue(os.path.isfile(os.path.join(rep["skill_root"],
                                                    "skill-catalog.json")))

    def test_install_token_written(self):
        rep = self._install()
        md = open(os.path.join(rep["skill_dir"], "SKILL.md"),
                  encoding="utf-8").read()
        self.assertIn(rep["token"], md)

    def test_install_idempotent_token(self):
        """重复安装不能换 token —— 否则用户之前记的验证串失效，会误判。"""
        r1 = self._install()
        r2 = self._install()
        self.assertEqual(r1["token"], r2["token"])

    def test_install_force_rotates_token(self):
        r1 = self._install()
        r2 = self._install(force=True)
        self.assertNotEqual(r1["token"], r2["token"])

    def test_token_shared_across_frameworks(self):
        """一台机器一个 token。四个框架四个 token 的话用户不知道该问哪个。"""
        toks = set()
        for fw in I.FRAMEWORKS:
            toks.add(self._install(fw)["token"])
        self.assertEqual(len(toks), 1)

    def test_install_profile_appended(self):
        self._install()
        p = I.profile_paths("codex", self.home)[0]
        txt = open(p, encoding="utf-8").read()
        self.assertIn(I.BEGIN, txt)

    def test_install_profile_idempotent(self):
        self._install()
        self._install()
        p = I.profile_paths("codex", self.home)[0]
        txt = open(p, encoding="utf-8").read()
        self.assertEqual(txt.count(I.BEGIN), 1)

    def test_install_dry_run_writes_nothing(self):
        self._install(dry_run=True)
        self.assertFalse(os.path.exists(
            os.path.join(self.home, ".codex")))

    def test_unknown_framework(self):
        with self.assertRaises(KeyError):
            self._install("nope")


# ---------------------------------------------------------------- 6. 卸载
class TestUninstall(TempHome):
    def test_removes_skill_dir(self):
        rep = I.install("codex", home=self.home)
        I.uninstall("codex", home=self.home)
        self.assertFalse(os.path.isdir(rep["skill_dir"]))

    def test_removes_only_own_block(self):
        """块标记不能吞掉用户自己写的内容。"""
        I.install("codex", home=self.home)
        p = I.profile_paths("codex", self.home)[0]
        with open(p, "a", encoding="utf-8") as fh:
            fh.write("\n第1行用户内容\n第2行用户内容\n")
        I.uninstall("codex", home=self.home)
        txt = open(p, encoding="utf-8").read()
        self.assertNotIn(I.BEGIN, txt)
        self.assertIn("第1行用户内容", txt)
        self.assertIn("第2行用户内容", txt)

    def test_preserves_newlines(self):
        """回归：卸载曾用 re.sub(r"\\n*", "")，会把整个文件的换行全删掉。
        只有一行用户内容时看不出来，多行才暴露。"""
        I.install("codex", home=self.home)
        p = I.profile_paths("codex", self.home)[0]
        with open(p, "a", encoding="utf-8") as fh:
            fh.write("\nAAA\nBBB\nCCC\n")
        I.uninstall("codex", home=self.home)
        lines = [l for l in open(p, encoding="utf-8").read().splitlines() if l]
        self.assertEqual(lines, ["AAA", "BBB", "CCC"])

    def test_uninstall_when_not_installed(self):
        rep = I.uninstall("codex", home=self.home)
        self.assertIn("未找到", rep["actions"][0])


# ---------------------------------------------------------------- 7. 校验
class TestCheck(TempHome):
    def test_good_skill_passes(self):
        I.install("codex", home=self.home)
        issues = I.check_skill_dir(
            os.path.join(I.detect_root("codex", self.home), I.SKILL_NAME))
        self.assertEqual([i for i in issues if i[0] == "high"], [])

    def test_missing_skill_md(self):
        issues = I.check_skill_dir(self.home)
        self.assertEqual(issues[0][1], "no-skill-md")

    def test_no_front_matter(self):
        d = os.path.join(self.home, "x")
        os.makedirs(d)
        open(os.path.join(d, "SKILL.md"), "w", encoding="utf-8").write(
            "# no front matter\n" + "x" * 300)
        codes = {i[1] for i in I.check_skill_dir(d)}
        self.assertIn("no-name", codes)
        self.assertIn("no-desc", codes)

    def test_no_token(self):
        d = os.path.join(self.home, "x")
        os.makedirs(d)
        open(os.path.join(d, "SKILL.md"), "w", encoding="utf-8").write(
            "---\nname: a\ndescription: " + "y" * 40 + "\n---\n"
            "## 边界\n" + "z" * 300)
        codes = {i[1] for i in I.check_skill_dir(d)}
        self.assertIn("no-token", codes)

    def test_worst_level_ordering(self):
        self.assertIsNone(I.worst_level([]))
        self.assertEqual(I.worst_level([("low", "a", "")]), "low")
        self.assertEqual(I.worst_level([("low", "a", ""), ("high", "b", "")]),
                         "high")

    def test_verify_before_install(self):
        self.assertIsNone(I.detect_root("codex", self.home, must_exist=True))
        sd = os.path.join(self.home, ".codex", "skills", I.SKILL_NAME)
        codes = {i[1] for i in I.check_skill_dir(sd)}
        self.assertIn("no-skill-md", codes)

    def test_verify_after_install_no_high(self):
        I.install("codex", home=self.home)
        sd = os.path.join(I.detect_root("codex", self.home), I.SKILL_NAME)
        high = [i for i in I.check_skill_dir(sd) if i[0] == "high"]
        self.assertEqual(high, [], high)


# ---------------------------------------------------------------- 8. CLI
class TestCLI(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="vcsi-cli-")
        self.env = dict(os.environ, HOME=self.home,
                        PYTHONPATH=ROOT)

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    def _run(self, *args):
        return subprocess.run(
            [sys.executable, os.path.join(ROOT, "cli.py")] + list(args),
            env=self.env, capture_output=True, text=True, timeout=120)

    def test_show_frameworks(self):
        r = self._run("show", "frameworks")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("codex", r.stdout)

    def test_install_then_verify(self):
        r = self._run("install", "--framework", "codex")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("VCP-", r.stdout)
        r = self._run("verify", "--framework", "codex")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("判定：通过", r.stdout)

    def test_install_all_then_verify_all(self):
        r = self._run("install", "--framework", "all")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = self._run("verify", "--framework", "all")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_uninstall(self):
        self._run("install", "--framework", "codex")
        r = self._run("uninstall", "--framework", "codex")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(os.path.isdir(os.path.join(
            self.home, ".codex", "skills", I.SKILL_NAME)))

    def test_uninstall_twice_ok(self):
        self._run("install", "--framework", "codex")
        self._run("uninstall", "--framework", "codex")
        r = self._run("uninstall", "--framework", "codex")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("未找到", r.stdout)

    def test_verify_probe_hit(self):
        self._run("install", "--framework", "codex")
        tok = json.load(open(os.path.join(
            self.home, ".config", "v2-codex-skill-injection", "state.json"),
            encoding="utf-8"))["probe_token"]
        r = self._run("verify", "--framework", "codex",
                      "--probe", "自读探针：%s" % tok)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("判定    : 通过", r.stdout)

    def test_verify_probe_miss(self):
        self._run("install", "--framework", "codex")
        r = self._run("verify", "--framework", "codex",
                      "--probe", "VCP-00000000")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("不通过", r.stdout)

    def test_bad_framework(self):
        r = self._run("install", "--framework", "nope")
        self.assertNotEqual(r.returncode, 0)

    def test_dry_run_no_writes(self):
        self._run("install", "--framework", "codex", "--dry-run")
        self.assertFalse(os.path.exists(os.path.join(self.home, ".codex")))

    def test_show_skill(self):
        r = self._run("show", "skill")
        self.assertEqual(r.returncode, 0)
        self.assertIn("veni-coldbrew", r.stdout)


class TestPyCompile(unittest.TestCase):
    def test_compiles(self):
        for f in ("cli.py", os.path.join("lib", "injector.py")):
            r = subprocess.run([sys.executable, "-m", "py_compile",
                                os.path.join(ROOT, f)],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, f + r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
