#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lib/llm_engine.py —— 本地 LLM 推理引擎(双模式)

模式 A(真实 LLM): 通过 Ollama 或 llama.cpp 调用本地模型
  - Ollama:  http://localhost:11434/api/generate
  - llama.cpp: http://localhost:8080/completion
模式 B(规则推理): 无 LLM 时降级, 基于 recon 报告的启发式推理
  - 每个保护机制 -> 绕过思路 + 可行性 + 工具链(知识库驱动)

设计原则: 永远有可运行的退化路径(dynamic_debug 同款哲学)。
只依赖 Python 3.8+ 标准库。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.request
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------- 推理知识库

# 保护机制 -> 绕过思路(自然语言 + 伪代码) + 可行性 + 工具链
BYPASS_KB: Dict[str, Dict[str, Any]] = {
    "加壳(UPX)": {
        "思路": "UPX 自带脱壳器, 优先用 upx -d; 失败则内存转储修复 IAT",
        "伪代码": [
            "// 方式1: 官方脱壳",
            "upx -d {TARGET}",
            "// 方式2: 内存转储",
            "1. attach 到进程, 等 OEP",
            "2. dump 内存镜像",
            "3. 用 impREC/Scylla 修复 IAT",
        ],
        "可行性": 0.9,
        "工具链": ["upx", "x64dbg", "Scylla"],
        "理由": "UPX 是开源壳, 有官方 -d; 脱壳后熵应回到原始水平",
    },
    "加壳(VMProtect/Themida)": {
        "思路": "虚拟化代码不适合静态还原, 优先运行时 patch 校验点",
        "伪代码": [
            "// 策略: 不脱壳, 运行期 patch",
            "1. 定位校验分支(通常是 cmp+jcc)",
            "2. 在 jcc 处下断点",
            "3. 修改标志位/ZF 使校验通过",
            "4. 或直接 NOP 掉跳转",
        ],
        "可行性": 0.4,
        "工具链": ["x64dbg", "Cheat Engine", "de4dot(仅.NET)"],
        "理由": "VM 指令还原需符号执行(低可行); 运行时 patch 绕过 VM 校验是常用路径",
    },
    "反调试": {
        "思路": "静态 patch 检测点 API 的返回, 或 hook 时间函数",
        "伪代码": [
            "// IsDebuggerPresent 返回改 0",
            "patch: mov eax, 0  (替换 call 后的分支)",
            "// 时间差检测 hook",
            "Hook GetTickCount/QueryPerformanceCounter, 固定返回值",
        ],
        "可行性": 0.8,
        "工具链": ["x64dbg", "ScyllaHide", "API Monitor"],
        "理由": "检测点数量有限且模式固定, patch 成本低; ScyllaHide 自动处理多数",
    },
    "反VM": {
        "思路": "CPUID 结果伪造(需 hypervisor), 或特征隐藏; 最省事是裸机/真实硬件",
        "伪代码": [
            "// CPUID leaf 1 清 hypervisor bit",
            "在 VMM 层拦截 CPUID",
            "// 或直接换环境",
            "用真实硬件/裸机运行, 不修二进制",
        ],
        "可行性": 0.3,
        "工具链": ["VMWare 配置修改", "QEMU -cpu host"],
        "理由": "VM 检测面广(设备/进程/注册表), 伪造成本高; 换环境最直接",
    },
    "完整性校验": {
        "思路": "保持文件不变 + 运行时 hook 校验函数(避免触发文件级检测)",
        "伪代码": [
            "// 方式1: hook 校验函数返回通过",
            "hook(check_fn) { return PASS; }",
            "// 方式2: 定位比较分支 patch",
            "在 checksum 比较的 jcc 处 NOP",
        ],
        "可行性": 0.6,
        "工具链": ["Frida", "x64dbg", "API Monitor"],
        "理由": "运行时 hook 不改文件, 绕过文件哈希; Frida 可脚本化",
    },
    "卡密校验(行为型)": {
        "思路": "定位 cmp 立即数比较指令, patch 条件跳转(je->jmp 或 NOP)",
        "伪代码": [
            "// 1. 找 cmp eax, imm32 + je 模式(analysis_v2 已定位)",
            "// 2. patch je(74) -> jmp(EB) 无条件跳成功分支",
            "// 3. 若目标有完整性校验, 同时 patch 校验 je",
        ],
        "可行性": 0.9,
        "工具链": ["patcher.py", "analysis_v2", "x64dbg"],
        "理由": "卡密比较是固定模式, patch 条件跳转成本最低, M26 已验证",
    },
    "反重打包": {
        "思路": "签名重签(自有场景)或 patch 签名校验分支",
        "伪代码": [
            "// asar 场景: 定位签名校验",
            "1. 搜索 signature_check/integrity_verify",
            "2. patch 比较分支",
            "3. 或重签(需原签名密钥)",
        ],
        "可行性": 0.5,
        "工具链": ["asar CLI", "签名工具", "x64dbg"],
        "理由": "重签需密钥(受限); patch 校验分支通用但会破坏其他保护",
    },
}

