# -*- coding: utf-8 -*-
"""package_delivery.py —— v2-codex-skill-injection 交付收口

五件事：
  1. 交付文件存在性 + 字节数
  2. Python 57 例 + Node 15 例单元测试（子进程跑，统计用例数）
  3. 回归断言：双候选路径 / 探针四判定 / 幂等 / 跨框架同 token / 卸载保内容
  4. 端到端：临时 HOME 里 install → verify → probe → uninstall
  5. 打包 zip（排除 node_modules / __pycache__）

用法：
    python3 package_delivery.py --check   # 只自检，不打包
    python3 package_delivery.py           # 自检 + 打包
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
WS = os.path.dirname(os.path.dirname(ROOT))          # /workspace
sys.path.insert(0, ROOT)
from lib import injector as I  # noqa: E402

PY_TESTS = [("tests/test_injector.py", 57), ("tests/test_workflow.py", 49)]
EXPECT_PY_CASES = sum(n for _, n in PY_TESTS)      # 106
EXPECT_JS_CASES = 15

# ---------------------------------------------------------------- 交付清单
DELIVERABLES = [
    ("README.md", "使用说明（30 秒跑通 / 安装 / 验证 / 依赖 / 已知限制）"),
    ("MODULE.md", "8 项模块说明（标识/功能/代码/边界/接口/测试/依赖/集成）"),
    ("DISSECTION.md", "视频内容梳理：注入方式 / 文件结构 / 效果 / 框架"),
    ("package_delivery.py", "本文件：收口脚本"),
    ("cli.py", "统一 CLI（install/uninstall/verify/probe/show）"),
    ("lib/injector.py", "核心库：路径/渲染/安装/卸载/校验/探针"),
    ("lib/workflow.py", "工作流引擎：激活匹配/自读/六段链/输出规范"),
    ("assets/AGENTS.md.tmpl", "全局人格层模板"),
    ("assets/skill-catalog.json", "catalog 模板"),
    ("assets/skills/veni-coldbrew/SKILL.md", "Skill 主文件（无害化重写）"),
    ("assets/skills/veni-coldbrew/references/mechanism.md", "机制拆解"),
    ("assets/skills/veni-coldbrew/references/self-read.md", "自读协议详解"),
    ("assets/skills/veni-coldbrew/references/activation.md", "激活与 description 检索"),
    ("assets/skills/veni-coldbrew/references/workflow.md", "六段工作流逐段拆解"),
    ("assets/skills/veni-coldbrew/references/dossier.md", "原视频三节原文与机制分析"),
    ("assets/skills/veni-coldbrew/cases/README.md", "案例库说明"),
    ("tools/asar_inspect.js", "Node：asar list/extract/info"),
    ("install.sh", "安装（POSIX，实测）"),
    ("verify.sh", "验证（POSIX，实测）"),
    ("install.ps1", "安装（Windows，**未实机运行**）"),
    ("verify.ps1", "验证（Windows，**未实机运行**）"),
    ("tests/test_injector.py", "Python 单元测试（注入/安装/校验）"),
    ("tests/test_workflow.py", "Python 单元测试（激活/自读/六段链）"),
    ("tests/test_asar_inspect.js", "Node 单元测试"),
]

EXCLUDE_DIRS = {"node_modules", "__pycache__", ".git", "build"}

NOISE = ("UserWarning", "pkg_resources", "ResourceWarning", "tracemalloc")


def clean(s):
    return "\n".join(l for l in s.splitlines()
                     if not any(n in l for n in NOISE))


def check_files():
    print("=" * 92)
    print("一、交付文件自检")
    print("=" * 92)
    ok = True
    for rel, desc in DELIVERABLES:
        p = os.path.join(ROOT, rel)
        if os.path.exists(p):
            print(f"  ✓ {rel:<52}{os.path.getsize(p):>7} B   {desc}")
        else:
            ok = False
            print(f"  ✗ {rel:<52}{'缺失':>7}     {desc}")
    print(f"\n  交付项 {len(DELIVERABLES)} 个")
    return ok


def run_py_tests():
    print()
    print("=" * 92)
    print("二、单元测试")
    print("=" * 92)
    print("\n  【Python】")
    n = 0
    passed = True
    for rel, expect in PY_TESTS:
        r = subprocess.run([sys.executable, os.path.join(ROOT, rel)],
                           cwd=ROOT, capture_output=True, text=True)
        out = clean(r.stdout + r.stderr)
        m = re.search(r"Ran (\d+) tests", out)
        got = int(m.group(1)) if m else 0
        ok = r.returncode == 0 and got == expect
        passed = passed and ok
        n += got
        print(f"    {'✓' if ok else '✗'} {os.path.basename(rel):<24}"
              f"{got:>5} 个用例（期望 {expect}）"
              f"   {'OK' if r.returncode == 0 else 'FAILED'}")
        if not ok:
            print("\n".join("      " + l for l in out.splitlines()[-25:]))

    print("\n  【Node】")
    node = shutil.which("node")
    njs = 0
    jpass = False
    if not node:
        print("    ✗ 未找到 node，跳过（Node 侧依赖缺失，非代码问题）")
    else:
        rj = subprocess.run(
            [node, os.path.join(ROOT, "tests", "test_asar_inspect.js")],
            cwd=ROOT, capture_output=True, text=True)
        outj = clean(rj.stdout + rj.stderr)
        mj = re.search(r"通过 (\d+) / 失败 (\d+) / 跳过 (\d+)", outj)
        if mj:
            njs = int(mj.group(1))
            njfail = int(mj.group(2))
            njskip = int(mj.group(3))
        else:
            njs = njfail = njskip = 0
        jpass = rj.returncode == 0 and njs == EXPECT_JS_CASES
        print(f"    {'✓' if jpass else '✗'} test_asar_inspect.js"
              f"{njs:>6} 个用例（期望 {EXPECT_JS_CASES}）"
              f"   {'OK' if rj.returncode == 0 else 'FAILED'}"
              + (f"  跳过 {njskip}" if njskip else ""))
        if not jpass:
            print("\n".join("      " + l for l in outj.splitlines()[-25:]))

    total = n + njs
    print("\n" + "-" * 92)
    print(f"  合计 {total} 个用例（Python {n} + Node {njs}）")
    return passed and jpass, total


def regressions():
    print()
    print("=" * 92)
    print("三、回归断言")
    print("=" * 92)
    home = tempfile.mkdtemp(prefix="vcsi-reg-")
    checks = []
    try:
        # --- 1. 双候选路径（视频是 ~/codex 无点，文档写 ~/.codex 带点）
        roots = I.skill_roots("codex", home)
        checks.append(("Codex 双候选 skills 根", len(roots) == 2
                       and any(r.endswith(os.path.join("codex", "skills"))
                               for r in roots)
                       and any(r.endswith(os.path.join(".codex", "skills"))
                               for r in roots),
                       " / ".join(os.path.basename(os.path.dirname(r))
                                  for r in roots)))

        # --- 2. 四框架路径表完整
        allfw = all(I.skill_roots(k, home) and I.profile_paths(k, home)
                    and I.FRAMEWORKS[k]["windows_skill_roots"]
                    for k in I.FRAMEWORKS)
        checks.append(("四框架路径表（含 Windows）", allfw,
                       "/".join(sorted(I.FRAMEWORKS))))

        # --- 3. 探针四判定
        t = "VCP-ABC12345"
        hit, _ = I.check_probe_answer("自读探针：%s" % t, t)
        other, d1 = I.check_probe_answer("VCP-DEADBEEF", t)
        notfound, d2 = I.check_probe_answer("找不到该文件", t)
        empty, _ = I.check_probe_answer("", t)
        checks.append(("探针：命中正确 token", hit is True, t))
        checks.append(("探针：错 token 判为别的 skill", other is False
                       and "别的 skill" in d1, d1[:28]))
        checks.append(("探针：找不到文件能识别", notfound is False
                       and "没能读到" in d2, d2[:28]))
        checks.append(("探针：空回答不通过", empty is False, "空"))

        # --- 4. 幂等：重复安装 token 不变
        r1 = I.install("codex", home=home)
        r2 = I.install("codex", home=home)
        checks.append(("安装幂等（token 不变）", r1["token"] == r2["token"],
                       r1["token"]))

        # --- 5. force 轮换
        r3 = I.install("codex", home=home, force=True)
        checks.append(("--force 轮换 token", r3["token"] != r1["token"],
                       f"{r1['token']} → {r3['token']}"))

        # --- 6. 跨框架同一 token
        toks = {I.install(fw, home=home)["token"] for fw in I.FRAMEWORKS}
        checks.append(("四框架共用同一 token", len(toks) == 1,
                       toks.pop() if len(toks) == 1 else f"{len(toks)} 个"))

        # --- 7. 安装产物完整
        sd = os.path.join(I.detect_root("codex", home), I.SKILL_NAME)
        files_ok = all(os.path.isfile(os.path.join(sd, f)) for f in
                       ("SKILL.md", "references/mechanism.md",
                        "references/self-read.md", "cases/README.md"))
        checks.append(("Skill 目录四件套", files_ok, os.path.basename(sd)))

        # --- 8. 结构校验无 high
        high = [i for i in I.check_skill_dir(sd) if i[0] == "high"]
        checks.append(("结构校验无 high 级问题", not high,
                       "无" if not high else str(high)))

        # --- 9. 带序号的边界标题不被误判
        checks.append(("「## 五、边界」算边界段",
                       bool(I.BOUNDARY_HEADING_RE.search("## 五、边界")),
                       "## 五、边界"))

        # --- 10. profile 块幂等（不重复追加）
        prof = I.profile_paths("codex", home)[0]
        txt = I.read_text(prof)
        checks.append(("profile 块只一份", txt.count(I.BEGIN) == 1,
                       f"count={txt.count(I.BEGIN)}"))

        # --- 11. 卸载保用户内容 + 换行
        with open(prof, "a", encoding="utf-8") as fh:
            fh.write("\nAAA\nBBB\nCCC\n")
        I.uninstall("codex", home=home)
        lines = [l for l in I.read_text(prof).splitlines() if l]
        checks.append(("卸载保用户内容与换行",
                       lines == ["AAA", "BBB", "CCC"] and I.BEGIN not in
                       I.read_text(prof), str(lines)))
    finally:
        shutil.rmtree(home, ignore_errors=True)

    # ---------------- 工作流引擎 ----------------
    from lib import workflow as W

    m = W.ActivationMatcher()
    trig_words = ["冷咖啡", "cold brew", "coldbrew", "ColdBrew",
                  "cold-brew", "veni-coldbrew", "冷咖啡模式"]
    checks.append(("激活词全部可触发",
                   all(m.would_trigger(w) for w in trig_words),
                   "%d/%d" % (sum(m.would_trigger(w) for w in trig_words),
                              len(trig_words))))
    checks.append(("否定词抑制", not m.would_trigger("不要冷咖啡"),
                   "不要冷咖啡"))
    checks.append(("弱信号不触发", m.match("咖啡")["decision"] == "weak",
                   "咖啡 → weak"))
    checks.append(("全角归一化", m.would_trigger("ＣＯＬＤ　ＢＲＥＷ"),
                   "ＣＯＬＤ　ＢＲＥＷ"))
    checks.append(("中文引号归一化", m.would_trigger("「冷咖啡」"), "「冷咖啡」"))

    ch_posix = W.render_chain_text(
        W.render_chain("/opt/app", "/tmp/o", platform="posix"))
    ch_ps = W.render_chain_text(
        W.render_chain("/opt/app", "/tmp/o", platform="powershell"))
    checks.append(("六段链（posix）",
                   all(("［%d" % i) not in ch_posix and
                       ("# %d." % i) in ch_posix for i in range(1, 7)),
                   "6 段"))
    checks.append(("六段链（powershell）",
                   all(("# %d." % i) in ch_ps for i in range(1, 7)),
                   "6 段"))
    checks.append(("PowerShell 链用 -LiteralPath", "-LiteralPath" in ch_ps,
                   "-LiteralPath"))
    checks.append(("工具链容错 / 定位严格",
                   "SilentlyContinue" in ch_ps and "'Stop'" in ch_ps,
                   "SilentlyContinue → Stop"))

    bad_words = ["crack", "patch", "注册机", "激活码", "去卡密"]
    clean_both = not any(b in (ch_posix + ch_ps).lower() for b in bad_words)
    checks.append(("生成的链不含越界动作", clean_both,
                   "无" if clean_both else "有"))

    dossier = I.read_text(os.path.join(
        I.ASSETS, "skills", I.SKILL_NAME, "references", "dossier.md"))
    checks.append(("dossier 逐字记录原能力声明",
                   "破解逆向移除卡密还是做外挂" in dossier, "已记录"))
    checks.append(("dossier 逐字记录原免责话术",
                   "以下内容全部为内部学习" in dossier, "已记录"))

    sk = I.render_skill_md("VCP-TEST0001")
    checks.append(("SKILL.md 七节齐备",
                   all(x in sk for x in ("一、激活", "二、自读协议",
                                         "三、能力声明", "四、工作流",
                                         "五、输出规范", "六、边界",
                                         "七、参考资料")),
                   "7 节"))
    checks.append(("SKILL.md 含六段工作流名",
                   all(lbl in sk for _, lbl, _ in W.STAGES), "6/6"))
    checks.append(("SKILL.md 无残留占位符",
                   not any(p in sk for p in ("{PROBE_TOKEN}", "{KIT_DIR}",
                                             "{SELF_READ_CMD}")),
                   "无"))
    # 能力声明段里，越界动词只能出现在"不做"那一节
    cap = I.parse_front_matter(sk)[1].split("## 三、能力声明")[1].split("## 四")[0]
    does_part = cap.split("**不做的三件事**")[0]
    checks.append(("能力声明不含越界动词",
                   not any(b in does_part for b in ("去卡密", "注册机", "激活码")),
                   "能力段干净"))

    refs_ok = all(os.path.isfile(os.path.join(
        I.ASSETS, "skills", I.SKILL_NAME, *r.split("/")))
        for r in I.REFERENCE_FILES)
    checks.append(("references 齐备（5 篇 + cases）", refs_ok,
                   "%d 个" % len(I.REFERENCE_FILES)))

    ok = True
    for name, passed, detail in checks:
        ok = ok and passed
        print(f"  {'✓' if passed else '✗'} {name:<32}{detail}")
    return ok


def end_to_end():
    print()
    print("=" * 92)
    print("四、端到端（临时 HOME，真跑脚本）")
    print("=" * 92)
    home = tempfile.mkdtemp(prefix="vcsi-e2e-")
    env = dict(os.environ, HOME=home)
    checks = []

    def run(args, **kw):
        return subprocess.run([sys.executable, os.path.join(ROOT, "cli.py")]
                              + args, env=env, capture_output=True,
                              text=True, timeout=180, **kw)

    try:
        # 1) dry-run 不落盘
        r = run(["install", "--framework", "codex", "--dry-run"])
        no_write = not os.path.exists(os.path.join(home, ".codex"))
        checks.append(("install --dry-run 不落盘",
                       r.returncode == 0 and no_write,
                       f"rc={r.returncode}"))

        # 2) 真装
        r = run(["install", "--framework", "all"])
        checks.append(("install --framework all", r.returncode == 0,
                       f"rc={r.returncode}"))

        # 3) verify
        r = run(["verify", "--framework", "all"])
        okv = "判定：通过" in r.stdout
        checks.append(("verify --framework all", r.returncode == 0 and okv,
                       "判定：通过" if okv else r.stdout[-60:]))

        # 4) 取 token，跑探针命中
        stp = os.path.join(home, ".config", "v2-codex-skill-injection",
                           "state.json")
        tok = json.load(open(stp, encoding="utf-8"))["probe_token"]
        r = run(["verify", "--framework", "codex",
                 "--probe", "自读探针：%s" % tok])
        checks.append(("探针命中判定通过", r.returncode == 0
                       and "判定    : 通过" in r.stdout, tok))

        # 5) 探针未命中
        r = run(["verify", "--framework", "codex", "--probe", "VCP-00000000"])
        checks.append(("探针未命中判定不通过", r.returncode == 1
                       and "不通过" in r.stdout, "rc=1"))

        # 6) shell 包装脚本（必须在卸载**之前**跑 —— 装好了才该判通过。
        #    放后面会因为"未安装"正确地返回 1，那是脚本对、测试顺序错。）
        r2 = subprocess.run(["bash", os.path.join(ROOT, "verify.sh")],
                            env=env, cwd=ROOT, capture_output=True,
                            text=True, timeout=180)
        checks.append(("verify.sh 可执行且判定通过",
                       r2.returncode == 0 and "判定：通过" in r2.stdout,
                       f"rc={r2.returncode}"))
        r3 = subprocess.run(["bash", os.path.join(ROOT, "install.sh"),
                             "--framework", "codex"], env=env, cwd=ROOT,
                            capture_output=True, text=True, timeout=180)
        checks.append(("install.sh 可执行", r3.returncode == 0,
                       f"rc={r3.returncode}"))

        # 7) 卸载
        r = run(["uninstall", "--framework", "all"])
        gone = not os.path.isdir(os.path.join(
            home, ".codex", "skills", I.SKILL_NAME))
        checks.append(("uninstall --framework all",
                       r.returncode == 0 and gone, f"rc={r.returncode}"))

        # 8) 重复卸载不报错
        r = run(["uninstall", "--framework", "codex"])
        checks.append(("重复卸载不报错", r.returncode == 0
                       and "未找到" in r.stdout, "rc=0"))

        # 9) 激活词探针（装完后「冷咖啡」应触发）
        r = run(["activate", "冷咖啡"])
        checks.append(("activate 冷咖啡 → 触发", r.returncode == 0
                       and "会触发" in r.stdout, "trigger"))
        r = run(["activate", "不要冷咖啡"])
        checks.append(("activate 否定词 → 不触发", r.returncode == 1
                       and "否定" in r.stdout, "no"))
        r = run(["activate", "帮我看看这个"])
        checks.append(("activate 无关句 → 不触发", r.returncode == 1, "no"))

        # 10) 六段链生成（两个平台）
        r = run(["chain", "/opt/Demo", "--platform", "posix"])
        checks.append(("chain posix 六段",
                       r.returncode == 0 and
                       all(("# %d." % i) in r.stdout for i in range(1, 7)),
                       "6 段"))
        r = run(["chain", "/opt/Demo", "--platform", "powershell"])
        checks.append(("chain powershell 六段",
                       r.returncode == 0 and
                       all(("# %d." % i) in r.stdout for i in range(1, 7))
                       and "-LiteralPath" in r.stdout, "6 段"))
        r = run(["chain", "/opt/Demo", "--json"])
        import json as _J
        try:
            ci = _J.loads(r.stdout)
            nstage = len(ci["stages"])
        except Exception:
            nstage = 0
        checks.append(("chain --json 可解析", nstage == 6, f"{nstage} 段"))

        # 11) 卸载后 verify 应当判不通过（反向断言，确认校验不是无脑 OK）
        r = run(["verify", "--framework", "codex"])
        checks.append(("卸载后 verify 判不通过", r.returncode == 1,
                       f"rc={r.returncode}"))
    finally:
        shutil.rmtree(home, ignore_errors=True)

    ok = True
    for name, passed, detail in checks:
        ok = ok and passed
        print(f"  {'✓' if passed else '✗'} {name:<32}{detail}")
    return ok


def make_zip():
    out = os.path.join(WS, "v2-codex-skill-injection.zip")
    n = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        # 收 DELIVERABLES + 目录里其余源码（排除 node_modules 等）
        seen = set()
        for rel, _ in DELIVERABLES:
            p = os.path.join(ROOT, rel)
            if os.path.exists(p):
                z.write(p, arcname=os.path.join("v2-codex-skill-injection", rel))
                seen.add(rel)
                n += 1
        for dp, dns, fns in os.walk(ROOT):
            dns[:] = [d for d in dns if d not in EXCLUDE_DIRS]
            for fn in fns:
                full = os.path.join(dp, fn)
                rel = os.path.relpath(full, ROOT)
                if rel in seen or fn.endswith(".pyc"):
                    continue
                if os.path.getsize(full) > 1024 * 1024:
                    continue
                z.write(full, arcname=os.path.join("v2-codex-skill-injection",
                                                   rel))
                n += 1
    print()
    print("=" * 92)
    print(f"五、已打包：{out}   {n} 个文件 / {os.path.getsize(out)} bytes")
    print("=" * 92)
    return out


if __name__ == "__main__":
    f_ok = check_files()
    t_ok, total = run_py_tests()
    r_ok = regressions()
    e_ok = end_to_end()
    zip_path = None
    if "--check" not in sys.argv:
        zip_path = make_zip()
    print()
    print("=" * 92)
    print(f"交付自检：文件 {'通过' if f_ok else '不通过'} / "
          f"测试 {'通过' if t_ok else '不通过'}（{total} 用例）/ "
          f"回归 {'通过' if r_ok else '不通过'} / "
          f"端到端 {'通过' if e_ok else '不通过'}")
    if zip_path:
        print(f"打包：{zip_path}")
    print("=" * 92)
    sys.exit(0 if (f_ok and t_ok and r_ok and e_ok) else 1)
