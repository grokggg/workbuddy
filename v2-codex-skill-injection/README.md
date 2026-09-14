# v2-codex-skill-injection

复现 B 站视频 **BV15y3U6oEmt**（by茶，197s，Codex Skill 注入）。

> 把 SKILL.md 放进 agent 框架的 skills 目录 → 输入激活词 → 模型加载它 → 行为被改写。
> 视频里这条链路被用来破解第三方软件；本工具只复现**机制本身**，
> 能力部分换成合法范围（自有/已授权 Electron 应用的 asar 查看与解包）。

**核心设计**：把视频第 3 步「模型自读 SKILL.md」做成**自读探针** ——
这是整条链路上唯一能被第三方客观验证的环节。文件落盘 ≠ 被加载，
模型能报出 SKILL.md 里的随机 token，才证明全文真进了上下文。

- 文档：[DISSECTION.md](DISSECTION.md)（视频梳理）· [MODULE.md](MODULE.md)（8 项说明）· [references/dossier.md](assets/skills/veni-coldbrew/references/dossier.md)（原视频三节原文逐字记录 + 机制分析）
- 测试：Python 106 例 + Node 15 例 = **121 例**，全绿
- **结构完整，载荷替换**：SKILL.md 七节一段不缺；原视频的「能力声明 / 免责话术 / 破解执行链」替换为合法能力（自有/已授权 Electron 应用的结构查看）。三节的槽位、判定逻辑、输出规范全保留，替换的只是**做什么**。

---

## 一、30 秒跑通

```bash
cd /workspace/up-tools/v2-codex-skill-injection

./install.sh                 # 装到 Codex（视频原框架）
./verify.sh                  # 看落盘位置 + 探针 token
```

然后**打开 Codex，新开一个会话**：

1. 输入 `冷咖啡`
2. 再问：`请读取你自己的 SKILL.md 全文，并原样输出其中「自读探针」标记的 token。`
3. 把回答喂回来判定：

```bash
./verify.sh --probe "自读探针：VCP-XXXXXXXX"
# 判定    : 通过 —— 命中 token VCP-XXXXXXXX
```

先离线确认激活词写对了（不用打开 agent）：

```bash
python3 cli.py activate "冷咖啡"      # → 会触发（trigger）
python3 cli.py activate "不要冷咖啡"  # → 不触发（否定词抑制）
```

Windows 用 `.\install.ps1` / `.\verify.ps1`。

---

## 二、目录结构

```
v2-codex-skill-injection/
├── cli.py                      统一 CLI（两个平台共用，脚本只是薄封装）
├── lib/injector.py             核心库：路径/安装/卸载/校验/探针
├── lib/workflow.py             工作流引擎：激活匹配/自读/六段链/输出规范
├── assets/
│   ├── AGENTS.md.tmpl          全局人格层模板
│   ├── skill-catalog.json      catalog 模板
│   └── skills/veni-coldbrew/
│       ├── SKILL.md            主文件（无害化重写）
│       ├── references/{mechanism,self-read,activation,workflow,dossier}.md
│       └── cases/README.md
├── tools/asar_inspect.js       Node：asar list / extract / info
├── install.sh   install.ps1    安装
├── verify.sh    verify.ps1     验证
├── tests/
│   ├── test_injector.py        57 例（注入/安装/校验）
│   ├── test_workflow.py        49 例（激活/自读/六段链）
│   └── test_asar_inspect.js    15 例
├── DISSECTION.md  MODULE.md  README.md
└── package_delivery.py         收口
```

**为什么脚本都是薄封装**：`install.sh` / `install.ps1` / `verify.sh` / `verify.ps1`
全部调 `cli.py`。同一套逻辑在 bash 和 PowerShell 里各写一遍，必然会在某处行为不一致。

---

## 三、安装

```bash
./install.sh                      # 装到 codex（默认）
./install.sh --framework all      # 四个框架都装
./install.sh --dry-run            # 只看会往哪写，不落盘
./install.sh --uninstall          # 卸载
./install.sh --force              # 重置探针 token
./install.sh --with-node-deps     # 顺带装 @electron/asar
```

Windows：

```powershell
.\install.ps1
.\install.ps1 -Framework all
.\install.ps1 -DryRun
.\install.ps1 -Uninstall
.\install.ps1 -Force
.\install.ps1 -WithNodeDeps
```

### 落盘位置

| 框架 | skills 目录 | 人格文件 |
|---|---|---|
| **Codex**（视频原环境） | `~/.codex/skills` 或 `~/codex/skills` | `~/.codex/AGENTS.md` 或 `~/codex/AGENTS.md` |
| Claude Code | `~/.claude/skills` | `~/.claude/CLAUDE.md` |
| Cursor | `~/.cursor/skills` | `~/.cursor/rules/agents.md` |
| 通用 | `~/.config/agent/skills` | `~/.config/agent/AGENTS.md` |

