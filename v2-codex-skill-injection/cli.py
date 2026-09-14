#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2-codex-skill-injection 统一 CLI

install.sh / install.ps1 / verify.sh / verify.ps1 全部调这里，
避免同一套逻辑在 bash 与 PowerShell 里各写一遍、然后行为不一致。

子命令：
    install    落盘 skill
    uninstall  删除（只删自己写的块）
    verify     三层校验
    probe      单独判定自读探针
    show       打印 SKILL.md 正文 / 探针问题
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import injector as I  # noqa: E402

FWS = sorted(I.FRAMEWORKS)


def _frameworks(v):
    return list(I.FRAMEWORKS) if v == "all" else [v]


def cmd_install(a):
    rc = 0
    for fw in _frameworks(a.framework):
        if fw not in I.FRAMEWORKS:
            print("  [skip] 未知框架：%s" % fw)
            rc = 1
            continue
        print("\n" + "-" * 56)
        print("框架：%s（%s）" % (fw, I.FRAMEWORKS[fw]["label"]))
        rep = I.install(fw, dry_run=a.dry_run, force=a.force)
        print("  skills 根：%s" % I.detect_root(fw, must_exist=False))
        for act in rep["actions"]:
            print("  %s" % act)
        for f in rep["files"]:
            print("    写：%s" % f)
        print("  自读探针：%s" % rep["token"])
        print("  下一步：在 agent 里输入「冷咖啡」，再问它探针 token 是多少。")
    print()
    if not a.dry_run:
        print("安装完成。跑 verify 校验：")
        print("  ./verify.sh                              # POSIX")
        print("  .\\verify.ps1                             # Windows")
    return rc


def cmd_uninstall(a):
    rc = 0
    for fw in _frameworks(a.framework):
        if fw not in I.FRAMEWORKS:
            print("  [skip] 未知框架：%s" % fw)
            rc = 1
            continue
        print("\n" + "-" * 56)
        print("框架：%s（%s）" % (fw, I.FRAMEWORKS[fw]["label"]))
        rep = I.uninstall(fw, dry_run=a.dry_run)
        if not rep["actions"]:
            print("  未找到已安装的 skills 目录（可能没装过）")
        for act in rep["actions"]:
            print("  %s" % act)
        for p in rep["removed"]:
            print("    %s" % p)
    return rc


def _layer_assets():
    print("=" * 78)
    print("一、kit 自身资产")
    print("=" * 78)
    src = os.path.join(I.ASSETS, "skills", I.SKILL_NAME)
    miss = []
    for rel, lv in (("SKILL.md", "high"),
                    ("references/mechanism.md", "mid"),
                    ("references/self-read.md", "mid"),
                    ("cases/README.md", "low")):
        ok = os.path.isfile(os.path.join(src, *rel.split("/")))
        print("  %s %-26s %s" % ("✓" if ok else "✗", rel,
                                 "在" if ok else "缺"))
        if not ok:
            miss.append((lv, "asset", "缺 %s" % rel))
    print("  结论：%s" % ("OK" if not miss else "%d 项缺失" % len(miss)))
    return miss


def _layer_activation(framework):
    """层 2.5：激活词自检。

    "装完后输入「冷咖啡」应触发"里可离线的那一半 ——
    验证 description 确实写对了。另一半（模型会不会真触发）由框架决定。
    """
    from lib import workflow as W
    print()
    print("=" * 78)
    print("二·五、激活词自检")
    print("=" * 78)
    m = W.ActivationMatcher()
    ok = True
    for word in ("冷咖啡", "cold brew", "coldbrew"):
        r = m.match(word)
        good = r["decision"] == "trigger"
        ok = ok and good
        print("  %s %-14s %-8s %s" % (
            "✓" if good else "✗", word, r["decision"], r["reason"][:36]))
    rep = I.verify(framework)
    sd = rep.get("skill_dir")
    if sd and os.path.isdir(sd):
        issues = I.check_activation(sd)
        bad = [i for i in issues if i[0] == "high"]
        ok = ok and not bad
        for lv, code, msg in issues:
            print("  %s %-14s %s" % ("✗" if lv == "high" else "!",
                                     code, msg))
        if not issues:
            print("  ✓ 已装的 description 可被激活词命中")
    print("  注意：这只验证 description 写对了；"
          "模型会不会真的触发由框架决定。")
    return 0 if ok else 1


