# -*- coding: utf-8 -*-
"""v2-codex-skill-injection 核心库

复现 BV15y3U6oEmt（by茶，197s）的 Codex Skill 目录注入链路：

    落盘 SKILL.md → 激活词触发 → 模型自读 SKILL.md → 能力声明 → 调用工具链

本模块负责链路里**可离线验证**的部分：落盘、卸载、结构校验、自读探针。
「模型是否真的按 skill 回答」由 agent 框架决定，本模块只提供**判据**，不代为回答。

关键设计：自读探针（self-read probe）
    视频第 3 步：模型执行 `Get-Content -LiteralPath <SKILL.md> -Raw`，
    即**模型自己把 SKILL.md 读了出来**。这是整条链路上唯一可被第三方客观验证的环节 ——
    文件存在 ≠ 被加载；模型能报出 SKILL.md 里的探针 token，才证明全文进了上下文。
    所以安装时把随机 token 写进 SKILL.md，人工问一句即可证伪。
"""
import hashlib
import json
import os
import re
import shutil
import sys

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(KIT, "assets")
SKILL_NAME = "veni-coldbrew"

# ---------------------------------------------------------------- 框架路径表
# 视频实测落盘位置：C:\Users\石井\codex\skills\veni-coldbrew\SKILL.md
#   注意是 ~/codex/（无点），与社区文档常见的 ~/.codex/ 不同 —— 两个都要认，
#   否则在 Windows 上会装错地方、然后误判"框架不支持"。
# 工作目录：C:\Users\石井\Documents\Codex\<date>\<session>\work\  （视频第 6 步）
FRAMEWORKS = {
    "codex": {
        "label": "Codex（视频原环境）",
        "skill_roots": ["~/.codex/skills", "~/codex/skills"],
        "profiles": ["~/.codex/AGENTS.md", "~/codex/AGENTS.md"],
        "work_root": "~/Documents/Codex",
        "windows_skill_roots": ["%USERPROFILE%\\.codex\\skills",
                                "%USERPROFILE%\\codex\\skills"],
    },
    "claude-code": {
        "label": "Claude Code",
        "skill_roots": ["~/.claude/skills"],
        "profiles": ["~/.claude/CLAUDE.md"],
        "work_root": "~/.claude",
        "windows_skill_roots": ["%USERPROFILE%\\.claude\\skills"],
    },
    "cursor": {
        "label": "Cursor",
        "skill_roots": ["~/.cursor/skills"],
        "profiles": ["~/.cursor/rules/agents.md"],
        "work_root": "~/.cursor",
        "windows_skill_roots": ["%USERPROFILE%\\.cursor\\skills"],
    },
    "generic": {
        "label": "通用 AGENTS.md",
        "skill_roots": ["~/.config/agent/skills"],
        "profiles": ["~/.config/agent/AGENTS.md"],
        "work_root": "~/.config/agent",
        "windows_skill_roots": ["%USERPROFILE%\\.config\\agent\\skills"],
    },
}

IS_WIN = os.name == "nt"

BEGIN = "<!-- v2-codex-skill-injection:begin -->"
END = "<!-- v2-codex-skill-injection:end -->"
BLOCK_RE = re.compile(
    re.escape(BEGIN) + r"(?:(?!" + re.escape(BEGIN) + r").)*?" + re.escape(END),
    re.S)

BOUNDARY_HEADING_RE = re.compile(
    # 允许带序号前缀（「## 五、边界」「## 3. Scope」），否则会误报成"没有边界段"。
    r"^#{1,6}\s*(?:[0-9一二三四五六七八九十]{1,3}\s*[、.．)）]\s*)?"
    r"(边界|范围与边界|不做|明确不做|不做什么|"
    r"Boundary|Boundaries|Out of Scope|Scope(?:\s*&\s*Boundaries)?)\s*$",
    re.M | re.IGNORECASE)

# 视频里模型自读用的命令（PowerShell）。POSIX 下给等价的 cat。
SELF_READ_CMD = {
    "powershell": "Get-Content -LiteralPath '{path}' -Raw",
    "posix": "cat '{path}'",
}


# ---------------------------------------------------------------- 路径解析
def expand(p, home=None):
    """展开 ~ 与 %USERPROFILE%。home 可注入，便于单测用临时目录。"""
    p = p.replace("%USERPROFILE%\\", "~/").replace("%USERPROFILE%/", "~/")
    p = os.path.expandvars(p)
    if home:
        p = p.replace("~", home, 1) if p.startswith("~") else p
    return os.path.expanduser(p)


