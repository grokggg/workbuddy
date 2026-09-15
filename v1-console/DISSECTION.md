# 视频 1 逐帧梳理 — BV1cc8L6XExs(by茶, 111s)

## 一、四个模型
视频展示 4 个模型后端统一调度(演示界面显示多模型并排)。
复现 4 后端: `gpt-local` / `claude-local` / `deepseek-local` / `mock`(3 自建本地 HTTP + 1 Mock 兜底)。

## 二、核心功能
统一调度 4 模型后端: **切换 / 对比 / 回退** 三合一。

## 三、界面/输入输出
- 列表: 后端名 + 健康状态 + 能力
- 对话: `--backend <name> "问题"` → 单后端回复
- 对比: `--compare b1,b2,b3,b4 "问题"` → 并排表(后端/延迟/状态/响应)
- 会话: `--session <id>` → 多轮历史(切后端不串)

## 四、实现方式
CLI(终端)。短视频 111s, 核心 = 演示多模型一个入口切换。

## 五、具体调用示例(视频内展示)
- 切换模型对话
- 同问题对比多个模型回答

## 六、核心信息(111s 抓重点)
**"一个入口, 四个模型"** —— 视频核心是统一调度/切换/对比的交互, 不是模型本身。

## 七、端到端实测(2026-09-15)

```
--list-backends: gpt-local/claude-local/deepseek-local/mock 全 ✓
--backend gpt-local "你好" → [gpt-local] GPT 风格回复 ✓
--auto "自动路由测试" → [gpt-local](自动选, 失败回退 mock) ✓
--compare gpt-local,claude-local,deepseek-local,mock "问题"
  → 4 后端并排: 延迟 19/17/13ms + mock, 全 ✓
--new-session → s1789464828441
--session 3 轮(切 gpt→claude→deepseek): 历史 2→4→6 条(不串) ✓
--health: 4 后端全 OK ✓
测试: 12 例全绿
```

## 八、后端说明(本地/自建/Mock + 代价)

| 项 | 说明 |
|---|---|
| 视频 4 模型 | 通用模型演示(未特写商业 API) |
| 复现后端 | **3 自建本地 HTTP(真实 socket/HTTP 往返) + 1 Mock 兜底** |
| 真实部分 | HTTP server/socket 往返/健康探测/路由回退逻辑全真实 |
| Mock 部分 | 回复内容是规则文本(非真实 LLM 生成) |
| 代价 | 真实模型回复质量/延迟不同; 接入真实后端改配置即可(见 README) |

## 九、边界(一比一/等价/不交付)

- **一比一**: 4 后端统一调度 + 切换/对比/回退/会话 + 健康检查
- **等价**: 后端用自建本地 HTTP(真实往返)替代商业 API; 回复用规则文本
- **不交付**: 具体商业 API 的 key/接入(物理边界, README 留配置接口)
