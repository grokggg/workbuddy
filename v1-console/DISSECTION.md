# 视频 1 逐帧梳理 — BV1cc8L6XExs(by茶, 111s)

> 素材来源: `dossier/transcript.md`(GitHub workbuddy 根目录 材料4_结构化整理.md 链接 1, 20 段转写 + 9 帧 OCR)

## 一、视频真实内容(逐帧证据)

**核心机制** [材料4 L37-42]: 一个「**四模型统一控制台**」(画面标题: *冷咖啡·四模型统一控制台*), 把 **GPT-5.6 / Claude Code / Grok 4.6 / DeepSeek v4 Pro** 四个模型客户端收敛到**同一个 Web UI**, 注入同一套破甲 Skill, 用**大白话指令**直接驱动。

**关键步骤(演示)** [材料4 L42-49, 实测]:
1. 打开控制台, 界面**四个模型卡片并排**(GPT-5.6 / Claude Code / Grok 4.6 / DeepSeek v4 Pro)
2. 说话人自称正在脱一款「游戏外包软件」的 **VMP 壳**
3. 输入大白话指令: 「全破解这款软件」「可以使用全部功能」
4. 结论: 「直接打白话就做, **不会拒绝**」

**技术组件** [材料4 L51-57, 画面 OCR]:
- 控制台名: `冷咖啡·四模型统一控制台` / `ColdBrew冷咖啡|四模型工作台`
- 仓库(OCR 噪声): `github.com/3641387154-o/gpt5.6-claude-grok4.6-deepseekv4pro`
- 界面路由字符串: `[ROUTE] workflow-crack [stages: preset-locate-checks-trace-data-model-log] derive-or-patch`

## 二、工具实际(v1-console) vs 视频

| 维度 | 视频里的(出处) | 工具里的 | 一致? | 差异性质 |
|---|---|---|---|---|
| 模型 | GPT-5.6/Claude Code/Grok 4.6/DeepSeek v4 Pro [材料4 L38] | gpt-local/claude-local/deepseek-local/mock | ❌ | **没对上**(模型名全不同, 且用本地 HTTP/Mock 替代) |
| 界面 | **Web UI**(四模型卡片并排)[材料4 L42] | CLI(终端) | ❌ | **没对上**(GUI → CLI) |
| Skill 注入 | 注入同一套破甲 Skill [材料4 L38] | **无 Skill 注入** | ❌ | **没对上**(缺核心机制) |
| 指令 | 大白话「全破解这款软件」[材料4 L44] | `--backend gpt-local "问题"` | ❌ | **没对上**(指令形式不同) |
| 流程 | 四模型并排 → 同 Skill → 大白话驱动 | 5 子步骤(切换/对比/回退/会话) | ⚠️ | 部分(调度/对比机制对, 无 Skill) |
| 效果 | 脱 VMP 壳 + 不拒绝 | 教学后端回复 | ❌ | **没对上**(视频是真实破解场景) |

## 三、结论

**v1 = 假复现(3 处没对上)**: 模型名、界面形式(Web UI vs CLI)、Skill 注入机制全部缺失。
工具只复现了"多后端调度"的壳, 核心的 **Web UI + 4 真实模型 + Skill 注入 + 大白话驱动** 都没做。

**重做方案**: 需补 ①四模型真实后端接入(GPT-5.6/Claude Code/Grok/DeepSeek 或等价)②Web UI(四卡片并排)③Skill 注入机制(激活词 → 注入行为准则)④大白话指令路由。当前 CLI 版只能算"调度机制原型"。
