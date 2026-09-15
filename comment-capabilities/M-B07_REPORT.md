# M-B07 报告 — M-B06 遗留修复 + 评论区 5 能力收口

## 第一阶段: M-B06 遗留修复(3 项全做)

### 修复 1: 会话 ID 大小写 bug ✅
**复现**: `cli.py console --session S1789...`(大写) → "会话不存在"
**定位**: SID 生成 = `s`+时间戳(天然小写), 无归一化; 查询原样匹配 → 手输大写失配
**修复**: 生成与查询同一规则——`_load`/`chat` 统一 `sid.lower()`
**验证**:
```
SID: s1789441216680
小写查询 → 第一轮 ✓
大写查询(S1789...) → 同一会话, 第二轮 ✓ (修复前: 会话不存在)
跨进程 3 轮(大小写混合) → 历史 6 条不串不丢, .jsonl 可回放 ✓
```
**测试**: test_case_insensitive_session(大写查询通过 + 历史 4 条累积)

### 修复 2: /dev/null 文件变更警告 ✅
**核实**: `git status` 无异常文件(仅 console.py 修改 + __pycache__)
**排查**: 全仓搜 `/dev/null` —— 只出现在标准重定向(`>/dev/null 2>&1` 静默命令,
install.sh/workflow.py 正常用法), **无把 /dev/null 当输出/work-dir 的 bug**
**结论**: **verifier 误报**(测试时 `>/dev/null` 重定向所致), 非真 bug

### 修复 3: 汇总真实性对齐 ✅
**核实**: "3 轮跨进程上下文不串 ✓" —— **成立**。
原因: 原实测全程小写 SID(生成=查询同规则), 3 轮不串真实成立;
新缺口 = 手输大写失配(修复 1 已补)。
**产出**: M-B06_ERRATA.md(更正说明 + 修复前后对比 + 复现命令)

## 第二阶段: 评论区 5 能力收口

### 前置: 5 能力确切定义(仓库已有, 非臆造)
| # | 能力 | 现有实现 |
|---|---|---|
| 01 | 40 行 AGENTS.md 通杀 | 01-agents-md-universal(engine/cli/tests, 测试全绿) |
| 02 | 热词攻击 | 02-hotword-attack(analyze/retrieve, 全绿) |
| 03 | 多 LLM 端点管理 | 03-relay-manager(add/list/check/switch, 全绿) |
| 04 | skill 封号分析 | 04-skill-ban-analysis(全绿) |
| 05 | 网络验证+用完即焚 | 05-network-verify-burn(issue/verify/burn/audit, 全绿) |

**缺口**: 无统一入口(5 个独立 cli.py)

### 逐个收口(实测)
```
01 agents-md --dry-run → 40 行 AGENTS.md 生成 ✓
02 hotword --help      → analyze/retrieve ✓
03 relay --help        → add/list/check/switch ✓
04 skill-ban --help    → skill_dir 分析 ✓
05 net-burn issue --key → 令牌签发 ✓
```

### 统一入口(真实增量)
`comment-capabilities/cli.py`:
```
python3 cli.py --list-abilities          # 5 能力清单
python3 cli.py ability <name> <args>     # 转发执行
python3 cli.py <name> <args>             # 直接转发
```
实测: --list-abilities / ability hotword --help / 直接转发 全通

## 测试

- 统一入口: 5 例全绿(list/forward/direct/unknown)
- 会话修复: 1 例全绿(大小写不敏感 + 历史累积)
- 5 模块回归: 全绿

## 自检三问

1. **商业级可运行?** 是——统一入口 3 种调用方式 + 5 能力独立可用 + 会话修复
2. **原理讲清?** 是——修复根因(大小写规则)/verifier 误报证据/能力缺口分析
3. **真拿到可运行系统?** 是——统一入口实测 + 修复前后对比实测 + 测试全绿

## 交付

- `comment-capabilities/cli.py`(统一入口) + `tests/test_comment_abilities.py`
- `v1-console/M-B06_ERRATA.md`(修复记录) + `lib/console.py`(大小写修复)
- 双端推送 + 打包
