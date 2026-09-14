#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
04-skill-ban-analysis —— skill 封号机制(检测点分析 + 规避成本评估)

评论区提到能力: "skill 绕过包封号"。
机制(学术研究向): 分析 agent 框架对 skill 目录注入的检测能力与规避成本。
  - 检测点清单: 平台/框架可能部署的检测点
  - 检测点扫描: 对给定 skill 目录算每个检测点的风险分
  - 规避成本评估: 每个检测点的规避难度 + 综合成本

边界: 学术分析, 不含真实规避载荷; 测试本地 mock。
只依赖 Python 3.8+ 标准库。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any, Dict, List, Optional

# 检测点清单(学术模型: 平台可能部署的检测点)
DETECTION_POINTS = [
    {
        "id": "dir_hash_baseline",
        "name": "目录哈希基线",
        "principle": "平台记录 skills 目录初始哈希, 变动即告警",
        "reliability": 0.9,
        "evade_cost": "高",
        "evade_note": "需保持目录与基线一致, 或伪造哈希",
    },
    {
        "id": "file_mtime",
        "name": "文件修改时间",
        "principle": "检测 SKILL.md 的 mtime 异常(非安装时间)",
        "reliability": 0.6,
        "evade_cost": "低",
        "evade_note": "可还原 mtime",
    },
    {
        "id": "content_feature",
        "name": "内容特征",
        "principle": "扫描 SKILL.md 里的越界关键词/指令模式",
        "reliability": 0.7,
        "evade_cost": "中",
        "evade_note": "需改写措辞绕过关键词过滤",
    },
    {
        "id": "external_domain",
        "name": "外联域名",
        "principle": "检测 skill 引用的外部域名是否可疑",
        "reliability": 0.8,
        "evade_cost": "中",
        "evade_note": "需用正常域名或去除外联",
    },
    {
        "id": "behavior_log",
        "name": "行为日志",
        "principle": "检测模型行为是否偏离基线(异常指令跟随)",
        "reliability": 0.85,
        "evade_cost": "高",
        "evade_note": "需让行为与正常会话一致",
    },
    {
        "id": "account_correlation",
        "name": "多账号关联",
        "principle": "同一用户/设备多账号同 skill 指纹关联",
        "reliability": 0.75,
        "evade_cost": "高",
        "evade_note": "需隔离账号/设备指纹",
    },
]

COST_LEVELS = {"低": 1, "中": 2, "高": 3}


class BanAnalyzer:
    """封号机制分析器: 检测点扫描 + 规避成本评估。"""

    def __init__(self, detection_points: Optional[List[Dict[str, Any]]] = None) -> None:
        self.points = detection_points or DETECTION_POINTS

    # -- 检测点扫描 ------------------------------------------------------
    def scan(self, skill_dir: str) -> Dict[str, Any]:
        """对 skill 目录跑所有检测点, 输出每个的风险分。"""
        r = {"ok": False, "detail": "", "dir": skill_dir, "results": []}
        if not os.path.isdir(skill_dir):
            r["detail"] = f"目录不存在: {skill_dir}"
            return r

        results = []
        for p in self.points:
            risk = self._eval_point(p["id"], skill_dir, p["reliability"])
            results.append({
                "id": p["id"],
                "name": p["name"],
                "principle": p["principle"],
                "reliability": p["reliability"],
                "risk": risk,
                "risk_label": "高" if risk >= 0.7 else ("中" if risk >= 0.4 else "低"),
                "evade_cost": p["evade_cost"],
                "evade_note": p["evade_note"],
            })
        avg = sum(x["risk"] for x in results) / len(results)
        r["ok"] = True
        r["results"] = results
        r["avg_risk"] = round(avg, 3)
        r["detail"] = (f"扫描 {skill_dir}: {len(results)} 个检测点, "
                       f"平均风险 {avg:.2f}")
        return r

    def _eval_point(self, point_id: str, skill_dir: str, reliability: float) -> float:
        """每个检测点的风险分(0-1): 基于实际文件状态。"""
        # 简化模型: 有 SKILL.md 且非空 -> 基础风险; 有外联 -> 加分; 有敏感词 -> 加分
        base = 0.3
        skill_md = os.path.join(skill_dir, "SKILL.md")
        if os.path.exists(skill_md):
            base += 0.3
            try:
                content = open(skill_md, encoding="utf-8", errors="ignore").read()
            except OSError:
                content = ""
            # 外联检测
            if re.search(r"https?://[^\s\"']+", content):
                base += 0.2
            # 敏感词检测
            if re.search(r"破解|绕过|卡密|外挂|注入", content):
                base += 0.2
        return round(min(1.0, base * (0.5 + reliability * 0.5)), 3)

    # -- 规避成本评估 ------------------------------------------------------
    def evade_cost(self, scan_result: Dict[str, Any]) -> Dict[str, Any]:
        """综合规避成本评估。"""
        results = scan_result.get("results", [])
        if not results:
            return {"ok": False, "detail": "先扫描"}
        total = sum(COST_LEVELS.get(x["evade_cost"], 2) for x in results)
        max_cost = len(results) * 3
        ratio = round(total / max_cost, 3)
        level = "高" if ratio >= 0.7 else ("中" if ratio >= 0.4 else "低")
        high_risk = [x for x in results if x["risk"] >= 0.7]
        return {
            "ok": True,
            "total_cost": total,
            "max_cost": max_cost,
            "cost_ratio": ratio,
            "cost_level": level,
            "high_risk_points": [x["id"] for x in high_risk],
            "detail": (f"规避成本: {level}({total}/{max_cost}), "
                       f"高风险检测点 {len(high_risk)} 个"),
        }

    # -- 报告 ------------------------------------------------------------
    def report(self, skill_dir: str) -> Dict[str, Any]:
        scan = self.scan(skill_dir)
        cost = self.evade_cost(scan) if scan["ok"] else {"ok": False}
        return {"scan": scan, "cost": cost}


# ---------------------------------------------------------------- CLI

def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    p = argparse.ArgumentParser(prog="skill-ban-analysis")
    p.add_argument("skill_dir", help="要分析的 skill 目录")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    a = BanAnalyzer()
    r = a.report(args.skill_dir)
    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        if not r["scan"]["ok"]:
            print(r["scan"]["detail"])
            return 1
        print(f"=== 检测点分析: {args.skill_dir} ===")
        for x in r["scan"]["results"]:
            print(f"  [{x['risk_label']}] {x['name']:<8} 风险={x['risk']} "
                  f"规避难度={x['evade_cost']} | {x['principle']}")
        print(f"\n=== 规避成本评估 ===")
        print(r["cost"]["detail"])
        print(f"高风险检测点: {r['cost']['high_risk_points']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
