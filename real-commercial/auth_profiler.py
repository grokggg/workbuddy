#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
auth_profiler.py —— 授权机制分析框架(通用, 防御视角)

对任意二进制输出授权机制画像(不生成绕过载荷):
  1. 授权相关字符串统计(license/registration/trial/crypto/校验)
  2. 授权类型推断(签名验证型 / 密钥文件型 / 时间型 / 字符串剥离型)
  3. 强度评估(数学强度 / 部署弱点)
  4. 被攻击面分析(防御方视角: 攻击者可能怎么打)

用法: auth_profiler.py <binary>
"""
from __future__ import annotations

import re
import sys
from collections import Counter

# 授权相关模式(存在性统计, 不定位偏移)
PATTERNS = {
    "license_key": rb"license\s*[_-]?\s*key|licence\s*key|serial\s*number|activation\s*code",
    "registration": rb"regist(er|ration|ered)|unregistered|licensed\s*(to|for)",
    "trial": rb"trial|evaluation|expired|grace\s*period|days?\s*left",
    "invalid": rb"invalid\s*(key|license|serial)|not\s*valid|wrong\s*key|key\s*rejected",
    "crypto_sig": rb"rsa|sha(1|256|512)?with|ed25519|ecdsa|signature\s*verify|public\s*key|private\s*key",
    "crypto_sym": rb"aes|des|blowfish|chacha|rc4|cipher",
    "key_file": rb"\.key\b|keyfile|reg(istry)?\.key|license\.dat|lic\.dat",
    "hw_bind": rb"mac\s*address|hardware\s*id|machine\s*id|hostid|cpu\s*id|disk\s*serial",
    "online": rb"https?://|api\.[a-z]+\.(com|net|io)|activate|validate\s*online|server\s*response",
    "time": rb"expire|expiry|not\s*before|nbf|timestamp|unix\s*time|date\s*check",
    "checksum": rb"checksum|crc32|md5|self\s*check|integrity\s*check|hash\s*verify",
    "obfuscation": rb"vmprotect|themida|upx|asprotect|enigma|obsidium|morphine",
}


def profile(path: str) -> dict:
    with open(path, "rb") as f:
        data = f.read()

    counts = {}
    for label, pat in PATTERNS.items():
        counts[label] = len(re.findall(pat, data, re.IGNORECASE))

    # 极小文件(纯机器码教学 crackme)特殊处理
    if len(data) < 4096:
        return {
            "path": path,
            "size": len(data),
            "string_counts": counts,
            "auth_type": ["教学/微型二进制(非商业分类)"],
            "strength": "不适用",
            "attack_surface": ["极小机器码: 无授权字符串, 校验为直接比较(教学示例)"],
            "verdict": "防御分析(教学/微型)",
        }

    # 授权类型推断
    auth_type = []
    if counts["crypto_sig"] >= 3 and counts["license_key"] >= 1:
        auth_type.append("签名验证型(强)")
    if counts["key_file"] >= 1:
        auth_type.append("密钥文件型(中)")
    if counts["hw_bind"] >= 1:
        auth_type.append("硬件绑定型(强)")
    if counts["online"] >= 2:
        auth_type.append("在线验证型(部署强)")
    if counts["time"] >= 1:
        auth_type.append("时间型(试用)")
    if counts["obfuscation"] >= 1:
        auth_type.append("加壳/混淆(反分析)")
    if counts["license_key"] == 0 and counts["registration"] == 0 and counts["crypto_sig"] == 0:
        auth_type.append("字符串剥离型(需动态分析)")

    # 强度评估
    strength = "低"
    if "签名验证型(强)" in auth_type or "硬件绑定型(强)" in auth_type:
        strength = "高"
    elif "在线验证型(部署强)" in auth_type or "加壳/混淆(反分析)" in auth_type:
        strength = "中高"
    elif counts["license_key"] > 0 or counts["crypto_sig"] > 0:
        strength = "中"

    # 被攻击面(防御视角)
    attack_surface = []
    if "签名验证型(强)" in auth_type:
        attack_surface.append("签名验证: 数学不可伪造; 弱点=密钥泄露/验证调用被patch")
    if "密钥文件型(中)" in auth_type:
        attack_surface.append("密钥文件: 可被复制/伪造(若无私钥签名)")
    if "时间型(试用)" in auth_type:
        attack_surface.append("时间窗: 可被时钟回拨绕过(需控制运行环境)")
    if "硬件绑定型(强)" in auth_type:
        attack_surface.append("硬件绑定: 需模拟硬件指纹")
    if "在线验证型(部署强)" in auth_type:
        attack_surface.append("在线验证: 需伪造服务器响应(涉及他人服务, 不在范围)")
    if "字符串剥离型(需动态分析)" in auth_type:
        attack_surface.append("字符串剥离: 静态难定位, 需动态跟踪(商业破解范畴)")

    return {
        "path": path,
        "size": len(data),
        "string_counts": counts,
        "auth_type": auth_type,
        "strength": strength,
        "attack_surface": attack_surface,
        "verdict": "防御分析" if not auth_type else "防御分析(授权机制画像)",
    }


def main():
    if len(sys.argv) < 2:
        print("用法: auth_profiler.py <binary> [binary2 ...]")
        sys.exit(1)
    for p in sys.argv[1:]:
        r = profile(p)
        print(f"=== {r['path']} ({r['size']}B) ===")
        print(f"  授权类型: {', '.join(r['auth_type']) if r['auth_type'] else '未知'}")
        print(f"  强度: {r['strength']}")
        print(f"  字符串统计: {dict(r['string_counts'])}")
        print(f"  被攻击面(防御视角):")
        for s in r["attack_surface"]:
            print(f"    - {s}")
        print()


if __name__ == "__main__":
    main()
