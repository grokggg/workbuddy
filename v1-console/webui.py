#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v1-console web UI — 四模型统一控制台(视频 BV1cc8L6XExs 重做版)

视频规格(材料4_结构化整理.md):
  [行 39] 四模型统一控制台: GPT-5.6 / Claude Code / Grok 4.6 / DeepSeek v4 Pro
  [行 42] 界面四个模型卡片并排
  [行 39] 注入同一套破甲 Skill(此处为冷咖啡激活机制, 与 v2 同源)
  [行 44] 大白话指令直接驱动
  [行 64] 提示词扇出(fan-out): 同一条指令并行打到 4 个模型, 规避单模型拒绝率
  [行 48] 控制台名: 冷咖啡·四模型统一控制台

物理边界: 不交付"破甲"载荷, 只交付编排机制(材料4 行 66 同款空壳做法)。
模型名与视频一致, 但后端为自建本地适配器(真实 CLI 调用接口, 无真实订阅时降级规则回复)。
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from pathlib import Path

try:
    from flask import Flask, render_template_string, request, jsonify
    HAS_FLASK = True
except ImportError:
    HAS_FLASK = False

HERE = Path(__file__).resolve().parent
syspath_ok = True
try:
    import sys
    sys.path.insert(0, str(HERE / "lib"))
    from console import create_backends, Router, compare
except Exception as e:  # pragma: no cover
    syspath_ok = False
    _import_err = str(e)

# 视频 4 模型名(材料4 行 39, 与工具原 mock 名对齐后改名)
VIDEO_MODELS = [
    {"key": "gpt56", "name": "GPT-5.6", "adapter": ["gpt-5.6", "exec"], "style": "GPT-5.6 风格"},
    {"key": "claude", "name": "Claude Code", "adapter": ["claude", "-p"], "style": "Claude Code 风格"},
    {"key": "grok", "name": "Grok 4.6", "adapter": ["grok", "exec"], "style": "Grok 4.6 风格"},
    {"key": "deepseek", "name": "DeepSeek v4 Pro", "adapter": ["deepseek", "exec"], "style": "DeepSeek v4 Pro 风格"},
]

# 冷咖啡激活词(与 v2 同源, 材料4 行 133: Skill 靠激活词触发)
ACTIVATION_WORDS = ["冷咖啡", "冷咖啡模式", "cold brew", "coldbrew", "veni-coldbrew"]
ACTIVATION_THRESHOLD = 0.6

