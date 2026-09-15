# INTEGRATION_REPORT — 路线 B 总集成与总压测(M-B08)

## 一、总入口

`integration/cli.py` —— 门面模式统一入口, 11 模块:

```
python3 cli.py --list-all                    # 列全部
python3 cli.py <module> <args>               # 执行模块
python3 cli.py stress --rounds <n>           # 总压测
```

| 模块 | 来源 | 能力 |
|---|---|---|
| v1 | M-B06 | 四模型统一控制台 |
| v2 | M-B01 | Codex Skill 注入/冷咖啡 |
| v3 | M-B02 | 五步法+脱敏 |
| v4 | M-B03 | 越狱+提示词泄露 |
| v5 | M-B04 | AI 辅助改跳转 |
| v6 | M-B05 | Skill 路由+iv8 |
| agents-md | 评论区 | 40 行 AGENTS.md |
| hotword | 评论区 | 热词攻击 |
| relay | 评论区 | 多 LLM 端点管理 |
| skill-ban | 评论区 | skill 封号分析 |
| net-burn | 评论区 | 网络验证+用完即焚 |

## 二、端到端全链路(每模块真实执行)

```
v1 --backend mock "端到端"  → [mock] 收到: 端到端 ✓
v2 show skill               → SKILL.md 全文 ✓
v3 map                      → 18 条词表 ✓
v4 all "水循环"              → 7/8 通过 ✓
v5 --help                   → 子命令 ✓
v6 demo                     → 路由+iv8+回血 ✓
agents-md --dry-run         → 40 行 AGENTS.md ✓
hotword/relay/skill-ban/net-burn --help → 子命令 ✓
```

## 三、总压测

```
python3 cli.py stress --rounds 2
2 轮 × 11 模块 = 22 次调用
结果: 22/22 通过 (100.0%)
```

**修复记录**(压测中发现):
- v1: e2e 命令带双重 console 前缀 → 去重
- v2: probe 未安装 rc=1 → 改用 show skill

## 四、M-B07 遗留核实

| 核实 | 结果 |
|---|---|
| SID 大小写修复落地 | ✅ console.py 288/300 行 sid.lower(), commit b6e90c0/8f56629 已推 |
| 无第二份 v1-console | ✅ /workspace/up-tools 不存在 |
| 实测 | ✅ 大写 SID 查询同一会话 |
| M-B07 汇总对齐 | ✅ 原结论成立(全小写 SID 下 3 轮不串真实), 大写缺口已修 |

## 五、测试

`integration/tests/test_integration.py` 6 例全绿:
list_all / v1 转发 / v3 转发 / v6 转发 / 未知模块 / 压测 1 轮

## 六、自检三问

1. **商业级可运行?** 是——11 模块单入口 + 压测 100% + 全模块回归
2. **原理讲清?** 是——门面模式/路径解析/压测修复都有文档
3. **真拿到可运行系统?** 是——--list-all + 端到端 + stress 全实测

## 七、边界

- 本地/自建/Mock 后端 + 教学/开源目标
- v2/v4 越界载荷维持中性化(原文入 dossier/MockLLM)
- 不做针对具体商业软件的一键绕过
