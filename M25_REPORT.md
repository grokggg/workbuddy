# M25-A 报告 — AI 驱动的自动化二进制分析引擎

## 一、设计

**输入**: recon_v2 的 JSON 输出(保护机制清单 + 特征位置)
**输出**: 结构化分析报告(绕过思路 + 优先级排序 + 工具链)+ 脚本骨架

**双模式引擎**(工程手册原则: 永远有可运行退化路径):
- **模式 A(真实 LLM)**: Ollama(`/api/generate`)或 llama.cpp(`/completion`)
  - `LLMClient.available()` 探测服务, 有则用真实生成
  - LLM 输出 JSON 数组, 解析后按可行性排序
- **模式 B(规则推理)**: 无 LLM 时降级, `BYPASS_KB` 知识库(6 类保护)
  - 每类: 思路 + 伪代码 + 可行性 + 工具链 + 理由
  - 同样按可行性排序

## 二、文件

- `lib/llm_engine.py` — 引擎(LLMClient + LLMAnalyzer)
- `tests/test_llm_engine.py` — 12 例测试
- `toolkit.py` — 新增 `llm-analyze` 子命令

## 三、测试结果

### 测试 1: vmp-demo(4 类保护)
```
保护机制: ['加壳(VMProtect/Themida)', '反调试', '反VM', '完整性校验']
[1] 反调试 (0.8)   静态 patch IsDebuggerPresent / hook 时间函数
[2] 完整性校验 (0.6) 运行时 hook 校验函数(保持文件不变)
[3] 加壳 VMProtect (0.4) 运行期 patch 校验点(不脱壳)
[4] 反VM (0.3)     CPUID 伪造(需 hypervisor) / 换环境
```
**验证**: 策略合理, 排序正确(反调试最易, 反VM最难)。

### 测试 2: 7-Zip(自校验)
```
保护机制: ['反VM', '完整性校验']
[1] 完整性校验 (0.6) 保持文件不变 + hook 校验函数 ← 应对自校验正确
[2] 反VM (0.3)       CPUID 伪造 / 换环境
```
**验证**: 7-Zip 自校验应对思路正确(hook 而非 patch 文件, 避免触发文件哈希)。

### LLM 真实路径(mock 验证)
```
引擎: LLM | LLM 可用: True
[完整性校验] 0.7 hook 校验函数或 patch 比较分支 (来源 LLM)
[反VM] 0.3 CPUID 伪造或换环境 (来源 LLM)
```
**验证**: LLM JSON 输出解析 + 排序 + 结构化正确。

## 四、使用

```bash
# 有 Ollama(默认 qwen2.5:7b)
python3 lib/llm_engine.py --target 目标文件
python3 toolkit.py llm-analyze 目标文件

# 指定后端/模型
python3 lib/llm_engine.py --target 目标 --backend llama --model model.gguf

# 直接用 recon 的 JSON
python3 lib/recon_v2.py 目标 --json > recon.json
python3 lib/llm_engine.py --recon-json recon.json
```

## 五、边界

- LLM 输出为**建议**, 脚本骨架是占位符, 不自动执行
- 规则推理是降级路径, 无 LLM 时仍可用(测试用此路径)
- 真实 LLM 需用户自己装 Ollama/llama.cpp + 拉模型
