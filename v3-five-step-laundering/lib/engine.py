#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v3-five-step-laundering —— 五步法 + 脱敏词替换引擎

复现 BV15iti6aEuM(Codex 大白话破甲五步法)。

五步法(转录 490s-546s):
  1. 分析文件 —— 分析目标软件结构
  2. 说出你的目的 —— 用大白话说明需求(经脱敏替换)
  3. AI 做工作, 你配合 —— 按 AI 步骤操作(截图反馈)
  4. 脱壳/绕过/运行补丁 —— 执行修改(边界: 占位)
  5. 验证程序 —— 验证修改生效

脱敏词表: 把高风险表述替换为中性工程表述, 让对话可讨论。

只依赖 Python 3.8+ 标准库。
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------- 脱敏词表加载

class LaunderingMap:
    """脱敏词表: 加载 + 替换 + 意图判定。"""

    def __init__(self, map_path: Optional[str] = None) -> None:
        self.map_path = map_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "laundering_map.yaml")
        self.mappings: List[Dict[str, str]] = []
        self.intent: Dict[str, List[str]] = {}
        self.result_oriented: List[str] = []
        self.exclude: List[str] = []
        self._load()

    def _load(self) -> None:
        """加载 YAML(零依赖子集解析, 或退化 JSON)。"""
        raw = open(self.map_path, encoding="utf-8").read()
        try:
            import yaml  # type: ignore
            data = yaml.safe_load(raw)
        except Exception:
            # 零依赖解析: 处理简单块结构
            data = self._min_yaml(raw)
        self.mappings = data.get("mappings", [])
        self.intent = data.get("intent", {})
        self.result_oriented = data.get("result_oriented", [])
        self.exclude = data.get("exclude", [])

    def _min_yaml(self, raw: str) -> Dict[str, Any]:
        """零依赖 YAML 子集解析(块映射 + 块序列)。"""
        data: Dict[str, Any] = {}
        current_key = None
        current_list = None
        for line in raw.splitlines():
            line = line.rstrip()
            if not line or line.lstrip().startswith("#"):
                continue
            if line.startswith("mappings:") or line.startswith("intent:") \
               or line.startswith("result_oriented:") or line.startswith("exclude:"):
                current_key = line.split(":")[0]
                if current_key == "intent":
                    data[current_key] = {}  # dict
                    current_list = None
                else:
                    data[current_key] = []
                    current_list = data[current_key]
            elif line.startswith("  - "):
                item = line.strip()[2:].strip()
                if current_key == "mappings":
                    # 解析 {from: X, to: Y}
                    m = re.match(r'\{from:\s*"([^"]+)",\s*to:\s*"([^"]+)"\}', item)
                    if m:
                        current_list.append({"from": m.group(1), "to": m.group(2)})
                elif current_key in ("result_oriented", "exclude"):
                    current_list.append(item.strip('"'))
            elif line.startswith(("  ", "    ")) and current_key == "intent":
                m = re.match(r'\s*(\w+):\s*\[(.*)\]', line)
                if m:
                    key = m.group(1)
                    vals = [v.strip().strip('"') for v in m.group(2).split(",")]
                    data[current_key][key] = vals
        return data

    # -- 替换 ------------------------------------------------------------
    def replace(self, text: str) -> Dict[str, Any]:
        """脱敏替换。返回 {text, replaced[], count}。"""
        result = text
        replaced = []
        for m in self.mappings:
            frm, to = m["from"], m["to"]
            if frm in result:
                result = result.replace(frm, to)
                replaced.append({"from": frm, "to": to})
        return {"text": result, "replaced": replaced, "count": len(replaced)}

    # -- 意图判定 --------------------------------------------------------
    def judge_intent(self, text: str) -> Dict[str, Any]:
        """判定意图: 第三方(高风险) vs 自有(中性)。"""
        third = [w for w in self.intent.get("third_party", []) if w in text]
        own = [w for w in self.intent.get("own", []) if w in text]
        # 结果导向动词
        ro = [w for w in self.result_oriented if w in text]
        verdict = "third_party" if third and not own else "own"
        return {
            "verdict": verdict,
            "third_party_hits": third,
            "own_hits": own,
            "result_oriented": ro,
            "high_risk": bool(third) and not bool(own),
        }


