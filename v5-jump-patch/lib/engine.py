#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v5-jump-patch —— AI 辅助改跳转引擎

复现 BV1py8668Eqv(逐日逆向, 934s, AI 辅助破解改跳转)。

流程(转录):
  1. 分析文件    —— 读取文件大小/格式, PE 结构/字符串分析 (381s-473s)
  2. 定位跳转    —— 搜索条件跳转指令(JNZ/JZ/JE/JNE) (583s)
  3. 修改        —— 把条件跳转改为 NOP(只改副本, 不碰原件) (594s, 806s)
  4. 验证        —— 运行副本, 确认修改生效 (831s)

边界: 只改副本(copy_patch), 不碰原件; 具体目标参数由用户填; 测试在本地 mock。
只依赖 Python 3.8+ 标准库。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import struct
import subprocess
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------- 指令定义

# x86 条件跳转指令(常见): 短跳转(0x70-0x7F) + 近跳转(0x0F 0x80-0x8F)
# NOP = 0x90
CONDITIONAL_JUMPS = {
    # 短跳转: 操作码 -> 助记符
    0x74: "JE/JZ (short)",
    0x75: "JNE/JNZ (short)",
    0x70: "JO (short)",
    0x71: "JNO (short)",
    0x72: "JB/JC/JNAE (short)",
    0x73: "JAE/JNB/JNC (short)",
    0x76: "JBE/JNA (short)",
    0x77: "JA/JNBE (short)",
    0x78: "JS (short)",
    0x79: "JNS (short)",
    0x7C: "JL/JNGE (short)",
    0x7D: "JGE/JNL (short)",
    0x7E: "JLE/JNG (short)",
    0x7F: "JG/JNLE (short)",
}

# 近跳转(0F 8x): 需要 2 字节操作码
CONDITIONAL_JUMPS_NEAR = {
    0x84: "JE/JZ (near)",
    0x85: "JNE/JNZ (near)",
    0x80: "JO (near)",
    0x81: "JNO (near)",
    0x82: "JB/JC (near)",
    0x83: "JAE/JNB (near)",
    0x86: "JBE/JNA (near)",
    0x87: "JA/JNBE (near)",
    0x88: "JS (near)",
    0x89: "JNS (near)",
    0x8C: "JL/JNGE (near)",
    0x8D: "JGE/JNL (near)",
    0x8E: "JLE/JNG (near)",
    0x8F: "JG/JNLE (near)",
}

NOP = 0x90


# ---------------------------------------------------------------- 分析执行器

class Analyzer:
    """分析执行器: 真实读文件 + PE 结构/字符串分析。"""

    def __init__(self, target: str) -> None:
        self.target = target

    def analyze(self) -> Dict[str, Any]:
        """分析目标文件。返回 {size, is_pe, strings, jump_hits}。"""
        r = {"ok": False, "detail": "", "size": 0, "is_pe": False,
             "strings": [], "jump_hits": []}
        if not os.path.exists(self.target):
            r["detail"] = f"文件不存在: {self.target}"
            return r
        if os.path.isdir(self.target):
            r["detail"] = f"是目录: {self.target}"
            return r

        size = os.path.getsize(self.target)
        r["size"] = size

        # 读二进制
        with open(self.target, "rb") as f:
            data = f.read()

        # PE 检测: MZ 头 + PE 签名
        if data[:2] == b"MZ":
            r["is_pe"] = True
            pe_off = struct.unpack("<I", data[0x3C:0x40])[0]
            if data[pe_off:pe_off + 4] == b"PE\x00\x00":
                machine = struct.unpack("<H", data[pe_off + 4:pe_off + 6])[0]
                r["machine"] = "x64" if machine == 0x8664 else (
                    "x86" if machine == 0x14C else hex(machine))
            r["detail"] = (f"{self.target}: {size} 字节, PE 文件 "
                           f"({r.get('machine','?')})")
        else:
            r["detail"] = f"{self.target}: {size} 字节, 非 PE(可能是脚本/数据)"

        # 字符串提取(ASCII 可打印连续 >=4)
        strings = re.findall(rb"[\x20-\x7e]{4,}", data)
        r["strings"] = [s.decode("ascii", errors="ignore") for s in strings[:50]]

        # 条件跳转扫描
        r["jump_hits"] = self.scan_jumps(data)
        r["ok"] = True
        return r

    def scan_jumps(self, data: bytes) -> List[Dict[str, Any]]:
        """扫描条件跳转指令。返回 [{offset, mnemonic, opcode}]。"""
        hits = []
        i = 0
        while i < len(data) - 1:
            b = data[i]
            # 短跳转
            if b in CONDITIONAL_JUMPS:
                hits.append({
                    "offset": i,
                    "mnemonic": CONDITIONAL_JUMPS[b],
                    "opcode": f"{b:02X}",
                    "size": 2,
                    "type": "short",
                })
                i += 2
            # 近跳转(0F 8x)
            elif b == 0x0F and i + 1 < len(data) and data[i + 1] in CONDITIONAL_JUMPS_NEAR:
                hits.append({
                    "offset": i,
                    "mnemonic": CONDITIONAL_JUMPS_NEAR[data[i + 1]],
                    "opcode": f"0F {data[i+1]:02X}",
                    "size": 6,
                    "type": "near",
                })
                i += 6
            else:
                i += 1
        return hits