def cmd_verify(a):
    miss = _layer_assets()
    print()
    print("=" * 78)
    print("二、安装点")
    print("=" * 78)
    bad = 0 if not miss else 1
    token = None
    for fw in _frameworks(a.framework):
        if fw not in I.FRAMEWORKS:
            print("  [skip] 未知框架：%s" % fw)
            bad += 1
            continue
        rep = I.verify(fw)
        print()
        print(I.render_report(rep))
        if rep["worst"] == "high":
            bad += 1
        if rep.get("token"):
            token = rep["token"]

    # 层 2.5 只在单框架下跑，避免 all 时刷屏
    if a.framework != "all":
        bad += _layer_activation(a.framework)

    print()
    print("=" * 78)
    print("三、自读探针判据")
    print("=" * 78)
    if not a.probe:
        print("  未提供 --probe，跳过。")
        print("  到 agent 里输入「冷咖啡」，再问一句：")
        print("    %s" % I.probe_question(token))
        print("  然后把回答原文传回来：")
        print("    ./verify.sh --probe \"<模型回答>\"")
        print("    .\\verify.ps1 -Probe \"<模型回答>\"")
    else:
        ok, detail = I.check_probe_answer(a.probe, token)
        print("  探针    : %s" % (token or "（未安装）"))
        shown = a.probe[:120] + ("…" if len(a.probe) > 120 else "")
        print("  模型回答: %s" % shown)
        print("  判定    : %s —— %s" % ("通过" if ok else "不通过", detail))
        if not ok:
            bad += 1
        print()
        print("  阴性结果对照：")
        for case, mean in (
            ("报出正确 token", "链路通了，SKILL.md 全文进了上下文"),
            ("报出别的 token", "触发的是另一个 skill，检查 skills 目录重名"),
            ("说找不到文件", "skill 没被加载；Windows 上注意 ~/codex/ 与 ~/.codex/ 是两个地方"),
            ("答非所问", "可能没触发；换「冷咖啡 / cold brew」再试"),
        ):
            print("    %-18s %s" % (case, mean))
    print()
    print("=" * 78)
    if bad:
        print("判定：不通过（%d 处有问题）" % bad)
        return 1
    print("判定：通过")
    return 0


def cmd_probe(a):
    tok = None
    for fw in (a.framework,):
        rep = I.verify(fw)
        tok = rep.get("token")
    if a.probe is None:
        print("探针 token：%s" % (tok or "（未安装）"))
        print("该问的话：%s" % I.probe_question(tok))
        return 0 if tok else 1
    ok, detail = I.check_probe_answer(a.probe, tok)
    print("%s —— %s" % ("通过" if ok else "不通过", detail))
    return 0 if ok else 1


def cmd_activate(a):
    """激活词探针：离线判定一句话会不会触发。

    装完后用 `冷咖啡` 跑一次，确认激活词确实生效。
    """
    from lib import workflow as W
    m = W.ActivationMatcher().match(a.utterance)
    icon = {"trigger": "会触发", "weak": "弱信号", "no": "不触发"}[m["decision"]]
    print("输入      : %s" % m["input"])
    print("归一化    : %s" % m["normalized"])
    print("判定      : %s（%s）" % (icon, m["decision"]))
    print("分值      : %s（阈值 %.2f）" % (m["score"], W.THRESHOLD))
    if m["trigger"]:
        print("命中激活词: %s" % m["trigger"])
    print("理由      : %s" % m["reason"])
    if m["candidates"]:
        print("候选      :")
        for c in m["candidates"]:
            print("    %-22s %-6s %s" % (c["trigger"], c["score"], c["how"]))
    print()
    print("注意：这是**确定性的下界**，不是预测。")
    print("      判定「不触发」时，真实框架里的模型仍可能触发（它看得懂同义改写）。")
    return 0 if m["decision"] == "trigger" else 1


def cmd_chain(a):
    """生成六段命令链（不执行）。"""
    from lib import workflow as W
    out = a.out or W.work_dir()
    chain = W.render_chain(a.target, out, platform=a.platform)
    if a.json:
        print(json.dumps(chain, ensure_ascii=False, indent=2))
    else:
        print("# 目标根目录：%s" % a.target)
        print("# 输出目录  ：%s" % out)
        print()
        print(W.render_chain_text(chain))
    return 0


