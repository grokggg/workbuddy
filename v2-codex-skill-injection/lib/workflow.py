# -*- coding: utf-8 -*-
"""v2-codex-skill-injection 工作流引擎

复现 BV15y3U6oEmt 里**可离线实现**的四段机制：

    激活词匹配 → 自读 SKILL.md → 能力执行路径 → 输出生成

视频第 5 步（拖入目标 → 输「破解」→ 生成 PowerShell 链）的**结构**完整保留：
目标定位 → 根目录探测 → 版本目录 → 工具链检查 → asar 定位 → 输出到工作目录。
每一段做的是**结构查看**，不是破解 —— 用于你拥有或已获授权的 Electron 应用。

不含的部分（原视频的载荷，不是机制）：
    - 「破解 / 去卡密 / 外挂」的能力声明
    - 「内部学习不会违法」的免责话术
    - 以绕过授权校验为目的的命令链
逐字原文与机制分析见 references/dossier.md。
"""
import os
import re
import unicodedata

# ---------------------------------------------------------------- 激活词表
# 视频：输入「冷咖啡」→ 界面显示 Respond to cold coffee activation
TRIGGERS = {
    "冷咖啡": 1.0,
    "coldbrew": 1.0,
    "cold brew": 1.0,
    "cold-brew": 1.0,
    "veni-coldbrew": 1.0,
    "veni coldbrew": 1.0,
    "冷咖啡模式": 0.95,
    "咖啡": 0.35,          # 太泛，单独出现不足以触发
    "brew": 0.3,
}

# 显式否定：用户说"别用冷咖啡"时不该触发
NEGATIONS = ("不要", "别", "不用", "取消", "关闭", "退出", "停止",
             "no ", "don't", "do not", "disable", "stop", "cancel")

THRESHOLD = 0.6


def normalize(text):
    """归一化：全角转半角、去标点空格、小写。

    不做这一步的话「ＣＯＬＤ　ＢＲＥＷ」和「cold brew」会被判成两个东西，
    而模型侧的匹配其实是不区分这些的。
    """
    if not text:
        return ""
    t = unicodedata.normalize("NFKC", text)
    t = t.lower()
    t = re.sub(r"[\s_\-]+", "", t)
    # 含中文引号「」『』【】（）与书名号 —— 只写 ASCII 标点的话
    # 「冷咖啡」这类引在书名号里的输入会被判成没命中。
    t = re.sub(r"[，。！？、；：\"'`~!@#$%^&*()\[\]{}<>/\\|"
               r"「」『』【】（）《》〈〉·—…]+", "", t)
    return t


class ActivationMatcher:
    """激活词匹配器。

    把"会不会触发"从玄学变成一个可以离线测、有分数的判定。
    真框架里做这件事的是模型，判定不可预测也不可复现 ——
    这个匹配器给的是一个**确定性的下界**：
        匹配器说会触发 → 模型大概率也会（因为信号够强）
        匹配器说不会    → 模型仍可能触发（它看得懂同义改写）
    所以它的用途是**自查**，不是预测。
    """

    def __init__(self, triggers=None, threshold=THRESHOLD):
        self.triggers = dict(triggers or TRIGGERS)
        self.threshold = threshold

    def match(self, utterance):
        """返回 dict：{trigger, score, decision, reason, candidates}"""
        raw = utterance or ""
        n = normalize(raw)
        out = {
            "input": raw,
            "normalized": n,
            "trigger": None,
            "score": 0.0,
            "decision": "no",
            "reason": "",
            "candidates": [],
        }
        if not n:
            out["reason"] = "空输入"
            return out

        # 1) 逐条打分
        best = (None, 0.0, "")
        for trig, base in self.triggers.items():
            nt = normalize(trig)
            if not nt:
                continue
            if nt == n:
                score, how = base, "完全等于"
            elif nt in n:
                # 占比越高越可能是真的在叫它，而不是顺口提到
                score, how = base * (0.7 + 0.3 * len(nt) / max(len(n), 1)), "包含"
            else:
                continue
            out["candidates"].append({"trigger": trig, "score": round(score, 3),
                                      "how": how})
            if score > best[1]:
                best = (trig, score, how)

        out["trigger"], out["score"], how = best[0], round(best[1], 3), best[2]

        # 候选按分值降序 —— 排查"为什么触发了"时先看最高的那个
        out["candidates"].sort(key=lambda c: -c["score"])

        # 2) 否定词压制
        low = n
        neg = next((w for w in NEGATIONS if normalize(w) in low), None)
        if neg and out["score"] > 0:
            out["candidates"].append({"trigger": "<negation:%s>" % neg,
                                      "score": 0.0, "how": "否定"})
            out["reason"] = "检测到否定词「%s」，抑制触发" % neg
            out["decision"] = "no"
            return out

        # 3) 阈值判定
        if out["score"] >= self.threshold:
            out["decision"] = "trigger"
            out["reason"] = "命中激活词「%s」（%s，分值 %.2f ≥ 阈值 %.2f）" % (
                out["trigger"], how, out["score"], self.threshold)
        elif out["score"] > 0:
            out["decision"] = "weak"
            out["reason"] = ("信号偏弱（「%s」分值 %.2f < 阈值 %.2f）；"
                             "真实框架里可能仍会触发，也可能不会" %
                             (out["trigger"], out["score"], self.threshold))
        else:
            out["reason"] = "未命中任何激活词"
        return out

    def would_trigger(self, utterance):
        return self.match(utterance)["decision"] == "trigger"


