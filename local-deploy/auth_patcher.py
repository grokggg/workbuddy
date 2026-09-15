#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
auth_patcher.py —— 通用 patch 原理框架(方法论 + 骨架)

对 5 种授权类型给出 patch 模式 + 数学等价 + 副作用 + 最小字节数。
**不自动对具体目标生效**: 所有 patch 用 {OFFSET}/{OLD}/{NEW} 占位,
由用户本机对合法目标(自建 crackme)填入执行。

Patch 模式总表:
  1. 比较型   : je → jmp(恒真) 或 jne → nop(恒真) —— 2~6 字节
  2. 签名验证型: call verify → nop×5(跳过验证) —— 5 字节
  3. 时间型   : jcc(时间比较) → jmp/nop —— 2~6 字节
  4. 在线型   : 返回码比较 jcc → jmp/nop —— 2~6 字节
  5. 完整性型 : 校验和比较 jcc → jmp/nop —— 2~6 字节
"""
from __future__ import annotations

import sys

# ── patch 模式定义(数学等价 + 副作用 + 字节数) ──
PATCH_MODES = {
    "cmp_type": {
        "name": "比较型",
        "pattern": "cmp 校验值 → jcc 分支",
        "orig": "if (input == KEY) goto OK; else goto FAIL",
        "patched": "goto OK (恒真, 跳过 FAIL 分支)",
        "math": "原始: [input==KEY] ? OK : FAIL → patch 后: TRUE ? OK",
        "variants": [
            {"jcc": "je", "patch": "EB <rel8>", "bytes": 2, "note": "je→jmp: 相等才跳 → 恒跳"},
            {"jcc": "jne", "patch": "90 90", "bytes": 2, "note": "jne→nop×2: 不相等才跳 → 不跳"},
            {"jcc": "jz/jnz", "patch": "同 je/jne", "bytes": 2, "note": "别名"},
        ],
        "side_effects": "若校验后有完整性校验(校验 cmp 所在字节), 改字节触发自校验失败",
        "min_bytes": 2,
    },
    "sig_type": {
        "name": "签名验证型",
        "pattern": "call RSA_verify/ED25519 → test eax → jcc",
        "orig": "valid = verify(sig, key); if (!valid) goto FAIL",
        "patched": "valid = TRUE (跳过 verify 调用)",
        "math": "原始: verify()∈{0,1} → patch 后: 1(恒真)",
        "variants": [
            {"jcc": "call → nop×5", "patch": "90 90 90 90 90", "bytes": 5, "note": "call 5 字节 → 全 nop, 返回未定义但 rax 常保留"},
            {"jcc": "test→xor eax,eax; inc eax", "patch": "31 C0 FF C0", "bytes": 4, "note": "强制 rax=1(真)"},
        ],
        "side_effects": "后续逻辑可能再校验 token 字段 → 需多处 patch; 完整性校验可能触发",
        "min_bytes": 4,
    },
    "time_type": {
        "name": "时间型",
        "pattern": "call time() → cmp/子 → jcc (now < exp ? OK : FAIL)",
        "orig": "if (now < expiry) goto OK; else goto FAIL",
        "patched": "goto OK (恒真, 无视时间)",
        "math": "原始: [now<exp] ? OK : FAIL → patch 后: TRUE ? OK",
        "variants": [
            {"jcc": "jl/jge → jmp/nop", "patch": "EB <rel8> / 90 90", "bytes": 2, "note": "时间比较分支恒真"},
        ],
        "side_effects": "若 expiry 同时写日志/计数, 后续状态不一致",
        "min_bytes": 2,
    },
    "online_type": {
        "name": "在线型",
        "pattern": "call socket/curl → 返回码 cmp → jcc",
        "orig": "resp = http_verify(key); if (resp != OK) goto FAIL",
        "patched": "goto OK (跳过响应检查)",
        "math": "原始: [resp==OK] ? OK : FAIL → patch 后: TRUE ? OK",
        "variants": [
            {"jcc": "jne → nop×2", "patch": "90 90", "bytes": 2, "note": "失败分支不跳"},
            {"jcc": "call → nop×5", "patch": "90 90 90 90 90", "bytes": 5, "note": "跳过网络调用"},
        ],
        "side_effects": "服务端可能记录激活状态 → 本地显示 OK 但服务端未授权(仅离线场景)",
        "min_bytes": 2,
    },
    "integrity_type": {
        "name": "完整性型",
        "pattern": "call checksum → cmp 期望值 → jcc",
        "orig": "if (checksum(self) == EXPECTED) goto OK; else goto FAIL(self-modified)",
        "patched": "goto OK (无视校验和)",
        "math": "原始: [crc==EXP] ? OK : FAIL → patch 后: TRUE ? OK",
        "variants": [
            {"jcc": "jne → nop×2", "patch": "90 90", "bytes": 2, "note": "校验失败不跳"},
            {"jcc": "je → EB <rel8>", "patch": "EB <rel8>", "bytes": 2, "note": "恒跳 OK"},
        ],
        "side_effects": "**必须先于其他 patch 处理**——否则其他 patch 改字节, 完整性先炸",
        "min_bytes": 2,
    },
}

# ── patch 骨架(占位符) ──
PATCH_SKELETON = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动生成的 patch 脚本骨架(占位符机制)。

用法: 用户对合法目标(自建 crackme)填入:
  {OFFSET}   = 校验点文件偏移(用 auth_locator 定位)
  {OLD}      = 原始字节(hex)
  {NEW}      = patch 字节(hex, 参考 PATCH_MODES)
然后: python3 patch_skeleton.py <目标二进制>
"""
import sys

PATCHES = [
    # {模式}: 比较型
    # {{"offset": {OFFSET}, "old": bytes.fromhex("{OLD}"), "new": bytes.fromhex("{NEW}")}},
]

def apply_patch(path: str) -> None:
    with open(path, "rb") as f:
        data = bytearray(f.read())
    for p in PATCHES:
        off, old, new = p["offset"], p["old"], p["new"]
        if data[off:off+len(old)] != old:
            print(f"!! 偏移 {off:#x} 不匹配预期 {old.hex()} (实际 {bytes(data[off:off+len(old)]).hex()})")
            continue
        data[off:off+len(new)] = new
        print(f"OK 偏移 {off:#x}: {old.hex()} → {new.hex()}")
    out = path + "-patched"
    with open(out, "wb") as f:
        f.write(data)
    print(f"输出: {out}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: patch_skeleton.py <目标>")
        sys.exit(1)
    apply_patch(sys.argv[1])
'''


def print_modes():
    print("=== auth_patcher: 授权类型 patch 模式总表 ===")
    for key, m in PATCH_MODES.items():
        print(f"\n[{m['name']}] ({key}) 最小 {m['min_bytes']}B")
        print(f"  模式: {m['pattern']}")
        print(f"  原始: {m['orig']}")
        print(f"  patch: {m['patched']}")
        print(f"  数学等价: {m['math']}")
        print(f"  副作用: {m['side_effects']}")
        for v in m["variants"]:
            print(f"    {v['jcc']}: {v['patch']} ({v['bytes']}B) — {v['note']}")


def gen_skeleton() -> str:
    return PATCH_SKELETON


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--skeleton":
        print(gen_skeleton())
    else:
        print_modes()