# ---------------------------------------------------------------- 修改执行器

class Patcher:
    """修改执行器: 只改副本(copy_patch), 不碰原件。"""

    def __init__(self, target: str, work_dir: str) -> None:
        self.target = target
        self.work_dir = work_dir
        self.copy_path = ""

    def make_copy(self) -> str:
        """复制目标到工作目录(副本)。"""
        os.makedirs(self.work_dir, exist_ok=True)
        name = os.path.basename(self.target)
        self.copy_path = os.path.join(self.work_dir, f"{name}.patched")
        shutil.copy2(self.target, self.copy_path)
        return self.copy_path

    def nop_jump(self, offset: int, size: int) -> Dict[str, Any]:
        """把 offset 处 size 字节改为 NOP(只改副本)。"""
        r = {"ok": False, "detail": ""}
        if not self.copy_path or not os.path.exists(self.copy_path):
            r["detail"] = "未创建副本。先 make_copy()"
            return r
        with open(self.copy_path, "r+b") as f:
            f.seek(offset)
            orig = f.read(size)
            f.seek(offset)
            f.write(bytes([NOP] * size))
        r["ok"] = True
        r["orig"] = orig.hex()
        r["patched"] = (bytes([NOP] * size)).hex()
        r["detail"] = (f"偏移 {offset:#x}: {orig.hex()} -> "
                       f"{bytes([NOP]*size).hex()} (NOP)")
        return r

    def verify_bytes(self, offset: int, size: int, expected: bytes) -> bool:
        """验证副本指定位置字节。"""
        with open(self.copy_path, "rb") as f:
            f.seek(offset)
            return f.read(size) == expected


# ---------------------------------------------------------------- 验证执行器

class Verifier:
    """验证执行器: 真实运行副本 + 检查退出/输出。"""

    def __init__(self, work_dir: str) -> None:
        self.work_dir = work_dir
        self.log: List[str] = []

    def run(self, cmd: List[str], timeout: int = 10) -> Dict[str, Any]:
        """运行命令(真实执行), 返回 {ok, stdout, stderr, exit}。"""
        try:
            p = subprocess.run(cmd, capture_output=True, text=True,
                               timeout=timeout)
            res = {"ok": p.returncode == 0, "stdout": (p.stdout or "").strip(),
                   "stderr": (p.stderr or "").strip(), "exit": p.returncode}
        except FileNotFoundError:
            res = {"ok": False, "stdout": "", "stderr": f"命令不存在: {cmd[0]}",
                   "exit": 127}
        except subprocess.TimeoutExpired:
            res = {"ok": False, "stdout": "", "stderr": "超时", "exit": 124}
        self.log.append(f"$ {' '.join(cmd)} -> exit={res['exit']}")
        return res

    def verify_patch(self, copy_path: str, offset: int, size: int) -> Dict[str, Any]:
        """验证补丁已生效(副本字节 = NOP)。"""
        r = {"ok": False, "detail": ""}
        with open(copy_path, "rb") as f:
            f.seek(offset)
            b = f.read(size)
        if b == bytes([NOP] * size):
            r["ok"] = True
            r["detail"] = f"副本偏移 {offset:#x}: 已 NOP({size} 字节) ✓"
        else:
            r["detail"] = f"副本偏移 {offset:#x}: {b.hex()} (未 NOP)"
        return r


# ---------------------------------------------------------------- 总执行器

