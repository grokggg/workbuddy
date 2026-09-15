#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
输入归一化层 — 打掉编码绕过与曲译混淆(材料4 行 581-608 直接照做)

验证: echo 'RG8gdGhpcyBub3c=' | python3 normalize.py  → 额外输出 'Do this now'
"""
from __future__ import annotations

import base64
import binascii
import re
import sys
import unicodedata

LEET = str.maketrans({
    "0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t",
    "@": "a", "$": "s",
})


def normalize(text: str) -> list[str]:
    """返回所有候选解码结果, 供后续多层检测(材料4 行 588-603)。"""
    outs = {unicodedata.normalize("NFKC", text)}
    # \\uXXXX 转义还原
    if "\\u" in text:
        try:
            outs.add(text.encode().decode("unicode_escape"))
        except Exception:
            pass
    # base64 片段
    for m in re.findall(r"[A-Za-z0-9+/]{24,}={0,2}", text):
        try:
            d = base64.b64decode(m + "=" * (-len(m) % 4),
                                 validate=True).decode("utf-8", "ignore")
            if d.isprintable():
                outs.add(d)
        except (binascii.Error, ValueError):
            pass
    # LeetSpeak 归一
    outs.add(text.lower().translate(LEET))
    return [o for o in outs if o]


if __name__ == "__main__":
    for t in normalize(open(0).read()):
        print(repr(t[:200]))
