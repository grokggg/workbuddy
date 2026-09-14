# comment-capabilities — 评论区能力复现

> 复现评论区提到的 5 个能力。
> **重要说明**: 仓库 Phase H 记录("评论区摘录无落盘文件, 不可核实")。
> 本目录按**用户给的方向描述**构建, 机制中性, 用途选择, 学术/研究向。

## 能力清单

| # | 目录 | 能力 | 实现 | 测试 |
|---|---|---|---|---|
| 01 | [01-agents-md-universal](01-agents-md-universal/README.md) | 40 行 AGENTS.md 通杀 | 40 行模板 + 4 框架安装器 + 验证器 | 10 |
| 02 | [02-hotword-attack](02-hotword-attack/README.md) | 热词攻击 | 热度污染分析 + 检索影响评估 | 14 |
| 03 | [03-relay-manager](03-relay-manager/README.md) | 中转站管理 | 多端点管理 + 切换 + 健康检查 | 31 |
| 04 | [04-skill-ban-analysis](04-skill-ban-analysis/README.md) | skill 封号机制 | 检测点分析 + 规避成本评估 | 11 |
| 05 | [05-network-verify-burn](05-network-verify-burn/README.md) | 网络验证+用完即焚 | 服务端按需加载 + 用完即删 | 19 |

**测试合计: 85 例全绿**

## 快速开始

```bash
# 每个能力独立
cd <能力目录> && ./install.sh

# 示例(用 README.md 定位目录)
cd 01-agents-md-universal && python3 cli.py --name Leila --dry-run
cd 02-hotword-attack && python3 cli.py analyze "人工智能大模型是热搜"
cd 03-relay-manager && python3 cli.py add demo https://api.example.com --model gpt-4o
cd 04-skill-ban-analysis && python3 cli.py <skill目录>
cd 05-network-verify-burn && python3 cli.py issue
```

## 每个能力的 8 项结构
见各目录 README.md: 模块标识/功能/代码/边界/接口/测试/依赖/集成

## 边界
- 全部机制研究向, 不含攻击载荷
- 测试本地 mock / 临时目录
- 具体目标参数由用户填
