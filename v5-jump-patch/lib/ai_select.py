#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v5 AI 语义选点 — 从多个跳转里选"关键那一个"(视频 BV1py8668Eqv 补齐)

素材出处:
  [材料4 行 701] AI 定位分支: 「分支位置已确认: 文件偏移 0 的 0x10FD 是校验失败/
    密码错误提示的条件跳转」——从多个跳转中选出"决定授权"的那一个, 这是语义判断。
  [材料4 行 699] 「我随便输入什么都提示密码正确」= 选点意图。

物理边界: 不交付针对具体商业软件的选点载荷; 本模块是通用选点框架。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

# 语义选点提示词模板(把"哪个跳转是关键"的判断交给 LLM/规则)
SELECT_PROMPT = """你是逆向分析助手。以下是目标二进制 {target} 的条件跳转清单:

{jumps}

用户意图: {intent}
(例如: "随便输入什么都提示密码正确" = 选"校验失败→密码错误"分支的跳转)

请判断哪个跳转是【关键校验跳转】(决定授权/校验结果的那个), 输出:
- offset(hex)
- 类型(je/jne/jg/jl...)
- 理由(为什么它是关键, 而不是其他跳转)

只输出一个, 不要列多个。
"""


@dataclass
class JumpInfo:
    offset: int
    mnemonic: str
    size: int
    context: str = ""


@dataclass
class SelectionResult:
    offset: int
    mnemonic: str
    reason: str
    score: float
    manual: bool = False


class JumpSelector:
    """跳转语义选点: 规则优先(可被 LLM 覆盖)。

    规则(教学 crackme 场景, 材料4 行 701 同款判断):
      1. 越靠近"错误提示分支"的跳转越关键(上下文含 fail/error/wrong 相关)
      2. 比较指令 cmp 后紧跟的 je/jne 优先
      3. 缺上下文时, 取最后一个条件跳转(经验: 校验通常在尾部)
    """

    def __init__(self, target: str):
        self.target = target

    def select(self, jumps: List[JumpInfo],
               intent: str = "") -> SelectionResult:
        if not jumps:
            raise ValueError("无跳转可选")
        # 规则 1: 上下文含 fail/wrong/error/invalid 的跳转优先(材料4 行 701 同款)
        fail_kw = ("fail", "wrong", "error", "invalid", "bad", "密码错误",
                   "失败", "无效", "INCORRECT")
        for j in jumps:
            if any(k in j.context.lower() for k in fail_kw):
                return SelectionResult(j.offset, j.mnemonic,
                                       f"上下文含错误标记: {j.context[:40]}",
                                       0.9)
        # 规则 2: 最后的条件跳转(校验通常在尾部)
        last = jumps[-1]
        return SelectionResult(last.offset, last.mnemonic,
                               "无错误上下文, 取最后条件跳转(经验规则)",
                               0.6)

    def render_prompt(self, jumps: List[JumpInfo], intent: str) -> str:
        lines = []
        for j in jumps:
            lines.append(f"  offset=0x{j.offset:x} {j.mnemonic} "
                         f"({j.size} 字节) ctx={j.context[:40]}")
        return SELECT_PROMPT.format(
            target=self.target, jumps="\n".join(lines), intent=intent or "(未给出)")


# ---- 对比数据模块(材料4 行 707: 人工 OD 1 分钟 vs AI 22-85 分钟) ----
HUMAN_VS_AI = {
    "video_claim": {
        "human_od_min": 1,
        "ai_min": 22,
        "ai_unfinished_min": 85,
        "note": "UP 主亲测: 同一无壳程序改判定, 人工 OD 1 分钟, AI 22 分钟→85 分钟仍未完成 [材料4 行 707]",
    },
    "tool_measure": {
        "human_est_min": None,   # 需用户本机实测
        "ai_measured_s": None,   # 工具实际耗时(由调用方记录)
        "note": "工具自动定位+patch 为秒级, 人工对照由用户自行测",
    },
}