# 默认应对(未识别保护)
DEFAULT_BYPASS: Dict[str, Any] = {
    "思路": "未识别特定保护, 先做动态观察确认实际行为",
    "伪代码": ["1. 沙箱运行, 记录文件/网络/注册表行为", "2. 根据行为调整策略"],
    "可行性": 0.5,
    "工具链": ["ProcMon", "Wireshark", "沙箱"],
    "理由": "无特征时不应盲改, 行为分析优先",
}


# ---------------------------------------------------------------- LLM 客户端

class LLMClient:
    """本地 LLM 客户端(Ollama / llama.cpp)。"""

    def __init__(self, backend: str = "ollama",
                 model: str = "qwen2.5:7b",
                 base_url: Optional[str] = None) -> None:
        self.backend = backend
        self.model = model
        self.base_url = base_url or (
            "http://localhost:11434" if backend == "ollama"
            else "http://localhost:8080")

    def available(self) -> bool:
        try:
            if self.backend == "ollama":
                url = f"{self.base_url}/api/tags"
            else:
                url = f"{self.base_url}/health"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=3) as r:
                return r.status == 200
        except Exception:
            return False

    def generate(self, prompt: str, timeout: int = 120) -> str:
        """调用本地 LLM 生成文本。"""
        if self.backend == "ollama":
            url = f"{self.base_url}/api/generate"
            payload = json.dumps({"model": self.model, "prompt": prompt,
                                  "stream": False}).encode()
            req = urllib.request.Request(
                url, data=payload,
                headers={"Content-Type": "application/json"})
        else:  # llama.cpp
            url = f"{self.base_url}/completion"
            payload = json.dumps({"prompt": prompt, "n_predict": 1024,
                                  "stream": False}).encode()
            req = urllib.request.Request(
                url, data=payload,
                headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read())
        return d.get("response", "") or d.get("content", "")


# ---------------------------------------------------------------- 推理引擎

