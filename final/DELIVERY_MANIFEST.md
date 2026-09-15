# DELIVERY_MANIFEST — 路线 B 交付清单(v3.0-routeB-final)

## 核心入口

| 路径 | 说明 |
|---|---|
| `integration/cli.py` | **总入口**: --list-all / <module> / stress |
| `integration/INTEGRATION_REPORT.md` | 总集成报告 |
| `integration/tests/test_integration.py` | 集成测试(6 例) |

## 6 视频模块

| 路径 | 模块 | 关键文件 |
|---|---|---|
| `v1-console/` | 四模型控制台 | cli.py + lib/console.py + tests(12) |
| `v2-codex-skill-injection/` | 冷咖啡 | SKILL.md + cli.py(9 子命令) + lib/(injector/runner/runner_full/workflow) + install/verify 双版 + tests(120) |
| `v3-five-step-laundering/` | 五步法 | cli.py + five_step_e2e.py + data/laundering_map.yaml(18 词) + tests(17) |
| `v4-jailbreak-leak/` | 越狱泄露 | cli.py + lib/engine.py(8 方法+MockLLM) + tests(17) |
| `v5-jump-patch/` | AI 改跳转 | cli.py + lib/engine.py(修复 ELF/PE 头误判) + tests(17) |
| `v6-skill-router/` | Skill 路由 | cli.py + router_table.yaml(11 技能) + lib/router.py + tests(17) |

## 评论区 5 能力

| 路径 | 能力 |
|---|---|
| `comment-capabilities/cli.py` | 统一入口(--list-abilities) |
| `comment-capabilities/01-agents-md-universal/` | AGENTS.md 通杀 |
| `comment-capabilities/02-hotword-attack/` | 热词攻击 |
| `comment-capabilities/03-relay-manager/` | 端点管理 |
| `comment-capabilities/04-skill-ban-analysis/` | 封号分析 |
| `comment-capabilities/05-network-verify-burn/` | 验证烧毁 |
| `comment-capabilities/tests/` | 统一测试(5) |

## 报告与协议

| 路径 | 说明 |
|---|---|
| `final/FINAL_DELIVERY_REPORT.md` | 总交付报告 |
| `final/DELIVERY_MANIFEST.md` | 本清单 |
| `PROTOCOL_STATUS_V3.md` | 协议 V3.0 终版 |
| `v1-console/M-B06_ERRATA.md` | 修复记录 |

## 工具链(M01-M44 历史)

| 路径 | 说明 |
|---|---|
| `lib/` | recon_v2/analysis_v2/llm_engine/patcher/verifier |
| `real-*/` | M23-M42 真实目标库 |
| `auth-general/` | M41 授权定位/patcher |
| `local-deploy/` | M43 部署包 |
| `orchestrator/` | M33-M36 CI 编排 |

## 统计

- 模块: 11(6 视频 + 5 能力)
- 测试: 211 用例全绿(10 套件)
- 压测: 220/220 (100%)
- tag: v3.0-routeB-final(双远端)