> **Codex 两个候选都认**。视频画面里是 `~/codex/skills`（**无点**），
> 社区文档普遍写 `~/.codex/skills`（**带点**）。只认一个的话，
> 在 Windows 上会装错地方，然后误判成"框架不支持"。

### 幂等与可回滚

| 操作 | 行为 |
|---|---|
| 重复安装 | 保留原 token；profile 块「更新」不是「追加」 |
| `--force` | 重新生成 token（之前记的验证串会失效） |
| 卸载 | 只删 `<!-- v2-codex-skill-injection:begin/end -->` 内的内容 |
| 你自己写的内容 | **一格不动**（含换行） |

---

## 四、验证

```bash
./verify.sh                                    # 层 1 + 层 2
./verify.sh --framework all
./verify.sh --probe "<模型回答>"                # 加层 3
```

| 层 | 查什么 |
|---|---|
| 1 | kit 自身资产（`assets/` 里 SKILL.md + 5 篇 references + cases） |
| 2 | 安装点（SKILL.md 结构、探针 token、catalog、profile 块） |
| 2.5 | **激活词自检**（「冷咖啡」会不会命中已装的 description） |
| 3 | 自读探针（模型回答里有没有 token） |

层 2.5 是"装完后输入「冷咖啡」应触发"里**可离线的那一半**。
另一半（模型会不会真的触发）由框架决定，本工具验证不了 —— 详见下节。

**第 3 层的四种判定**：

| 现象 | 判定 | 含义 |
|---|---|---|
| 报出正确 token | 通过 | 链路通了 |
| 报出别的 token | 不通过 | 触发的是另一个 skill，检查 skills 目录重名 |
| 说"找不到文件" | 不通过 | skill 没被加载；Windows 上注意 `~/codex/` vs `~/.codex/` |
| 答非所问 | 不通过 | 可能没触发，换「冷咖啡 / cold brew」再试 |

### 验证跨会话持久

配置注入的性质是跨会话生效。会话 A 问出 token → **关掉重开会话 B** 再问：
仍报得出 = 真配置层注入；报不出 = 框架只在会话内缓存，与视频里的 Codex 不同。

---

## 五、Electron asar 工具（可选）

视频第 6 步模型调 `npx @electron/asar` 解包目标应用。
解包本身是合法的 Electron 开发操作，所以保留：

```bash
node tools/asar_inspect.js list    <app.asar>          # 列文件
node tools/asar_inspect.js info    <app.asar>          # 读 package.json
node tools/asar_inspect.js extract <app.asar> [输出]   # 解包
```

`list` / `info` **不需要** `@electron/asar`；只有 `extract` 需要：

```bash
./install.sh --with-node-deps     # 或 npx --yes @electron/asar 临时拉
```

范围写死为 `list` / `extract` / `info` 三件事 ——
**不做写回、打包、打补丁**，单测里有断言守着这条线。
解包产物默认落到 `~/Documents/Codex/<日期>/work/`，**不原地改原文件**。

---

## 六、跑测试

```bash
python3 tests/test_injector.py       # 57 例
python3 tests/test_workflow.py       # 49 例
node    tests/test_asar_inspect.js   # 15 例
python3 package_delivery.py          # 收口：跑全部 + 端到端 + 打包
python3 package_delivery.py --check  # 只自检
```

Python 侧：路径双候选、探针四种判定、幂等、跨框架同 token、卸载保内容与换行、
**激活匹配（全角/中文引号/否定词/弱信号）**、**六段链两个平台**、**链里不含越界动作**、
**SKILL.md 七节齐备且与工作流引擎对得上**、CLI 端到端。
Node 侧：头解析、walk、list/info、范围约束（不含打包能力）、extract 不原地改。

全部离线，不碰真实 HOME（用 `tempfile` + `HOME` 覆盖）。

---

## 七、依赖

| 依赖 | 必需？ | 用途 | 缺了会怎样 |
|---|---|---|---|
| Python 3.8+ | **必需** | `cli.py` / `lib/injector.py` | 装不了 |
| Node.js 18+ | 可选 | asar 工具 | asar 三命令不可用，其余照常 |
| @electron/asar | 可选 | asar `extract` | `list`/`info` 正常，`extract` 提示安装方式 |
| agent 框架 | 可选 | 真正加载 skill | 文件照装，但层 3 无法验证 |
| bash / PowerShell | 二选一 | 脚本入口 | 都能直接 `python3 cli.py` |