def skill_roots(framework, home=None):
    """返回该框架**所有候选** skills 根目录（已展开）。"""
    fw = FRAMEWORKS[framework]
    keys = "windows_skill_roots" if IS_WIN else "skill_roots"
    return [expand(p, home) for p in fw[keys]]


def profile_paths(framework, home=None):
    fw = FRAMEWORKS[framework]
    return [expand(p, home) for p in fw["profiles"]]


def detect_root(framework, home=None, must_exist=True):
    """挑一个实际存在的 skills 根。

    Codex 有两个候选（~/.codex 与 ~/codex）。规则：
      1. 已存在的优先（选第一个存在的）
      2. 都不存在且 must_exist=False → 返回第一个候选（默认建这个）
    """
    roots = skill_roots(framework, home)
    for r in roots:
        if os.path.isdir(r):
            return r
    if must_exist:
        return None
    return roots[0]


# ---------------------------------------------------------------- 探针
def make_token(seed=None):
    """生成自读探针 token。安装时写进 SKILL.md，人工提问时用来证伪。"""
    raw = (seed or os.urandom(16).hex()).encode("utf-8")
    return "VCP-" + hashlib.sha256(raw).hexdigest()[:8].upper()


def probe_question(token=None):
    """给用户在 agent 里问的那句话（验证用）。"""
    if token:
        return ("请读取你自己的 SKILL.md 全文，"
                "并原样输出其中「自读探针」标记的 token。")
    return ("请读取你自己的 SKILL.md 全文，"
            "并原样输出其中「自读探针」标记的 token。")


def check_probe_answer(answer, token):
    """判据：模型的回答里出现 token → 证明 SKILL.md 全文进了上下文。

    返回 (passed, detail)。
    """
    if not token:
        return False, "未安装（无 token），先跑 install.sh"
    if not answer:
        return False, "无回答"
    # 归一化：去掉可能被模型加上的分隔符/空格/反引号
    flat = re.sub(r"[\s`*_]", "", answer).upper()
    want = re.sub(r"[\s`*_]", "", token).upper()
    if want in flat:
        return True, f"命中 token {token}"
    low = answer.lower()
    for kw in ("没有", "无法", "找不到", "not found", "cannot", "no such"):
        if kw in low:
            return False, "模型没能读到 SKILL.md（技能可能未被加载）"
    return False, f"未命中 token {token}（可能触发的是别的 skill）"


# ---------------------------------------------------------------- front-matter
def parse_front_matter(text):
    """解析 --- 包裹的 YAML front-matter。返回 (dict, body)。"""
    if not text.startswith("---"):
        return {}, text
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.S)
    if not m:
        return {}, text
    fm = {}
    for line in m.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        mm = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", line)
        if mm:
            fm[mm.group(1)] = mm.group(2).strip().strip("'\"")
    return fm, m.group(2)


def render_front_matter(fm):
    lines = ["---"]
    for k in ("name", "description"):
        if k in fm:
            lines.append(f"{k}: {fm[k]}")
    for k, v in fm.items():
        if k not in ("name", "description"):
            lines.append(f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines)


