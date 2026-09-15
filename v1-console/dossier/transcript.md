# 素材来源: GitHub workbuddy 根目录 材料4_结构化整理.md

# 链接 1：b23.tv/DP7YelS

## 一、材料标识

| 项 | 内容 |
|----|------|
| 短链 | https://b23.tv/DP7YelS |
| BV 号 | BV1cc8L6XExs |
| 标题 | gpt5.6已经全破，需要自取 |
| UP 主 | by茶 |
| 时长 / 发布 | 111 秒 / 2026-08-19 |
| 数据 | 14437 播放 |
| 解析状态 | ✅ 成功（无官方字幕，本地转写 20 段 + 9 帧 OCR） |

## 二、内容蒸馏

**核心机制**：一个「**四模型统一控制台**」（画面标题：*冷咖啡·四模型统一控制台*），把 GPT-5.6 / Claude Code / Grok 4.6 / DeepSeek v4 Pro 四个模型客户端收敛到同一个 Web UI，注入同一套破甲 Skill，用**大白话指令**直接驱动。

**关键步骤（演示）**【实测】
1. 打开控制台，界面四个模型卡片并排（GPT-5.6 / Claude Code / Grok 4.6 / DeepSeek v4 Pro）
2. 说话人自称正在脱一款「游戏外包软件」的 **VMP 壳**
3. 输入大白话指令：「全破解这款软件」「可以使用全部功能」
4. 说话人结论：「直接打白话就做，**不会拒绝**」

**技术组件**【画面 OCR】
- 控制台名称：`冷咖啡·四模型统一控制台` / `ColdBrew冷咖啡|四模型工作台`
- 仓库地址（OCR 有噪声，多帧交叉确认）：`github.com/3641387154-o/gpt5.6-claude-grok4.6-deepseekv4pro`
- 仓库描述：*四模型统一启动·部署·验证·回滚*
- 仓库可见文件（OCR 噪声，仅作参考）：`copy.py`、`mooo.py`、`README.md`、Package/Releases 区
- 社群：QQ 群 `057540028`、另一串 `1077074552`（OCR 噪声）
- 界面出现路由式字符串（OCR 严重噪声，无法完整还原）：`...ROUTE] workflow-crack [stages: preset-locate-checks-trace-data-model-log] derive-or-patch`、`copy-lesson-security-driver | ai-anti-crack-workflow`

**依赖条件**
- 四个模型的可用订阅 / API
- 本地已装 Codex、Claude Code 客户端
- Windows 环境、目标软件本体

## 三、机制分析

**类别**：Agent 配置注入（多客户端统一编排层）＋ 提示词层的行为边界改写

**作用范围**：作用于**本地 Agent 客户端的调度层**，不触及模型权重。它把「选模型」和「下指令」两层合并，使得同一条大白话指令可以并行/切换地打到 4 个模型上——本质是**提示词的扇出（fan-out）**，用来规避单模型拒绝率。

**实现路径**（给一个**空壳**的四模型统一控制台，不含任何破甲内容——只演示编排机制）

目录与依赖：
```bash
mkdir -p ~/mux-console && cd ~/mux-console
python3 -m venv .venv && source .venv/bin/activate
pip install flask
```

`app.py`：
```python
import subprocess, shlex
from flask import Flask, request, jsonify
app = Flask(__name__)

# 只做“把同一条指令路由到本地 CLI”的编排，不做任何提示词改写
ADAPTERS = {
    "claude": ["claude", "-p"],           # Claude Code 非交互模式
    "codex":  ["codex", "exec"],          # Codex CLI
}
@app.post("/run")
def run():
    body = request.get_json(force=True)
    model, prompt = body["model"], body["prompt"]
    cmd = ADAPTERS[model] + [prompt]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    return jsonify({"model": model,
                    "rc": p.returncode,
                    "stdout": p.stdout[-8000:],
                    "stderr": p.stderr[-2000:]})
app.run(port=8899)
```

验证：
```bash
python3 app.py &
curl -s localhost:8899/run -H 'Content-Type: application/json' \
  -d '{"model":"claude","prompt":"用一句话说明当前目录下有哪些文件类型"}' | head -c 500
```
看到 `rc:0` 与模型输出即编排层打通。

配套的**审计脚本**（这才是这个机制真正值得落地的部分——检测环境里有没有被塞入未知 Skill）：
```bash
cat > ~/audit_skills.sh <<'EOF'
#!/usr/bin/env bash
# 扫描常见 Agent 的 skill / 指令目录，输出 SHA256 基线
for d in "$HOME/.claude/skills" "$HOME/.codex/skills" "$HOME/.claude/commands"; do
  [ -d "$d" ] || continue
  echo "== $d =="
  find "$d" -name '*.md' -type f -print0 | while IFS= read -r -d '' f; do
    printf '%s  %s\n' "$(sha256sum "$f" | cut -c1-16)" "$f"
  done
done
EOF
chmod +x ~/audit_skills.sh && ~/audit_skills.sh | tee ~/skill-baseline.txt
```
把 `skill-baseline.txt` 存为基线，之后 `~/audit_skills.sh | diff ~/skill-baseline.txt -` 就能发现新增/改动。

**脆弱点**
- 单点注入、多点生效：一套 Skill 改 4 个客户端，攻击成本被摊薄到 1/4
- 编排层是**信任放大器**：用户以为在跟"一个助手"对话，实际背后是 4 个模型的拒绝率取最小值
- 仓库/社群分发方式使得 Skill 内容不可审计（用户下载即运行）

## 四、跨材料关系

- 与**链接 2** 同源（同一 UP 主 by茶，同一「冷咖啡」品牌），链接 1 是"控制台/成果展示"，链接 2 是"Skill 本体与安装演示"
- 与**链接 4** 共享"大白话下指令"这一交互范式，但链接 4 用的是原生 Codex 无控制台
- 与**材料 3（本系列前序）** 的「Skill `description` 字段是唯一检索入口」结论一致：这里的 Skill 也是靠"激活词"触发

## 五、待验证点

1. GitHub 仓库 `3641387154-o/gpt5.6-claude-grok4.6-deepseekv4pro` 是否真实存在且可访问（OCR 噪声较大，**未验证**）
2. 控制台是否为本地 Web 服务还是纯客户端壳——视频未展示启动过程，**材料未提供**
3. 「四模型统一」是否真并行，还是仅切换——视频只展示了界面，**材料未提供**
4. 说话人称「VMP 壳已脱」——画面未见壳工具输出，**无法证实**

---