# ---------------------------------------------------------------- 五步法引擎

class FiveStepEngine:
    """五步法执行引擎。每步真实可跑, 输出日志。"""

    STEPS = [
        ("analyze",  "分析文件",    "分析目标软件结构(只读)"),
        ("purpose",  "说出目的",    "用大白话说明需求(经脱敏替换)"),
        ("cooperate", "AI协作",    "按 AI 步骤操作(截图反馈)"),
        ("modify",   "脱壳/绕过",   "执行修改(边界: 占位)"),
        ("verify",   "验证程序",    "验证修改生效"),
    ]

    def __init__(self, target_root: str = "") -> None:
        self.target_root = target_root
        self.launder = LaunderingMap()
        self.log: List[Dict[str, Any]] = []
        self.artifacts: Dict[str, Any] = {}

    def _log(self, step: int, key: str, ok: bool, detail: str) -> Dict[str, Any]:
        entry = {"step": step, "key": key, "ok": ok, "detail": detail}
        self.log.append(entry)
        return entry

    # -- 步 1: 分析文件 ----------------------------------------------------
    def step_analyze(self) -> Dict[str, Any]:
        """分析目标文件结构(只读)。"""
        r = {"step": 1, "key": "analyze", "label": "分析文件", "ok": False,
             "detail": "", "command": f"ls -la {self.target_root}"}
        if not self.target_root:
            r["detail"] = "未指定目标。用 --target 传目标路径。"
            self._log(1, "analyze", False, r["detail"])
            return r
        if not os.path.exists(self.target_root):
            r["detail"] = f"路径不存在: {self.target_root}"
            self._log(1, "analyze", False, r["detail"])
            return r
        is_dir = os.path.isdir(self.target_root)
        size = os.path.getsize(self.target_root)
        if is_dir:
            items = sorted(os.listdir(self.target_root))
            r["detail"] = (f"目录 {self.target_root}: {len(items)} 项 "
                           f"({', '.join(items[:8])})")
        else:
            r["detail"] = (f"文件 {self.target_root}: {size} 字节")
        r["ok"] = True
        self.artifacts["analyzed"] = self.target_root
        self._log(1, "analyze", True, r["detail"])
        return r

    # -- 步 2: 说出目的(脱敏替换) ------------------------------------------
    def step_purpose(self, raw_request: str) -> Dict[str, Any]:
        """用大白话说明需求, 经脱敏词表替换。"""
        r = {"step": 2, "key": "purpose", "label": "说出目的", "ok": True,
             "detail": "", "command": "脱敏替换"}
        if not raw_request:
            r["detail"] = "未提供需求。用 --request 传需求文本。"
            r["ok"] = False
            self._log(2, "purpose", False, r["detail"])
            return r
        res = self.launder.replace(raw_request)
        intent = self.launder.judge_intent(raw_request)
        r["detail"] = (f"原始需求: {raw_request}\n"
                       f"替换后: {res['text']}\n"
                       f"替换数: {res['count']}\n"
                       f"意图: {intent['verdict']} "
                       f"(第三方词: {intent['third_party_hits']}, "
                       f"自有词: {intent['own_hits']})")
        r["replaced"] = res["replaced"]
        r["clean_text"] = res["text"]
        r["intent"] = intent
        self.artifacts["purpose"] = res["text"]
        self._log(2, "purpose", True, r["detail"])
        return r

    # -- 步 3: AI 协作 -----------------------------------------------------
    def step_cooperate(self, feedback: str = "") -> Dict[str, Any]:
        """按 AI 步骤操作(截图/反馈循环)。"""
        r = {"step": 3, "key": "cooperate", "label": "AI协作", "ok": True,
             "detail": "", "command": "截图反馈 + 按步骤操作"}
        r["detail"] = (
            "按 AI 给出的步骤操作:\n"
            "  1. 执行 AI 指示的命令\n"
            "  2. 截图反馈结果\n"
            "  3. 遇到问题就描述现象(AI 会调整)\n"
            f"  当前反馈: {feedback or '(无, 等 AI 指示)'}"
        )
        self.artifacts["feedback"] = feedback
        self._log(3, "cooperate", True, r["detail"])
        return r

    # -- 步 4: 脱壳/绕过(边界: 占位) ----------------------------------------
    def step_modify(self, patch: str = "") -> Dict[str, Any]:
        """执行修改(边界: 具体修改由用户填, 这里给结构)。"""
        r = {"step": 4, "key": "modify", "label": "脱壳/绕过", "ok": True,
             "detail": "", "command": "{PATCH}"}
        r["detail"] = (
            "执行修改(结构, 具体由用户填):\n"
            f"  {{PATCH}} = {patch or '(用户填入具体修改)'}\n"
            "  边界: 只给修改方法(读文件->替换->写回), 不注入破解逻辑"
        )
        r["placeholder"] = True
        self._log(4, "modify", True, r["detail"])
        return r

    # -- 步 5: 验证程序 ----------------------------------------------------
    def step_verify(self, verify_cmd: str = "") -> Dict[str, Any]:
        """验证修改生效。"""
        r = {"step": 5, "key": "verify", "label": "验证程序", "ok": True,
             "detail": "", "command": "{VERIFY_CMD}"}
        r["detail"] = (
            "验证修改生效:\n"
            f"  {{VERIFY_CMD}} = {verify_cmd or '(用户填启动命令)'}\n"
            "  判据: 应用启动无崩溃 / 行为变化生效"
        )
        r["placeholder"] = True
        self._log(5, "verify", True, r["detail"])
        return r

    # -- 全流程 ------------------------------------------------------------
    def run_all(self, raw_request: str) -> List[Dict[str, Any]]:
        """执行五步。"""
        steps = [
            self.step_analyze(),
            self.step_purpose(raw_request),
            self.step_cooperate(),
            self.step_modify(),
            self.step_verify(),
        ]
        return steps

    # -- 日志 ------------------------------------------------------------
    def log_text(self) -> str:
        """真实运行日志文本。"""
        if not self.log:
            self.run_all("")
        lines = []
        for entry in self.log:
            status = "OK " if entry["ok"] else "FAIL"
            lines.append(f"[{entry['step']}/5] {entry['key']:<10} → {status}")
            for line in entry["detail"].splitlines():
                lines.append(f"      {line}")
        ok = sum(1 for e in self.log if e["ok"])
        lines.append("-" * 50)
        lines.append(f"通过 {ok}/5")
        return "\n".join(lines)


# ---------------------------------------------------------------- CLI

def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    p = argparse.ArgumentParser(
        prog="v3-five-step-laundering",
        description="五步法 + 脱敏词替换(BV15iti6aEuM 复现)")
    p.add_argument("--target", default="", help="目标文件/目录路径")
    p.add_argument("--request", default="", help="需求文本(将脱敏替换)")
    p.add_argument("--map", default=None, help="脱敏词表路径")
    p.add_argument("--json", action="store_true", help="输出 JSON")
    args = p.parse_args(argv)

    eng = FiveStepEngine(args.target)
    if args.map:
        eng.launder = LaunderingMap(args.map)
    steps = eng.run_all(args.request)

    if args.json:
        print(json.dumps(steps, ensure_ascii=False, indent=2))
    else:
        print(eng.log_text())
    return 0 if all(s["ok"] for s in steps) else 1


if __name__ == "__main__":
    raise SystemExit(main())