# ---------------------------------------------------------------- 自读
SELF_READ = {
    "powershell": "Get-Content -LiteralPath '{path}' -Raw",
    "posix": "cat '{path}'",
}

TOKEN_RE = re.compile(r"VCP-[0-9A-F]{8}")


def self_read_command(path, platform=None):
    """视频第 3 步：模型把自己刚加载的 SKILL.md 读出来。"""
    pf = platform or ("powershell" if os.name == "nt" else "posix")
    return SELF_READ.get(pf, SELF_READ["posix"]).format(path=path)


def verify_self_read(answer, token):
    """判据：回答里出现 token 即证明全文进了上下文。"""
    from lib.injector import check_probe_answer
    return check_probe_answer(answer, token)


# ---------------------------------------------------------------- 六段工作流
# 视频第 6 步的链，逐段对应。每段做的是结构查看。
STAGES = [
    ("locate",     "目标定位",     "从快捷方式/进程/安装清单定位应用安装路径"),
    ("root",       "根目录探测",   "确认安装根目录与目录结构"),
    ("version",    "版本目录",     "定位带版本号的目录"),
    ("toolchain",  "工具链检查",   "确认 node/npm/npx 与 @electron/asar 可用"),
    ("asar",       "asar 定位",   "定位 resources/app.asar"),
    ("output",     "输出工作目录", "建带时间戳的输出目录，产物不写回原位置"),
]


def work_dir(base=None, date=None, name="work"):
    """输出目录：~/Documents/Codex/<日期>/work/ —— 与视频第 6 步一致。"""
    import datetime
    base = base or os.path.expanduser("~")
    d = date or datetime.date.today().isoformat()
    return os.path.join(base, "Documents", "Codex", d, name)