class JumpPatchEngine:
    """AI 辅助改跳转总引擎: 分析 -> 定位 -> 修改 -> 验证。"""

    def __init__(self, target: str, work_dir: str) -> None:
        self.target = target
        self.work_dir = work_dir
        self.analyzer = Analyzer(target)
        self.patcher = Patcher(target, work_dir)
        self.verifier = Verifier(work_dir)
        self.log: List[Dict[str, Any]] = []
        self.analysis: Dict[str, Any] = {}
        self.chosen_jump: Optional[Dict[str, Any]] = None

    def _log(self, step: int, key: str, ok: bool, detail: str) -> None:
        self.log.append({"step": step, "key": key, "ok": ok, "detail": detail})

    def run_analyze(self) -> Dict[str, Any]:
        """步1: 分析文件(真实读)。"""
        self.analysis = self.analyzer.analyze()
        r = {"step": 1, "key": "analyze", "ok": self.analysis["ok"],
             "detail": self.analysis["detail"]}
        if self.analysis["ok"]:
            r["detail"] += f"\n  字符串样本: {self.analysis['strings'][:5]}"
            jumps = self.analysis["jump_hits"]
            r["detail"] += f"\n  条件跳转: {len(jumps)} 处"
            if jumps:
                r["detail"] += f"  首个: offset={jumps[0]['offset']:#x} " \
                               f"{jumps[0]['mnemonic']}"
        self._log(1, "analyze", r["ok"], r["detail"])
        return r

    def run_locate(self, jump_index: int = 0) -> Dict[str, Any]:
        """步2: 定位跳转(真实搜索)。"""
        r = {"step": 2, "key": "locate", "ok": False, "detail": ""}
        jumps = self.analysis.get("jump_hits", [])
        if not jumps:
            r["detail"] = "未找到条件跳转"
            self._log(2, "locate", False, r["detail"])
            return r
        if jump_index >= len(jumps):
            r["detail"] = f"跳转索引越界({jump_index} >= {len(jumps)})"
            self._log(2, "locate", False, r["detail"])
            return r
        self.chosen_jump = jumps[jump_index]
        r["ok"] = True
        r["detail"] = (f"定位: offset={self.chosen_jump['offset']:#x} "
                       f"{self.chosen_jump['mnemonic']} "
                       f"(opcode {self.chosen_jump['opcode']}, "
                       f"{self.chosen_jump['size']} 字节)")
        self._log(2, "locate", True, r["detail"])
        return r

    def run_modify(self) -> Dict[str, Any]:
        """步3: 修改(复制副本 + NOP, 只改副本)。"""
        r = {"step": 3, "key": "modify", "ok": False, "detail": ""}
        if not self.chosen_jump:
            r["detail"] = "未定位跳转。先 run_locate()"
            self._log(3, "modify", False, r["detail"])
            return r
        copy = self.patcher.make_copy()
        r["detail"] = f"副本: {copy}"
        res = self.patcher.nop_jump(self.chosen_jump["offset"],
                                    self.chosen_jump["size"])
        r["detail"] += f"\n  {res['detail']}"
        r["ok"] = res["ok"]
        self._log(3, "modify", r["ok"], r["detail"])
        return r

    def run_verify(self, verify_cmd: Optional[List[str]] = None) -> Dict[str, Any]:
        """步4: 验证(真实运行副本 + 字节检查)。"""
        r = {"step": 4, "key": "verify", "ok": False, "detail": ""}
        if not self.chosen_jump or not self.patcher.copy_path:
            r["detail"] = "未修改。先 run_modify()"
            self._log(4, "verify", False, r["detail"])
            return r
        # 字节验证
        bres = self.verifier.verify_patch(self.patcher.copy_path,
                                          self.chosen_jump["offset"],
                                          self.chosen_jump["size"])
        r["detail"] = bres["detail"]
        # 真实运行(如有命令)
        if verify_cmd:
            rres = self.verifier.run(verify_cmd)
            r["detail"] += f"\n  运行: {' '.join(verify_cmd)} -> exit={rres['exit']}"
            r["run"] = rres
            r["ok"] = bres["ok"] and rres["ok"]
        else:
            r["ok"] = bres["ok"]
            r["detail"] += "\n  (未提供运行命令, 仅字节验证)"
        self._log(4, "verify", r["ok"], r["detail"])
        return r

    def run_all(self, jump_index: int = 0,
                verify_cmd: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """执行完整流程。"""
        steps = [
            self.run_analyze(),
            self.run_locate(jump_index),
            self.run_modify(),
            self.run_verify(verify_cmd),
        ]
        return steps

    def log_text(self) -> str:
        """真实运行日志。"""
        if not self.log:
            return "无日志"
        lines = []
        for entry in self.log:
            status = "OK " if entry["ok"] else "FAIL"
            lines.append(f"[{entry['step']}/4] {entry['key']:<8} → {status}")
            for line in entry["detail"].splitlines():
                lines.append(f"      {line}")
        ok = sum(1 for e in self.log if e["ok"])
        lines.append("-" * 50)
        lines.append(f"通过 {ok}/4")
        return "\n".join(lines)


# ---------------------------------------------------------------- CLI

def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    p = argparse.ArgumentParser(
        prog="v5-jump-patch",
        description="AI 辅助改跳转(BV1py8668Eqv 复现): 分析->定位->修改->验证")
    p.add_argument("target", help="目标文件")
    p.add_argument("--work-dir", default=None, help="工作目录(副本落点)")
    p.add_argument("--jump-index", type=int, default=0, help="定位第几个跳转")
    p.add_argument("--verify-cmd", default=None, help="验证命令(空格分隔)")
    p.add_argument("--json", action="store_true", help="输出 JSON")
    args = p.parse_args(argv)

    import tempfile
    work_dir = args.work_dir or os.path.join(tempfile.gettempdir(), "v5-jump-patch")
    eng = JumpPatchEngine(args.target, work_dir)
    verify_cmd = args.verify_cmd.split() if args.verify_cmd else None
    steps = eng.run_all(args.jump_index, verify_cmd)

    if args.json:
        print(json.dumps(steps, ensure_ascii=False, indent=2))
    else:
        print(eng.log_text())
    return 0 if all(s["ok"] for s in steps) else 1


if __name__ == "__main__":
    raise SystemExit(main())