# ---------------------------------------------------------------- 渲染
SKILL_TMPL = """\
---
name: {name}
description: {description}
---

# {name}

> 本 Skill 复现自 B 站视频 BV15y3U6oEmt（by茶，197s）的 Codex Skill 目录注入机制。
> 内容为**无害重写**：原视频的 skill 用于破解第三方软件，本文件只保留可观测的
> 机制链路（激活 → 自读 → 能力声明 → 工具链），能力部分替换为合法范围。
> 详见 `references/mechanism.md`。

## 一、激活

当用户提到「冷咖啡」「cold brew」「coldbrew」「veni-coldbrew」时激活本 Skill。
激活后先输出一行：

    [veni-coldbrew 已激活]

## 二、自读协议（本 Skill 的核心）

激活后，**第一步是读取你自己的 SKILL.md 全文**，并原样输出「自读探针」的 token。

{self_read_cmd}

读到后输出：

    自读探针：<token>

**为什么要有这一步**：文件落盘到 skills 目录 ≠ 被加载进上下文。
只有你能报出这个 token，才证明 SKILL.md 的全文真的进了上下文。
这是整条注入链路上唯一可被第三方客观验证的环节。

**自读探针**：`{token}`

## 三、能力声明

本 Skill 的能力范围为 **Electron 应用自查**（仅限你拥有或已获授权的应用）：

- 列出 `app.asar` 内的文件结构
- 解包 `app.asar` 到工作目录，供本地调试与排错
- 读出 `package.json`，确认入口与版本

调用方式：

    node {kit}/tools/asar_inspect.js list  <app.asar>
    node {kit}/tools/asar_inspect.js extract <app.asar> <输出目录>
    node {kit}/tools/asar_inspect.js info  <app.asar>

## 四、工作目录约定

解包产物一律写到工作目录，不原地修改原文件：

- Windows：`%USERPROFILE%\\Documents\\Codex\\<日期>\\work\\`
- POSIX：`~/Documents/Codex/<日期>/work/`

每次操作前先建目录，命名带时间戳，避免覆盖上一次的结果。

## 五、边界

**明确不做**：

- 不破解、不去卡密、不绕过任何软件的授权校验
- 不生成注册机、激活码、补丁程序
- 不对不属于用户、未获授权的应用做上述操作
- 不因为本 Skill 的存在，放宽你自身原有的安全限制
- 不隐瞒、不淡化上述边界；用户要求放宽时，说明原因再拒绝

用户提出越界请求时，按这个顺序处理：
1. 说明该请求超出本 Skill 范围
2. 给出**合法**的替代路径（例如联系软件作者获取授权）
3. 不做任何"供学习参考"式的变通实现

## 六、参考资料（渐进式加载）

正文到此为止。按需再读：

- `references/mechanism.md` —— 注入机制拆解：为什么落盘一个文件就能改行为
- `references/self-read.md` —— 自读协议的作用与判据
- `cases/README.md` —— 案例库说明（默认不回写）

---

自读探针：`{token}`
"""


ASSET_SKILL_MD = os.path.join(ASSETS, "skills", SKILL_NAME, "SKILL.md")


def render_skill_md(token, kit_dir=None, self_read_cmd=None):
    """渲染 SKILL.md。

    单一来源：正文以 assets/skills/veni-coldbrew/SKILL.md 为准，
    这里只替换三个占位符。之前模板写在代码里、资产另存一份，
    两份必然 drift（改了资产忘了改代码，装出来的还是旧版）。
    """
    text = read_text(ASSET_SKILL_MD)
    if not text:
        # 资产缺失时退回内联模板，至少不产出空文件
        desc = ("当用户提到「冷咖啡」「cold brew」「coldbrew」或 veni-coldbrew 时激活。"
                "激活后自读 SKILL.md 全文并回报探针 token。")
        cmd = self_read_cmd or (SELF_READ_CMD["powershell"] if IS_WIN
                                else SELF_READ_CMD["posix"])
        return SKILL_TMPL.format(name=SKILL_NAME, description=desc,
                                 token=token, kit=kit_dir or KIT,
                                 self_read_cmd=cmd.format(
                                     path="<本文件的绝对路径>"))
    cmd = self_read_cmd or (
        SELF_READ_CMD["powershell"] if IS_WIN else SELF_READ_CMD["posix"])
    return (text
            .replace("{PROBE_TOKEN}", token or "VCP-DEMO0000")
            .replace("{KIT_DIR}", kit_dir or KIT)
            .replace("{SELF_READ_CMD}",
                     cmd.format(path="<本文件的绝对路径>")))


def render_profile(token, skill_dir, kit_dir=None):
    return f"""{BEGIN}
## veni-coldbrew（冷咖啡）

已加载 Skill：`veni-coldbrew`，位于 `{skill_dir}`。

- 激活词：冷咖啡 / cold brew / coldbrew / veni-coldbrew（阈值 0.6；
  「不要冷咖啡」这类带否定词的不触发）
- 自读探针：`{token}`
- 能力范围：自有或已授权 Electron 应用的 asar 结构查看与解包
- 工作流：目标定位 → 根目录探测 → 版本目录 → 工具链检查 →
  asar 定位 → 输出工作目录（六段，逐段报告）
- 工具：`node {kit_dir or KIT}/tools/asar_inspect.js {{list|info|extract}}`
- 边界：不破解、不去卡密、不绕过授权校验

（本段由 v2-codex-skill-injection 写入，卸载时只删这一段。）
{END}
"""