def render_chain(target_root, out_dir, platform=None, asar_rel=None):
    """生成六段命令链。

    结构照搬视频第 6 步，但每段都是只读查看：
        定位 → 根目录 → 版本 → 工具链 → asar → 输出
    最后一步调 asar_inspect.js 的 list/info/extract，不做写回或补丁。
    """
    pf = platform or ("powershell" if os.name == "nt" else "posix")
    asar_rel = asar_rel or os.path.join("resources", "app.asar")
    stages = []

    if pf == "powershell":
        cmds = [
            ("locate", "Get-Item -LiteralPath $target | Select-Object FullName,Target"),
            ("root", "Get-ChildItem -LiteralPath $root | Select-Object Name,Length"),
            ("version", "Get-ChildItem -LiteralPath $root -Directory | Sort-Object Name"),
            ("toolchain", "$ErrorActionPreference='SilentlyContinue'; "
                          "node --version; npm --version; "
                          "npx --yes @electron/asar --version"),
            ("asar", "$ErrorActionPreference='Stop'; "
                     "Get-Item -LiteralPath (Join-Path $ver '%s')" % asar_rel),
            ("output", "New-Item -ItemType Directory -Force -Path $dst | Out-Null"),
        ]
        head = [
            "$root = '%s'" % target_root,
            "$dst  = '%s'" % out_dir,
        ]
    else:
        cmds = [
            ("locate", "readlink -f \"$target\" 2>/dev/null || echo \"$target\""),
            ("root", "ls -la \"$root\""),
            ("version", "find \"$root\" -maxdepth 2 -type d | sort"),
            ("toolchain", "node --version; npm --version; "
                          "npx --yes @electron/asar --version"),
            ("asar", "ls -la \"$ver/%s\"" % asar_rel),
            ("output", "mkdir -p \"$dst\""),
        ]
        head = [
            "root='%s'" % target_root,
            "dst='%s'" % out_dir,
        ]

    for i, (key, label, desc) in enumerate(STAGES, 1):
        cmd = dict(cmds)[key]
        stages.append({
            "index": i,
            "key": key,
            "label": label,
            "desc": desc,
            "command": cmd,
        })

    tool = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "tools", "asar_inspect.js")
    if pf == "powershell":
        tail = [
            "# 结构查看（不写回、不打补丁）",
            "node \"%s\" info    \"$ver\\%s\"" % (tool, asar_rel),
            "node \"%s\" list    \"$ver\\%s\"" % (tool, asar_rel),
            "node \"%s\" extract \"$ver\\%s\" \"$dst\"" % (tool, asar_rel),
        ]
    else:
        tail = [
            "# 结构查看（不写回、不打补丁）",
            "node %s info    \"$ver/%s\"" % (tool, asar_rel),
            "node %s list    \"$ver/%s\"" % (tool, asar_rel),
            "node %s extract \"$ver/%s\" \"$dst\"" % (tool, asar_rel),
        ]
    return {"platform": pf, "header": head, "stages": stages, "tail": tail}


def render_chain_text(chain):
    lines = list(chain["header"])
    for s in chain["stages"]:
        lines.append("")
        lines.append("# %d. %s —— %s" % (s["index"], s["label"], s["desc"]))
        lines.append(s["command"])
    lines.append("")
    lines.extend(chain["tail"])
    return "\n".join(lines)


# ---------------------------------------------------------------- 输出规范
def render_report_section(stages):
    """输出规范：模型每段之后该报告什么。

    视频状态栏显示的是 Planning unpacking and decompiling steps / 已处理 1m54s，
    即每段都有可见的进度输出。这里把"该报告什么"写死成结构。
    """
    rows = []
    for s in stages:
        rows.append("| %d | %s | %s |" % (s["index"], s["label"], s["desc"]))
    return "\n".join(rows)


class Workflow:
    """把上面串起来：激活 → 自读 → 执行 → 输出。"""

    def __init__(self, skill_dir, token=None, platform=None):
        self.skill_dir = skill_dir
        self.token = token
        self.platform = platform or ("powershell" if os.name == "nt"
                                     else "posix")
        self.matcher = ActivationMatcher()

    def skill_path(self):
        return os.path.join(self.skill_dir, "SKILL.md")

    def step_activate(self, utterance):
        return self.matcher.match(utterance)

    def step_self_read(self):
        return {
            "command": self_read_command(self.skill_path(), self.platform),
            "token": self.token,
            "question": ("请读取你自己的 SKILL.md 全文，"
                         "并原样输出其中「自读探针」标记的 token。"),
        }

    def step_execute(self, target_root, out_dir=None, date=None):
        out_dir = out_dir or work_dir(date=date)
        return render_chain(target_root, out_dir, platform=self.platform)

    def step_output(self, chain):
        return {"report": render_report_section(chain["stages"]),
                "out_dir": work_dir()}

    def run(self, utterance, target_root=None):
        """跑一遍完整链路（不含真实执行，只生成）。"""
        a = self.step_activate(utterance)
        r = {"activation": a}
        if a["decision"] == "no":
            r["halt"] = "未触发，链路到此为止"
            return r
        r["self_read"] = self.step_self_read()
        if target_root:
            r["chain"] = self.step_execute(target_root)
            r["output"] = self.step_output(r["chain"])
        return r