INDEX_HTML = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>冷咖啡·四模型统一控制台</title>
<style>
body{font-family:sans-serif;max-width:1100px;margin:20px auto;padding:0 16px;background:#f7f8fa}
h1{font-size:20px}
.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:16px 0}
.card{border:1px solid #ddd;border-radius:8px;padding:12px;background:#fff}
.card h3{margin:0 0 6px;font-size:15px}
.card .status{font-size:12px;color:#888}
.card .out{font-size:13px;margin-top:8px;background:#f5f5f5;padding:8px;border-radius:4px;min-height:40px;white-space:pre-wrap}
.controls{margin:12px 0}
textarea{width:100%;height:60px;font-size:14px}
button{padding:8px 18px;font-size:14px;margin-right:8px}
.audit{background:#fff8e1;border:1px solid #eeda88;border-radius:8px;padding:10px;margin-top:16px;font-size:13px}
</style>
</head>
<body>
<h1>冷咖啡·四模型统一控制台 <small style="color:#999">(BV1cc8L6XExs 复现)</small></h1>
<div class="controls">
  <textarea id="q" placeholder="大白话指令，例如：分析这个软件的流程"></textarea><br>
  <button onclick="runAll()">四模型并排回答</button>
  <button onclick="runOne('gpt56')">只问 GPT-5.6</button>
  <button onclick="auditSkills()">审计 Skill 目录</button>
</div>
<div class="cards" id="cards">
{% for m in models %}
<div class="card" data-key="{{m.key}}">
  <h3>{{m.name}}</h3>
  <div class="status" id="st-{{m.key}}">待命</div>
  <div class="out" id="out-{{m.key}}"></div>
</div>
{% endfor %}
</div>
<div class="audit" id="audit"></div>
<script>
async function runAll(){
  const q = document.getElementById('q').value || '(空指令)';
  for (const m of {{models|tojson}}) {
    document.getElementById('st-'+m.key).textContent = '运行中…';
    const r = await fetch('/run', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({model:m.key, prompt:q})});
    const d = await r.json();
    document.getElementById('st-'+m.key).textContent = 'rc='+d.rc+' '+d.latency;
    document.getElementById('out-'+m.key).textContent = d.stdout || d.stderr || '(无输出)';
  }
}
async function runOne(key){
  const q = document.getElementById('q').value || '(空指令)';
  const r = await fetch('/run', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({model:key, prompt:q})});
  const d = await r.json();
  document.getElementById('st-'+key).textContent = 'rc='+d.rc+' '+d.latency;
  document.getElementById('out-'+key).textContent = d.stdout || d.stderr || '(无输出)';
}
async function auditSkills(){
  const r = await fetch('/audit-skills');
  const d = await r.json();
  document.getElementById('audit').textContent = d.output || '(无 skill 目录)';
}
</script>
</body>
</html>
"""


class ModelAdapter:
    """模型适配器: 优先真实 CLI, 无则规则降级(与材料4 行 82 ADAPTERS 同构)。"""

    def __init__(self, key: str, name: str, adapter: list, style: str):
        self.key = key
        self.name = name
        self.adapter = adapter
        self.style = style

    def available(self) -> bool:
        try:
            subprocess.run([self.adapter[0], "--version"],
                           capture_output=True, timeout=3)
            return True
        except Exception:
            return False

    def chat(self, prompt: str, activated: bool = False) -> dict:
        t0 = time.time()
        if self.available():
            try:
                p = subprocess.run(self.adapter + [prompt],
                                   capture_output=True, text=True, timeout=120)
                return {"rc": p.returncode, "stdout": p.stdout[-8000:],
                        "stderr": p.stderr[-2000:], "latency": f"{(time.time()-t0)*1000:.0f}ms"}
            except Exception as e:
                return {"rc": -1, "stdout": "", "stderr": str(e), "latency": "err"}
        # 规则降级: 冷咖啡激活 = 身份切换(回复内容不同, 非日志)
        if activated:
            identity = (f"[冷咖啡·{self.name}] 我是冷咖啡工作台, 大白话指令直接驱动。"
                        f"你的指令: {prompt} → 已按冷咖啡模式处理: 定位→分析→出方案")
        else:
            identity = f"[{self.style}] 收到: {prompt} (规则降级, 无真实 {self.name} CLI)"
        return {"rc": 0, "stdout": identity,
                "stderr": "", "latency": f"{(time.time()-t0)*1000:.0f}ms"}


class ActivationGate:
    """冷咖啡激活门控(与 v2 同源, 材料4 行 133: Skill 靠激活词触发)。"""

    @staticmethod
    def match(text: str) -> dict:
        norm = text.lower().replace(" ", "").replace("-", "")
        best, best_w = 0.0, None
        for w in ACTIVATION_WORDS:
            wn = w.lower().replace(" ", "").replace("-", "")
            score = 1.0 if wn in norm else 0.0
            if score > best:
                best, best_w = score, wn
        return {"activated": best >= ACTIVATION_THRESHOLD,
                "word": best_w, "score": best}


def create_app() -> "Flask":
    app = Flask(__name__)
    adapters = {m["key"]: ModelAdapter(**m) for m in VIDEO_MODELS}

    @app.get("/")
    def index():
        return render_template_string(INDEX_HTML, models=VIDEO_MODELS)

    @app.post("/run")
    def run():
        body = request.get_json(force=True)
        model, prompt = body.get("model"), body.get("prompt", "")
        gate = ActivationGate.match(prompt)
        note = f" [Skill 激活: {gate['word']}]" if gate["activated"] else ""
        if model not in adapters:
            return jsonify({"rc": 1, "stdout": "", "stderr": "未知模型", "latency": "0ms"}), 400
        r = adapters[model].chat(prompt, activated=gate["activated"])
        r["stdout"] = r["stdout"] + note
        return jsonify(r)

    @app.get("/audit-skills")
    def audit_skills():
        """审计脚本(材料4 行 108-122): 扫描常见 Agent skill 目录 SHA256 基线。"""
        lines = []
        for d in (Path.home() / ".claude" / "skills",
                  Path.home() / ".codex" / "skills",
                  Path.home() / ".claude" / "commands"):
            if not d.is_dir():
                continue
            lines.append(f"== {d} ==")
            for f in sorted(d.rglob("*.md")):
                try:
                    import hashlib
                    h = hashlib.sha256(f.read_bytes()).hexdigest()[:16]
                    lines.append(f"{h}  {f}")
                except Exception:
                    pass
        return jsonify({"output": "\n".join(lines) or "(未发现 skill 目录)"})

    return app


def main(argv=None) -> int:
    if not HAS_FLASK:
        print("需要 flask: pip install flask")
        return 1
    port = int(os.environ.get("PORT", "8899"))
    print(f"冷咖啡·四模型统一控制台 (BV1cc8L6XExs) @ http://localhost:{port}")
    print(f"  模型: {', '.join(m['name'] for m in VIDEO_MODELS)}")
    create_app().run(port=port, debug=False)


if __name__ == "__main__":
    main()