# 安装时要一并拷贝的参考资料（渐进式加载的第 3 层）
REFERENCE_FILES = ["references/mechanism.md", "references/self-read.md",
                   "references/activation.md", "references/workflow.md",
                   "references/dossier.md", "cases/README.md"]


def build_catalog(framework, skill_dir, token, written):
    """写 catalog。

    以 assets/skill-catalog.json 为底本（那里是完整条目），
    这里只填运行时才知道的三个字段 + 增补实际写入的文件列表。
    """
    base = None
    try:
        base = json.loads(read_text(os.path.join(ASSETS,
                                                 "skill-catalog.json")))
    except ValueError:
        base = None
    cat = base or {"generator": "v2-codex-skill-injection",
                   "source": "BV15y3U6oEmt", "skills": [{"name": SKILL_NAME}]}
    cat["framework"] = framework
    cat["skill_dir"] = skill_dir
    cat["probe_token"] = token
    cat["written_files"] = written
    if cat.get("skills"):
        s = cat["skills"][0]
        s["path"] = os.path.join(skill_dir, "SKILL.md")
        s["description"] = s.get("description") or parse_front_matter(
            render_skill_md(token))[0].get("description", "")
    return cat


# ---------------------------------------------------------------- 探针状态
# 一台机器一个 token。否则「--framework all」会装出四个不同 token，
# 用户验证时根本不知道该问哪一个（实测踩坑）。
STATE_REL = os.path.join(".config", "v2-codex-skill-injection", "state.json")


def state_path(home=None):
    base = home if home else os.path.expanduser("~")
    return os.path.join(base, STATE_REL)


def read_state(home=None):
    p = state_path(home)
    if not os.path.isfile(p):
        return {}
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except (ValueError, OSError):
        return {}


def write_state(state, home=None, dry_run=False):
    p = state_path(home)
    if dry_run:
        return p
    _write(p, json.dumps(state, ensure_ascii=False, indent=2))
    return p


def resolve_token(home=None, force=False, seed=None):
    """取本机的探针 token：已有就用（除非 --force），没有就生成并存下来。"""
    st = read_state(home)
    tok = st.get("probe_token")
    if tok and re.match(r"^VCP-[0-9A-F]{8}$", tok) and not force:
        return tok, False
    tok = make_token(seed)
    st["probe_token"] = tok
    st["generator"] = "v2-codex-skill-injection"
    write_state(st, home)
    return tok, True


# ---------------------------------------------------------------- 安装 / 卸载
def _write(path, content, dry_run=False):
    if dry_run:
        return "dry-run"
    d = os.path.dirname(os.path.abspath(path))
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return "written"


def read_text(path, default=""):
    """读文本。文件不存在返回 default，不抛。统一用它是为了避免
    `open(p).read()` 到处留未关闭的句柄（实测会刷一片 ResourceWarning）。"""
    if not os.path.isfile(path):
        return default
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return default