def cmd_show(a):
    if a.what == "skill":
        print(I.render_skill_md(I.make_token("demo")))
    elif a.what == "question":
        print(I.probe_question(None))
    elif a.what == "frameworks":
        for k in FWS:
            fw = I.FRAMEWORKS[k]
            print("%-14s %s" % (k, fw["label"]))
            for r in fw[("windows_skill_roots" if I.IS_WIN
                         else "skill_roots")]:
                print("     skills : %s" % r)
            for p in fw["profiles"]:
                print("     profile: %s" % p)
    elif a.what == "catalog":
        p = os.path.join(I.ASSETS, "skill-catalog.json")
        print(open(p, encoding="utf-8").read())
    return 0


def cmd_run(a):
    """真正执行六段链（定位/查看/检查，只读）。"""
    from lib.runner import ChainRunner
    runner = ChainRunner(a.target, out_dir=a.out)
    stages = runner.run_all()
    if a.json:
        print(json.dumps(stages, ensure_ascii=False, indent=2))
    else:
        print(runner.report_text())
    return 0 if all(s["ok"] for s in stages) else 1


def cmd_run_full(a):
    """真正执行十二段链（解包/查看/定位真实执行, 修改/打包占位）。"""
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.dirname(_os.path.dirname(
        _os.path.abspath(__file__))))
    from lib.config_util import load_config, resolve_param
    from lib.runner_full import ChainRunnerFull
    cfg = load_config(a.config)
    target = resolve_param(cfg, "v2", "target", env="TARGET_PATH",
                           default="", cli_value=a.target)
    out = resolve_param(cfg, "v2", "output", env="OUTPUT_DIR",
                        default=None, cli_value=a.out)
    if not target:
        print("错误: 未指定目标。用 TARGET_PATH 环境变量 / config.json / 命令行",
              file=sys.stderr)
        return 1
    runner = ChainRunnerFull(target, out_dir=out)
    stages = runner.run_all()
    if a.json:
        print(json.dumps(stages, ensure_ascii=False, indent=2))
    else:
        print(runner.report_text())
    return 0 if all(s["ok"] for s in stages) else 1


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="cli.py", description="v2-codex-skill-injection（BV15y3UoEmt 复现）")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("install", help="落盘 skill")
    p.add_argument("--framework", default="codex", choices=FWS + ["all"])
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--force", action="store_true", help="重置自读探针 token")
    p.set_defaults(fn=cmd_install)

    p = sub.add_parser("uninstall", help="删除（只删自己写的块）")
    p.add_argument("--framework", default="codex", choices=FWS + ["all"])
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(fn=cmd_uninstall)

    p = sub.add_parser("verify", help="三层校验")
    p.add_argument("--framework", default="codex", choices=FWS + ["all"])
    p.add_argument("--probe", default=None, help="模型回答原文，用于第三层判据")
    p.set_defaults(fn=cmd_verify)

    p = sub.add_parser("probe", help="单独判定自读探针")
    p.add_argument("--framework", default="codex", choices=FWS)
    p.add_argument("probe", nargs="?", default=None)
    p.set_defaults(fn=cmd_probe)

    p = sub.add_parser("activate", help="激活词探针：这句话会不会触发")
    p.add_argument("utterance")
    p.set_defaults(fn=cmd_activate)

    p = sub.add_parser("chain", help="生成六段命令链（只生成，不执行）")
    p.add_argument("target", help="目标应用安装根目录")
    p.add_argument("--out", default=None, help="输出目录（默认工作目录约定）")
    p.add_argument("--platform", choices=["posix", "powershell"],
                   default=None)
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_chain)

    p = sub.add_parser("run", help="真正执行六段链（定位/查看/检查，只读）")
    p.add_argument("target", help="目标应用安装根目录")
    p.add_argument("--out", default=None, help="输出工作目录")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("run-full", help="真正执行十二段链（解包/查看/定位真实执行, 修改/打包占位）")
    p.add_argument("target", nargs="?", default=None,
                   help="目标应用安装根目录(默认从 config/环境变量)")
    p.add_argument("--out", default=None, help="输出工作目录")
    p.add_argument("--config", default=None, help="config.json 路径")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_run_full)

    p = sub.add_parser("show", help="打印内容")
    p.add_argument("what", choices=["skill", "question", "frameworks",
                                    "catalog"])
    p.set_defaults(fn=cmd_show)

    a = ap.parse_args(argv)
    if not getattr(a, "cmd", None):
        ap.print_help()
        return 2
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