Python 侧**零第三方依赖**（只用标准库）。

---

## 八、统一 CLI

脚本只是包装，直接用 CLI 也行：

```bash
python3 cli.py install   --framework codex [--dry-run] [--force]
python3 cli.py uninstall --framework all
python3 cli.py verify    --framework codex [--probe "<回答>"]
python3 cli.py probe     "<回答>"
python3 cli.py show      {skill|question|frameworks|catalog}
```

Python API：

```python
from lib import injector as I

rep = I.install("codex")              # 装
tok = rep["token"]                    # 'VCP-XXXXXXXX'
I.check_probe_answer(回答, tok)        # (bool, detail)
I.verify("codex")                     # 三层校验
I.uninstall("codex")                  # 卸
```

---

## 九、已知限制（不藏）

1. **能不能触发，本工具说了不算。** 扫描与命中由框架做，模型的激活词判断
   既不可预测也不可复现。`cli.py activate` 给的是**确定性的下界**：
   它说"会触发"→ 模型大概率也会；它说"不触发"→ 模型**仍可能触发**
   （模型看得懂同义改写）。用途是自查，不是预测。

2. **`install.ps1` / `verify.ps1` 未经实机运行。** 开发环境是 Linux 沙箱，
   没有 PowerShell。语法按 5.1 规范写，**请以实机结果为准**。
   `.sh` 版本是实测过的。

3. **`skill-catalog.json` 和 `AGENTS.md` 不是视频里的东西。**
   视频只展示了单个 `SKILL.md`。这两个是本工具为记账与分层补的，不参与框架加载。

4. **`description` 字段不可审计。** 它是纯自然语言，改一个词就改变触发条件，
   而用户在界面上看不到这个字段。

5. **SKILL.md 是"结构完整、载荷替换"。** 原视频三节（能力声明「破解逆向移除卡密
   还是做外挂」、免责话术「内部学习不会违法」、以破解为目的的执行链）**不保留为
   可执行内容** —— 这三节合起来就是那个 payload：能力声明定目标，免责话术移除
   危害判断，执行链落地。逐字原文与机制分析见 `references/dossier.md`，
   SKILL.md 里也标注了每个槽位被替换了什么、为什么。

6. **`node_modules` 不随包**（6.5 MB），需要时再装。

---

## 十、来源标注

| 来源 | 覆盖 |
|---|---|
| BV15y3U6oEmt【实测】 | Skill 名 `veni-coldbrew`、激活词「冷咖啡」、落盘路径 `~/codex/skills/`、**模型自读 SKILL.md**、PowerShell 解包链、Codex 客户端 |
| 我的工程化 | 自读探针机制、双候选路径解析、一机一 token、四框架适配、asar 工具的范围约束、全部测试 |

> **范围声明**：原视频涉及「去除卡密 / 破解第三方商业软件授权」的具体操作，
> 不在本工具提供范围内。本工具只复现**注入机制**与**可验证性工程**。

---

## 可运行包(新增, 区别于参考层)

本目录是可**实际运行**的包, 不是模板:

```bash
# 全链路: install → verify → activate → run
./install.sh --framework codex      # 1. 装到 Codex skills 目录
./verify.sh --framework codex       # 2. 验证(激活词自检 + 自读探针)
python3 cli.py activate "冷咖啡"     # 3. 激活词探针: 输入即触发
python3 cli.py run <目标根目录>       # 4. 六段链真实执行(定位/查看/检查, 只读)
```

### 六段链执行引擎 `lib/runner.py`

视频第 6 步的 PowerShell 六段链, 用 Python **真正执行**(每段只读):

| 段 | 做什么 | 实现 |
|---|---|---|
| 1 目标定位 | 确认目标存在 | `os.path.isdir` |
| 2 根目录探测 | 列目录内容 | `os.listdir` |
| 3 版本目录 | 递归找 x64/4.2.0 | `os.walk` + 版本号模式 |
| 4 工具链检查 | node/npm/npx/asar | `subprocess` |
| 5 asar 定位 | 找 resources/app.asar | `os.path` |
| 6 输出工作目录 | 建 ~/Documents/Codex/<日期>/work | `os.makedirs` |

```bash
# 测试(新增 14 例)
python3 tests/test_runner.py -v
```

### 测试矩阵(135 例全绿)

| 套件 | 例数 | 覆盖 |
|---|---|---|
| test_injector.py | 57 | 注入/安装/校验 |
| test_workflow.py | 49 | 激活/自读/六段链模板 |
| test_runner.py | **14** | **六段链真实执行** |
| test_asar_inspect.js | 15 | asar list/info/extract |
| **合计** | **135** | 全绿 |