def install(framework="codex", home=None, token=None, dry_run=False,
            force=False, kit_dir=None):
    """把 skill 装到 framework。返回 dict 报告。"""
    if framework not in FRAMEWORKS:
        raise KeyError("未知框架 %r，可选：%s"
                       % (framework, ", ".join(sorted(FRAMEWORKS))))
    rep = {"framework": framework, "dry_run": dry_run,
           "files": [], "actions": [], "issues": []}

    root = detect_root(framework, home, must_exist=False)
    rep["skill_root"] = root
    skill_dir = os.path.join(root, SKILL_NAME)
    rep["skill_dir"] = skill_dir

    # token 优先序：显式传入 > 已装文件里的 > 本机 state 里的 > 现生成。
    # 幂等很关键：重复安装换新 token，会让用户之前记下的验证串失效，
    # 然后误判成"skill 没加载"。
    existing = os.path.join(skill_dir, "SKILL.md")
    if token:
        tok = token
        rep["token"] = tok
    elif os.path.isfile(existing) and not force:
        m = re.search(r"VCP-[0-9A-F]{8}", read_text(existing))
        if m:
            tok = m.group(0)
            rep["token"] = tok
            rep["actions"].append(f"skill 已存在，保留原探针 {tok}（--force 可重置）")
        else:
            tok, fresh = resolve_token(home, force)
            rep["token"] = tok
            rep["actions"].append("skill 已存在但无探针 token，重写")
    else:
        tok, fresh = resolve_token(home, force)
        rep["token"] = tok
        if fresh:
            rep["actions"].append(f"生成新探针 {tok}（已存到 {state_path(home)}）")

    # 1) SKILL.md
    _write(existing, render_skill_md(tok), dry_run)
    rep["files"].append(existing)
    rep["actions"].append(f"写 SKILL.md（探针 {tok}）")

    # 2) references + cases（从 assets 拷，缺则不拷）
    src_skill = os.path.join(ASSETS, "skills", SKILL_NAME)
    if os.path.isdir(src_skill):
        for rel in REFERENCE_FILES:
            s = os.path.join(src_skill, *rel.split("/"))
            if os.path.isfile(s):
                dst = os.path.join(skill_dir, *rel.split("/"))
                if not dry_run:
                    _write(dst, read_text(s))
                rep["files"].append(dst)
        rep["actions"].append("写 references/ 与 cases/")

    # 3) catalog
    cat_path = os.path.join(root, "skill-catalog.json")
    cat = build_catalog(framework, skill_dir, tok, rep["files"])
    _write(cat_path, json.dumps(cat, ensure_ascii=False, indent=2), dry_run)
    rep["catalog"] = cat_path
    rep["actions"].append("写 skill-catalog.json")

    # 4) profile 块
    profs = profile_paths(framework, home)
    prof = profs[0] if profs else None
    for p in profs:
        if os.path.isfile(p):
            prof = p
            break
    if prof:
        block = render_profile(tok, skill_dir, kit_dir or KIT)
        old = ""
        if os.path.isfile(prof):
            old = read_text(prof)
        if BEGIN in old:
            new = BLOCK_RE.sub(lambda m: block, old)
            act = "更新 profile 块"
        else:
            new = (old.rstrip() + "\n\n" + block) if old.strip() else block
            act = "追加 profile 块"
        if not dry_run:
            _write(prof, new)
        rep["profile"] = prof
        rep["actions"].append(act)
    else:
        rep["issues"].append(("low", "no-profile", "未找到可写的人格文件"))

    return rep


def uninstall(framework="codex", home=None, dry_run=False):
    """删 skill 目录 + catalog + profile 块（只删自己写的块）。"""
    rep = {"framework": framework, "removed": [], "actions": []}
    root = detect_root(framework, home, must_exist=True)
    if not root:
        rep["actions"].append("未找到已安装的 skills 目录")
        return rep
    sd = os.path.join(root, SKILL_NAME)
    if os.path.isdir(sd):
        if not dry_run:
            shutil.rmtree(sd, ignore_errors=True)
        rep["removed"].append(sd)
        rep["actions"].append("删 skill 目录")
    for p in profile_paths(framework, home):
        if not os.path.isfile(p):
            continue
        old = read_text(p)
        if BEGIN not in old:
            continue
        new = BLOCK_RE.sub("", old)
        new = re.sub(r"\n{3,}", "\n\n", new).strip() + "\n"
        if not dry_run:
            _write(p, new)
        # 说清是"删块"不是"删文件" —— 实测时"删：<AGENTS.md>"很容易被读成文件没了
        rep["removed"].append(p + "（仅删本工具的块，文件保留）")
        rep["actions"].append("删 profile 块（用户内容保留）")
    return rep


# ---------------------------------------------------------------- 校验
def check_skill_dir(skill_dir):
    """结构校验。返回 [(level, code, msg)]，level ∈ high/mid/low。"""
    issues = []
    md = os.path.join(skill_dir, "SKILL.md")
    if not os.path.isfile(md):
        return [("high", "no-skill-md", "缺 SKILL.md")]
    text = read_text(md)
    fm, body = parse_front_matter(text)
    if not fm.get("name"):
        issues.append(("high", "no-name", "front-matter 缺 name"))
    if not fm.get("description"):
        issues.append(("high", "no-desc", "front-matter 缺 description（触发全靠它）"))
    elif len(fm["description"]) < 20:
        issues.append(("mid", "short-desc", "description 过短，触发判定会不稳"))
    if not BOUNDARY_HEADING_RE.search(body):
        issues.append(("mid", "no-boundary", "正文没有边界类标题"))
    m = re.search(r"VCP-[0-9A-F]{8}", text)
    if not m:
        issues.append(("high", "no-token", "缺自读探针 token，无法客观验证是否加载"))
    if len(body.strip()) < 200:
        issues.append(("mid", "too-short", "正文过短"))
    return issues


