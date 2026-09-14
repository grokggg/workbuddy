#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lib/countermeasure.py —— 应对模块

输入: 保护机制清单(recon_v2 输出)
输出: 每个机制的应对思路 + 可行性评估 + 实现框架

边界: 学术研究向, 应对框架不含针对具体商业软件的可执行载荷。
只依赖 Python 3.8+ 标准库。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# 应对知识库: 保护机制 -> 应对思路
COUNTERMEASURES: Dict[str, List[Dict[str, Any]]] = {
    "加壳(UPX)": [
        {
            "approach": "UPX 自带脱壳: upx -d",
            "feasibility": "高(UPX 支持 -d)",
            "framework": ["which upx && upx -d target", "验证: 重新探测熵是否下降"],
        },
        {
            "approach": "内存转储 + 修复 IAT(手动脱壳)",
            "feasibility": "中(需 OllyDbg/x64dbg)",
            "framework": ["附加进程", "内存 dump", "IAT 修复(impREC)"],
        },
    ],
    "加壳(VMProtect/Themida)": [
        {
            "approach": "虚拟化代码定位(VM 入口分析)",
            "feasibility": "低(需高级逆向)",
            "framework": ["找 VM 入口(特征: push 大常数序列)",
                          "分析 handler 分派表", "符号化执行还原"],
        },
        {
            "approach": "运行期内存 patch(不脱壳)",
            "feasibility": "中",
            "framework": ["附加调试器", "断在校验点", "内存 patch", "dump"],
        },
    ],
    "反调试": [
        {
            "approach": "静态 patch 检测点(IsDebuggerPresent 返回改 0)",
            "feasibility": "高",
            "framework": ["定位 IsDebuggerPresent call", "NOP 掉或改 eax=0",
                          "验证: 检测点不再触发"],
        },
        {
            "approach": "时间差检测对抗(忽略单步时间戳)",
            "feasibility": "中",
            "framework": ["Hook GetTickCount/QPC", "固定返回值",
                          "或用 ScyllaHide 类插件"],
        },
    ],
    "反VM": [
        {
            "approach": "CPUID 结果伪造",
            "feasibility": "中(需 hypervisor 层)",
            "framework": ["VMM 层拦截 CPUID leaf 1", "清 hypervisor bit",
                          "伪造 vendor 字符串"],
        },
        {
            "approach": "特征隐藏(设备名/进程/注册表)",
            "feasibility": "低(VM 特征多且深)",
            "framework": ["枚举特征点", "逐个隐藏/改名", "或用裸机/真实硬件"],
        },
    ],
    "完整性校验": [
        {
            "approach": "定位校验点 + patch 比较结果",
            "feasibility": "中",
            "framework": ["找 checksum/hash 调用", "NOP 掉比较分支",
                          "验证: 修改后校验通过"],
        },
        {
            "approach": "保持文件不变, 运行期内存 hook",
            "feasibility": "高(不改文件不触发)",
            "framework": ["附加进程", "hook 校验函数", "返回通过值"],
        },
    ],
    "反重打包": [
        {
            "approach": "签名重签(仅自有/授权场景)",
            "feasibility": "中",
            "framework": ["提取原签名", "重打包后重签", "验证签名链"],
        },
        {
            "approach": "完整性校验 patch(asar 场景)",
            "feasibility": "中",
            "framework": ["定位校验逻辑", "patch 比较分支", "验证不触发"],
        },
    ],
}


class Countermeasure:
    """应对模块: 根据检测结果给出应对思路。"""

    def __init__(self, recon_report: Optional[Dict[str, Any]] = None) -> None:
        self.recon = recon_report or {}

    def _classify(self) -> List[str]:
        """从 recon 报告提取保护机制类别。"""
        cats = []
        if not self.recon:
            return cats
        pk = self.recon.get("packer", {})
        if pk.get("packed") or pk.get("verdict") == "加壳":
            markers = pk.get("markers", [])
            if any("VMProtect" in m or "Themida" in m for m in markers):
                cats.append("加壳(VMProtect/Themida)")
            elif any("UPX" in m for m in markers):
                cats.append("加壳(UPX)")
            else:
                cats.append("加壳(未知)")
        ad = self.recon.get("antidebug", {}).get("detected", [])
        if ad:
            cats.append("反调试")
        av = self.recon.get("antivm", {}).get("detected", [])
        if av:
            cats.append("反VM")
        ig = self.recon.get("integrity", {}).get("detected", [])
        if ig:
            cats.append("完整性校验")
        ar = self.recon.get("anti_repack", {}).get("detected", [])
        if ar:
            cats.append("反重打包")
        return cats

    def plan(self) -> Dict[str, Any]:
        """生成应对计划。"""
        cats = self._classify()
        if not cats:
            return {"ok": True, "note": "未检出保护机制, 无应对计划",
                    "categories": []}
        plans = []
        for c in cats:
            known = COUNTERMEASURES.get(c)
            if not known:
                # 退化: 按主类匹配
                main_cat = c.split("(")[0]
                for k, v in COUNTERMEASURES.items():
                    if k.split("(")[0] == main_cat:
                        known = v
                        break
            if not known:
                known = [{"approach": f"研究 {c} 的识别与应对",
                          "feasibility": "未知", "framework": ["先做 recon 细化"]}]
            plans.append({"category": c, "options": known})
        return {"ok": True, "categories": cats, "plans": plans}

    def plan_text(self) -> str:
        r = self.plan()
        lines = []
        lines.append("=== 应对计划 ===")
        if not r.get("categories"):
            lines.append("  未检出保护机制")
            return "\n".join(lines)
        for p in r["plans"]:
            lines.append(f"\n[{p['category']}]")
            for o in p["options"]:
                lines.append(f"  思路: {o['approach']}")
                lines.append(f"  可行性: {o['feasibility']}")
                for f in o["framework"]:
                    lines.append(f"    步骤: {f}")
        return "\n".join(lines)


# ---------------------------------------------------------------- CLI
def main(argv: Optional[List[str]] = None) -> int:
    import argparse, json, os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from recon_v2 import ReconV2

    p = argparse.ArgumentParser(prog="countermeasure")
    p.add_argument("target", help="目标文件(自动先探测)")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    r = ReconV2(args.target)
    rep = r.report()
    cm = Countermeasure(rep)
    if args.json:
        print(json.dumps({"recon": rep, "plan": cm.plan()},
                         ensure_ascii=False, indent=2))
    else:
        pk = rep["packer"]
        print(f"检测: {pk['verdict']} | 反调试: {rep['antidebug']['detected']} "
              f"| 反VM: {rep['antivm']['detected']}")
        print(cm.plan_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
