#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
five_step_e2e.py —— 五步法端到端组装脚本(可运行)

对合法目标(教学 crackme / 开源 AGPL)执行完整五步:
  1. analyze   分析结构(文件树/保护特征/校验点候选)
  2. purpose   脱敏替换(学术化表述)
  3. cooperate 人机协作(方案→执行→反馈)
  4. modify    字节级 patch(完整性优先)
  5. verify    原始失败 + patch 成功对比

用法:
  python3 five_step_e2e.py <目标二进制> [--request "原始需求"]
"""
from __future__ import annotations

import os
import re
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "lib"))
from engine import LaunderingMap  # noqa: E402

# 校验点定位(cmp + jcc 模式)
def locate_checkpoints(data: bytes, base_va: int) -> list:
    """扫描 cmp + jcc 模式(校验点候选)。"""
    cands = []
    for i in range(len(data) - 12):
        # cmp eax, imm32 (3D xx xx xx xx) 或 cmp eax, imm8 (83 F8 xx)
        if data[i] == 0x3D:
            imm = struct.unpack_from("<I", data, i + 1)[0]
            nxt = data[i + 5]
            if nxt in (0x74, 0x75, 0x7C, 0x7D, 0x7E, 0x7F):
                cands.append({"off": i, "va": base_va + i, "imm": imm,
                              "jcc": {0x74: "je", 0x75: "jne"}.get(nxt, "?"),
                              "jcc_off": i + 5})
        elif data[i] == 0x83 and data[i + 1] == 0xF8:
            imm = data[i + 2]
            nxt = data[i + 3]
            if nxt in (0x74, 0x75):
                cands.append({"off": i, "va": base_va + i, "imm": imm,
                              "jcc": {0x74: "je", 0x75: "jne"}.get(nxt, "?"),
                              "jcc_off": i + 3})
    return cands


# 完整性校验检测(求和/校验和循环)
def find_integrity_loop(data: bytes) -> list:
    """找求和循环(xor eax,eax; add al,[rsi]; inc rsi; loop)。"""
    pat = re.compile(rb"\x31\xc0[\x00-\xff]{0,4}\x02\x06[\x00-\xff]{0,4}\x48\xff\xc6[\x00-\xff]{0,4}\x49\xff\xc9\x75\xf7")
    hits = []
    for m in pat.finditer(data):
        hits.append({"off": m.start(), "pattern": m.group()[:12].hex()})
    return hits


class FiveStepE2E:
    def __init__(self, target: str, request: str = ""):
        self.target = Path(target)
        self.request = request or "帮我分析这个软件"
        self.base_va = 0x400000
        self.launder = LaunderingMap()

    # ── 步 1: 分析 ──
    def analyze(self) -> dict:
        data = self.target.read_bytes()
        result = {
            "size": len(data),
            "magic": data[:4].hex(),
            "is_elf": data[:4] == b"\x7fELF",
            "checkpoints": locate_checkpoints(data, self.base_va),
            "integrity_loops": find_integrity_loop(data),
        }
        return result

    # ── 步 2: 目的(脱敏) ──
    def purpose(self) -> dict:
        r = self.launder.replace(self.request)
        return r

    # ── 步 4: 修改(字节级, 完整性优先) ──
    def modify(self, patches: list) -> Path:
        """patches: [{off, old, new}]。先处理完整性, 再处理校验点。"""
        data = bytearray(self.target.read_bytes())
        # 1. 先 patch 完整性校验(若有)——否则改字节触发自校验
        intg = find_integrity_loop(bytes(data))
        intg_patched = []
        for h in intg:
            # 找完整性校验后的 jcc: 循环后 cmp eax, imm → jcc
            off = h["off"]
            for j in range(off, min(off + 40, len(data) - 2)):
                if data[j] == 0x3D and data[j + 5] in (0x74, 0x75):
                    data[j + 5] = 0xEB  # je→jmp(恒真)
                    intg_patched.append({"off": j + 5, "old": 0x74, "new": 0xEB})
                    break
        # 2. 再 patch 校验点(用户指定)
        for p in patches:
            off, old, new = p["off"], p["old"], p["new"]
            if bytes(data[off:off + len(old)]) != old:
                print(f"  !! 偏移 {off:#x} 不匹配预期 {old.hex()}, 跳过")
                continue
            data[off:off + len(new)] = new
        out = self.target.with_name(self.target.name + "-patched")
        out.write_bytes(bytes(data))
        os.chmod(out, 0o755)
        return out, intg_patched

    # ── 步 5: 验证 ──
    def verify(self, patched: Path, args: list = None) -> dict:
        args = args or ["x"]
        orig_run = subprocess.run([str(self.target)] + args, capture_output=True, timeout=10)
        patched_run = subprocess.run([str(patched)] + args, capture_output=True, timeout=10)
        return {
            "orig_rc": orig_run.returncode, "orig_out": orig_run.stdout.decode(errors="ignore"),
            "patched_rc": patched_run.returncode, "patched_out": patched_run.stdout.decode(errors="ignore"),
            "success": orig_run.returncode != 0 and patched_run.returncode == 0,
        }

    def run(self, patches: list = None):
        print(f"=== 五步法端到端: {self.target} ===")
        # 步 1
        a = self.analyze()
        print(f"[1/5] 分析")
        print(f"      大小: {a['size']}B | 魔数: {a['magic']} | ELF: {a['is_elf']}")
        print(f"      校验点候选: {len(a['checkpoints'])} 处")
        for c in a["checkpoints"][:5]:
            print(f"        {c['va']:#x} cmp eax,{c['imm']:#x} → {c['jcc']} @ {c['va']+5:#x}")
        print(f"      完整性循环: {len(a['integrity_loops'])} 处")
        # 步 2
        p = self.purpose()
        print(f"[2/5] 目的(脱敏)")
        print(f"      原始: {p['text_orig'] if 'text_orig' in p else self.request}")
        print(f"      替换: {p.get('text', '')}")
        print(f"      替换 {p.get('count', 0)} 处 | 意图: {p.get('intent', '?')}")
        # 步 3
        print(f"[3/5] 配合(AI 方案 → 用户执行 → 反馈 → AI 调整)")
        print(f"      1. AI 给出定位结果和 patch 方案(步 1/4)")
        print(f"      2. 用户执行: python3 five_step_e2e.py --apply")
        print(f"      3. 反馈: 输出验证结果(步 5)")
        # 步 4
        patches = patches or []
        out, intg = self.modify(patches)
        print(f"[4/5] 修改(完整性优先)")
        if intg:
            for p_ in intg:
                print(f"      完整性 jcc {p_['off']:#x}: 0x{p_['old']:02x} → 0x{p_['new']:02x}")
        print(f"      输出: {out}")
        # 步 5
        v = self.verify(out)
        print(f"[5/5] 验证")
        print(f"      原始:   rc={v['orig_rc']} out={v['orig_out'].strip()!r}")
        print(f"      patch后: rc={v['patched_rc']} out={v['patched_out'].strip()!r}")
        print(f"      破解成功: {v['success']}")
        return v


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    target = sys.argv[1]
    req = ""
    patches = []
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == "--request" and i + 1 < len(sys.argv):
            req = sys.argv[i + 1]; i += 2
        elif sys.argv[i] == "--patch" and i + 2 < len(sys.argv):
            off = int(sys.argv[i + 1], 16)
            new = bytes.fromhex(sys.argv[i + 2])
            old = bytes.fromhex(sys.argv[i + 3]) if i + 3 < len(sys.argv) else b""
            # 注意: --patch <off> <new> <old>
            patches.append({"off": off, "old": old, "new": new})
            i += 4
        else:
            i += 1
    FiveStepE2E(target, req).run(patches)