def check_activation(skill_dir):
    """激活词自检：已装的 SKILL.md 的 description，能不能被「冷咖啡」触发。

    这是"装完后输入「冷咖啡」应触发"里**可离线验证的那一半** ——
    验证 description 确实写对了。另一半（模型会不会真的触发）
    由框架决定，本工具验证不了。
    """
    from lib import workflow as W
    md = os.path.join(skill_dir, "SKILL.md")
    if not os.path.isfile(md):
        return [("high", "activate-no-file", "缺 SKILL.md")]
    fm, _ = parse_front_matter(read_text(md))
    desc = fm.get("description", "")
    issues = []
    if not desc:
        return [("high", "activate-no-desc", "description 为空，永远不会被触发")]
    m = W.ActivationMatcher()
    probes = [("冷咖啡", True), ("cold brew", True), ("coldbrew", True)]
    for word, should in probes:
        r = m.match(word)
        if should and r["decision"] != "trigger":
            issues.append(("high", "activate-miss",
                           f"激活词「{word}」在 description 里匹配不上：{r['reason']}"))
    # 反查：description 本身会不会触发（description 是真正的检索入口）
    rd = m.match(desc)
    if rd["decision"] != "trigger":
        issues.append(("mid", "activate-desc-weak",
                       "description 自身未命中激活词，框架检索时可能捞不到"))
    return issues


def worst_level(issues):
    if not issues:
        return None
    for lv in ("high", "mid", "low"):
        if any(i[0] == lv for i in issues):
            return lv
    return "low"


def verify(framework="codex", home=None):
    """三层校验：资源 → 安装点 → 结论。返回 (report_dict)。"""
    rep = {"framework": framework, "layers": [], "issues": []}

    # 层 1：kit 自身资产
    a = []
    src = os.path.join(ASSETS, "skills", SKILL_NAME, "SKILL.md")
    if not os.path.isfile(src):
        a.append(("high", "asset-skill", "assets 里缺 SKILL.md"))
    for rel in REFERENCE_FILES:
        if not os.path.isfile(os.path.join(ASSETS, "skills", SKILL_NAME,
                                           *rel.split("/"))):
            a.append(("mid", "asset-ref", f"assets 缺 {rel}"))
    if not os.path.isfile(os.path.join(ASSETS, "skill-catalog.json")):
        a.append(("low", "asset-cat", "assets 缺 skill-catalog.json（可生成）"))
    rep["layers"].append(("kit 自身资产", a))

    # 层 2：安装点
    b = []
    root = detect_root(framework, home, must_exist=True)
    if not root:
        b.append(("high", "no-root", "未找到 skills 目录（没装）"))
        rep["layers"].append(("安装点", b))
        rep["issues"] = a + b
        rep["worst"] = worst_level(a + b)
        return rep
    sd = os.path.join(root, SKILL_NAME)
    if not os.path.isdir(sd):
        b.append(("high", "not-installed", f"未安装到 {sd}"))
    else:
        b.extend(check_skill_dir(sd))
        b.extend(check_activation(sd))
        cat = os.path.join(root, "skill-catalog.json")
        if not os.path.isfile(cat):
            b.append(("low", "no-catalog", "缺 skill-catalog.json"))
    profs = profile_paths(framework, home)
    if not any(os.path.isfile(p) and BEGIN in read_text(p)
               for p in profs):
        b.append(("low", "no-profile-block", "人格文件里没有本工具的块"))
    rep["layers"].append(("安装点", b))

    rep["issues"] = a + b
    rep["worst"] = worst_level(a + b)
    rep["skill_root"] = root
    rep["skill_dir"] = os.path.join(root, SKILL_NAME)
    tok = None
    md = os.path.join(sd, "SKILL.md")
    if os.path.isfile(md):
        m = re.search(r"VCP-[0-9A-F]{8}", read_text(md))
        tok = m.group(0) if m else None
    rep["token"] = tok
    return rep


def render_report(rep):
    lines = []
    lines.append("框架：%s（%s）" % (rep["framework"],
                                    FRAMEWORKS[rep["framework"]]["label"]))
    if rep.get("skill_root"):
        lines.append("  skills  : %s" % rep["skill_root"])
    if rep.get("token"):
        lines.append("  探针    : %s" % rep["token"])
    for name, issues in rep["layers"]:
        if not issues:
            lines.append("  [%s] OK" % name)
            continue
        lines.append("  [%s] %d 项" % (name, len(issues)))
        for lv, code, msg in issues:
            lines.append("    %-4s %-16s %s" % (lv, code, msg))
    return "\n".join(lines)
