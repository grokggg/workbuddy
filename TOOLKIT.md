# up-tools TOOLKIT — 统一工具链

> M18 端到端集成: 把 v2/v3/v4/v5/v6 + 评论区 5 能力集成为统一工具链。

## 一、统一入口 `toolkit.py`

```bash
python3 toolkit.py list               # 工具清单
python3 toolkit.py health             # 健康检查(跑各工具测试)
python3 toolkit.py v2-run <目标>       # v2 十二段链
python3 toolkit.py v3-five-step <目标> # v3 五步法 + 脱敏
python3 toolkit.py v4-jailbreak <方法> # v4 越狱 + 泄露
python3 toolkit.py v5-jump-patch <文件> # v5 AI 辅助改跳转
python3 toolkit.py v6-route <任务>     # v6 路由架构
python3 toolkit.py comment <能力>      # 评论区能力(01-05)
```

统一配置: `~/.config/up-tools/config.json`
统一日志: `~/.config/up-tools/logs/YYYY-MM-DD.log`

## 二、统一回归 `regression.py`

```bash
python3 regression.py            # 跑全部 11 套件 + 报告
python3 regression.py --json     # JSON 报告
python3 regression.py --summary  # 汇总
```

## 三、工具清单

| 工具 | 功能 | 使用 | 边界 |
|---|---|---|---|
| **v2-codex-skill-injection** | 十二段链: 定位→解包→查看→定位校验→修改→重打包→验证 | `toolkit v2-run <目标根目录>` | 修改/打包占位, 只改副本 |
| **v3-five-step-laundering** | 五步法 + 脱敏词表(18 条) | `toolkit v3-five-step <目标>` | 修改/验证占位 |
| **v4-jailbreak-leak** | 5 越狱 + 3 泄露方法(学术研究) | `toolkit v4-jailbreak <方法>` | 本地 mock, 无真实载荷 |
| **v5-jump-patch** | AI 辅助改跳转: 分析→定位→NOP→验证 | `toolkit v5-jump-patch <文件>` | 只改副本, 原件不动 |
| **v6-skill-router** | 11 skill 路由 + iv8 接口 + 案例回血 | `toolkit v6-route <任务>` | mock 后端可跑 |
| **comment-capabilities** | 评论区 5 能力(AGENTS通杀/热词/中转站/封号分析/用完即焚) | `toolkit comment <01-05>` | 机制研究向 |

## 四、集成说明

1. **统一入口**: toolkit.py 注册表 `TOOLS` 定义每个工具的 run/test 命令, 子命令路由
2. **统一回归**: regression.py 的 `SUITES` 跑全部工具测试(11 套件 / 192 测试)
3. **统一配置**: config.json 存共享配置(API key 名等)
4. **统一日志**: 所有入口操作写 logs/ 每日文件
5. **依赖**: 全部 Python 3.8+ 标准库, 零第三方

## 五、测试矩阵(实测)

| 套件 | 测试数 | 状态 |
|---|---|---|
| v2 十二段链 | 10 | ✓ |
| v3 五步法 | 17 | ✓ |
| v4 越狱/泄露 | 17 | ✓ |
| v5 改跳转 | 17 | ✓ |
| v6 路由 | 17 | ✓ |
| 评论01 AGENTS通杀 | 10 | ✓ |
| 评论02 热词 | 31 | ✓ |
| 评论03 中转站 | 31 | ✓ |
| 评论04 封号分析 | 11 | ✓ |
| 评论05 用完即焚 | 19 | ✓ |
| toolkit 统一入口 | 12 | ✓ |
| **合计** | **192** | **11/11 通过** |

## 六、目录结构

```
up-tools/
├── toolkit.py          # 统一入口
├── regression.py       # 统一回归
├── TOOLKIT.md          # 本文档
├── tests/test_toolkit.py  # toolkit 测试
├── v2-codex-skill-injection/  # 十二段链
├── v3-five-step-laundering/   # 五步法
├── v4-jailbreak-leak/         # 越狱/泄露
├── v5-jump-patch/             # 改跳转
├── v6-skill-router/           # 路由
└── comment-capabilities/      # 评论区 5 能力
```