class LLMAnalyzer:
    """LLM 驱动分析引擎: recon 报告 -> 绕过策略。"""

    def __init__(self, llm: Optional[LLMClient] = None) -> None:
        self.llm = llm or LLMClient()
        self.llm_available = self.llm.available()

    # -- 从 recon 报告提取保护类别 ----------------------------------------
    def _extract_protections(self, recon: Dict[str, Any]) -> List[str]:
        cats = []
        pk = recon.get("packer", {})
        if pk.get("packed") or pk.get("verdict") == "加壳":
            markers = pk.get("markers", [])
            if any("VMProtect" in m or "Themida" in m for m in markers):
                cats.append("加壳(VMProtect/Themida)")
            elif any("UPX" in m for m in markers):
                cats.append("加壳(UPX)")
            else:
                cats.append("加壳(未知)")
        if recon.get("antidebug", {}).get("detected"):
            cats.append("反调试")
        if recon.get("antivm", {}).get("detected"):
            cats.append("反VM")
        if recon.get("integrity", {}).get("detected"):
            cats.append("完整性校验")
        if recon.get("anti_repack", {}).get("detected"):
            cats.append("反重打包")
        # M27: 行为型校验补充 —— 卡密 cmp 定位(analysis_v2 的 cmp-imm32 信号)
        if not cats and recon.get("static", {}).get("count", 0) >= 1:
            cats.append("卡密校验(行为型)")
        return cats

    # -- 规则推理(降级路径) -----------------------------------------------
    def _rule_reason(self, protections: List[str]) -> List[Dict[str, Any]]:
        strategies = []
        for p in protections:
            kb = BYPASS_KB.get(p) or BYPASS_KB.get(
                "加壳(未知)" if p == "加壳(未知)" else p) or DEFAULT_BYPASS
            strategies.append({
                "protection": p,
                "思路": kb["思路"],
                "伪代码": kb["伪代码"],
                "可行性": kb["可行性"],
                "工具链": kb["工具链"],
                "理由": kb["理由"],
                "来源": "规则推理",
            })
        # 按可行性排序(高优先)
        strategies.sort(key=lambda s: s["可行性"], reverse=True)
        return strategies

    # -- LLM 推理(真实路径) -----------------------------------------------
    def _llm_reason(self, recon: Dict[str, Any],
                    protections: List[str]) -> List[Dict[str, Any]]:
        prompt = self._build_prompt(recon, protections)
        raw = self.llm.generate(prompt)
        # 解析 LLM 输出(期望 JSON 数组)
        strategies = []
        try:
            start = raw.find("[")
            end = raw.rfind("]")
            if start != -1 and end != -1:
                parsed = json.loads(raw[start:end + 1])
                for item in parsed:
                    strategies.append({
                        "protection": item.get("protection", ""),
                        "思路": item.get("思路", item.get("idea", "")),
                        "伪代码": item.get("伪代码", item.get("pseudocode", [])),
                        "可行性": item.get("可行性", item.get("feasibility", 0.5)),
                        "工具链": item.get("工具链", item.get("tools", [])),
                        "理由": item.get("理由", item.get("reason", "")),
                        "来源": "LLM",
                    })
        except (json.JSONDecodeError, ValueError):
            # LLM 输出非 JSON, 包成一条
            strategies = [{
                "protection": ", ".join(protections) or "整体",
                "思路": raw[:500],
                "伪代码": [],
                "可行性": 0.5,
                "工具链": [],
                "理由": "LLM 原始输出",
                "来源": "LLM",
            }]
        strategies.sort(key=lambda s: s["可行性"], reverse=True)
        return strategies

    def _build_prompt(self, recon: Dict[str, Any],
                      protections: List[str]) -> str:
        """构建 LLM 提示词(机制中性, 学术研究向)。"""
        return f"""你是二进制安全分析助手。根据以下目标保护机制检测报告, 生成应对策略。
要求:
1. 每个保护机制给: 思路(自然语言) + 伪代码 + 可行性(0-1) + 工具链
2. 按可行性从高到低排序
3. 只输出 JSON 数组, 格式:
[{{"protection": "类别", "思路": "...", "伪代码": ["..."], "可行性": 0.8, "工具链": ["..."], "理由": "..."}}]

检测报告:
{json.dumps(recon, ensure_ascii=False, indent=2)[:4000]}

识别到的保护: {protections}
"""

    # -- 生成绕过脚本骨架 ----------------------------------------------------
    def _gen_script_skeleton(self, strategies: List[Dict[str, Any]],
                             target: str) -> str:
        """基于策略生成可执行脚本骨架(占位符版)。"""
        lines = ["#!/usr/bin/env python3",
                 "# 自动生成的绕过脚本骨架(占位符版, 需按目标填充)",
                 "# 由 M25 LLM 分析引擎生成", "", "import sys", "",
                 f"TARGET = {json.dumps(target)}", ""]
        for i, s in enumerate(strategies):
            lines.append(f"# ==== 策略 {i+1}: {s['protection']} (可行性 {s['可行性']}) ====")
            lines.append(f"# 思路: {s['思路']}")
            for line in s.get("伪代码", []):
                lines.append(f"#   {line}")
            lines.append(f"# 工具链: {', '.join(s.get('工具链', []))}")
            lines.append("def strategy_{}(target):".format(i + 1))
            lines.append("    # TODO: 填充实际实现")
            lines.append(f"    print(f'[策略{i+1}] {s['protection']}: 待实现')")
            lines.append("    return False")
            lines.append("")
        lines.append("if __name__ == '__main__':")
        lines.append("    print('M25 脚本骨架: 修改对应 strategy_N 后运行')")
        return "\n".join(lines)

    # -- 主入口 ----------------------------------------------------------------
    def analyze(self, recon: Dict[str, Any],
                target: str = "") -> Dict[str, Any]:
        protections = self._extract_protections(recon)
        if self.llm_available:
            strategies = self._llm_reason(recon, protections)
            engine = "LLM"
        else:
            strategies = self._rule_reason(protections)
            engine = "规则推理(降级)"
        skeleton = self._gen_script_skeleton(strategies, target)
        return {
            "engine": engine,
            "llm_available": self.llm_available,
            "protections": protections,
            "strategies": strategies,
            "script_skeleton": skeleton,
        }


# ---------------------------------------------------------------- CLI
def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    p = argparse.ArgumentParser(prog="llm-engine")
    p.add_argument("target", nargs="?", help="目标文件(可选, 自动先跑 recon)")
    p.add_argument("--recon-json", help="recon_v2 的 JSON 输出文件")
    p.add_argument("--backend", default="ollama", choices=["ollama", "llama"])
    p.add_argument("--model", default="qwen2.5:7b")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    # 获取 recon 报告
    if args.recon_json and os.path.exists(args.recon_json):
        with open(args.recon_json) as f:
            recon = json.load(f)
    elif args.target:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from recon_v2 import ReconV2
        from analysis_v2 import AnalysisV2
        recon = ReconV2(args.target).report()
        # M27: 并入 analysis_v2 的校验定位(行为型校验信号)
        try:
            ana = AnalysisV2(args.target).report()
            recon["static"] = ana["static"]
            recon["analysis"] = ana
        except Exception:
            pass
    else:
        print("需要 --recon-json 或 --target")
        return 1

    llm = LLMClient(backend=args.backend, model=args.model)
    ana = LLMAnalyzer(llm)
    rep = ana.analyze(recon, target=args.target or "")
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        print(f"=== LLM 分析引擎 ===")
        print(f"引擎: {rep['engine']} (LLM 可用: {rep['llm_available']})")
        print(f"保护机制: {rep['protections'] or '未识别'}")
        for i, s in enumerate(rep["strategies"]):
            print(f"\n[{i+1}] {s['protection']} (可行性 {s['可行性']})")
            print(f"  思路: {s['思路']}")
            for line in s.get("伪代码", [])[:4]:
                print(f"    {line}")
            print(f"  工具链: {', '.join(s.get('工具链', []))}")
        print("\n=== 脚本骨架(前 10 行) ===")
        print("\n".join(rep["script_skeleton"].splitlines()[:10]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
