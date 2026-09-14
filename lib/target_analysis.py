#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lib/target_analysis.py —— 目标情报集成

输入: 目标文件
输出: 完整分析报告 + 修改建议

串联: recon -> static_analysis -> 修改建议
只依赖 Python 3.8+ 标准库。
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List, Optional

# 确保 lib 可导入
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from recon import Recon  # noqa: E402
from static_analysis import StaticAnalyzer  # noqa: E402


class TargetAnalyzer:
    """目标情报分析器。"""

    def __init__(self, target: str) -> None:
        self.target = target
        self.recon = Recon(target)
        self.static = StaticAnalyzer(target)

    def analyze(self) -> Dict[str, Any]:
        """完整分析: 探测 + 静态 + 建议。"""
        rep = self.recon.report()
        stat = self.static.report()
        suggestions = self._suggestions(rep, stat)
        return {
            "target": self.target,
            "recon": rep,
            "static": stat,
            "suggestions": suggestions,
        }

    def _suggestions(self, rep: Dict[str, Any],
                     stat: Dict[str, Any]) -> List[Dict[str, Any]]:
        """根据分析结果生成修改建议。"""
        sug = []
        ft = rep.get("file_type", "?")

        # 1. 格式建议
        if ft == "PE":
            sug.append({
                "priority": "高",
                "action": "分析入口点与节表",
                "detail": f"PE 文件, 入口点 {rep.get('entry_point',{}).get('ep','?')}, "
                          f"节 {[s['name'] for s in rep.get('sections',{}).get('sections',[])[:4]]}",
            })
        elif ft == "ELF":
            sug.append({"priority": "高", "action": "分析 ELF 段与符号",
                        "detail": "ELF 格式, 用 readelf/objdump 深入"})

        # 2. 加壳建议
        pkg = rep.get("packed", {})
        if pkg.get("verdict") == "可疑":
            sug.append({"priority": "高", "action": "先脱壳再分析",
                        "detail": f"熵 {pkg.get('entropy')}, 特征 {pkg.get('markers')}"})
        else:
            sug.append({"priority": "中", "action": "直接静态分析",
                        "detail": "未见加壳特征"})

        # 3. 敏感字符串建议
        st = rep.get("strings", {})
        if st.get("sensitive"):
            sug.append({
                "priority": "中",
                "action": "追踪敏感字符串引用",
                "detail": f"敏感词 {st['sensitive'][:5]}, "
                          f"用 static_analysis 定位引用",
            })

        # 4. 校验逻辑建议
        chk = stat.get("checks", {})
        if chk.get("count"):
            first = chk["checks"][0]
            sug.append({
                "priority": "高",
                "action": f"NOP 掉校验跳转 @ {first['jmp_offset']:#x}",
                "detail": f"cmp@{first['cmp_offset']:#x} {first['cmp']} + "
                          f"{first['jmp']}@{first['jmp_offset']:#x}, "
                          f"用 patcher 改 {first['jmp']} 为 NOP",
            })
        else:
            sug.append({"priority": "中", "action": "手动确认校验逻辑",
                        "detail": "未自动识别 cmp+跳转, 需人工定位"})

        return sug

    def report_text(self) -> str:
        r = self.analyze()
        lines = []
        lines.append(f"=== 目标情报分析: {r['target']} ===")
        rc = r["recon"]
        lines.append(f"类型: {rc.get('file_type','?')} | "
                     f"架构: {rc.get('arch','?')} | "
                     f"大小: {rc.get('size',0)} 字节")
        pkg = rc.get("packed", {})
        lines.append(f"加壳: {pkg.get('verdict','?')} "
                     f"(熵 {pkg.get('entropy',0)})")
        st = rc.get("strings", {})
        lines.append(f"字符串: {st.get('total',0)} 个, "
                     f"敏感 {len(st.get('sensitive',[]))} 个")
        if st.get("sensitive"):
            lines.append(f"  敏感: {st['sensitive'][:6]}")
        imp = rc.get("imports", {})
        if imp.get("apis"):
            lines.append(f"导入 API: {imp['apis'][:6]}")
        sc = rc.get("sections", {})
        if sc.get("sections"):
            lines.append(f"节: {[s['name'] for s in sc['sections'][:6]]}")
        ep = rc.get("entry_point", {})
        if "ep" in ep:
            lines.append(f"入口点: {ep['ep']}")
        sa = r["static"]
        jg = sa.get("jump_graph", {})
        lines.append(f"跳转: {jg.get('count',0)} 条")
        chk = sa.get("checks", {})
        lines.append(f"校验逻辑: {chk.get('count',0)} 个")
        lines.append("")
        lines.append("=== 修改建议 ===")
        for s in r["suggestions"]:
            lines.append(f"[{s['priority']}] {s['action']}: {s['detail']}")
        return "\n".join(lines)


# ---------------------------------------------------------------- CLI
def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    p = argparse.ArgumentParser(prog="target-analysis")
    p.add_argument("target", help="目标文件")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    a = TargetAnalyzer(args.target)
    if args.json:
        print(json.dumps(a.analyze(), ensure_ascii=False, indent=2))
    else:
        print(a.report_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
