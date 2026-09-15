#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analysis_all.py —— M31 统一分析入口

输入: 任意二进制文件
流程:
  a. 格式识别(ELF/PE/Mach-O/ASAR)
  b. recon_v3 静态分析
  c. 保护类型识别(无壳/UPX/VMProtect/反调试/完整性/多校验)
  d. analysis_v2 校验点定位
  e. llm_engine 策略生成
  f. 自动选择处理方式:
     - 无保护 → 直接 patch 校验点
     - UPX → 脱壳 + patch
     - 反调试 → patch 反调试检测 + patch 校验点
     - 多校验 → 全部校验点 patch
     - 完整性 → 完整性校验 patch + 校验点 patch
  g. 实际 patch
  h. 验证破解

输出: 完整报告(JSON) + 补丁脚本 + 破解后二进制
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
UP_TOOLS = os.path.dirname(HERE)
sys.path.insert(0, UP_TOOLS)
sys.path.insert(0, os.path.join(UP_TOOLS, "lib"))

# UPX 路径(自动探测)
UPX = shutil.which("upx") or "/tmp/m24/targets/upx-4.0.1-amd64_linux/upx"


def run(cmd, timeout=60, inp=None):
    r = subprocess.run(cmd, input=inp, capture_output=True, timeout=timeout)
    return r.stdout.decode(errors="ignore"), r.returncode


class UnifiedAnalyzer:
    """统一分析器。"""

    def __init__(self, target: str, work_dir: str = "") -> None:
        self.target = target
        self.work = work_dir or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "out")
        os.makedirs(self.work, exist_ok=True)
        self.report: Dict[str, Any] = {"target": target}

    # -- a. 格式识别 ---------------------------------------------------------
    def detect_format(self) -> str:
        d = open(self.target, "rb").read(16)
        if d[:4] == b"\x7fELF":
            return "ELF"
        if d[:2] == b"MZ":
            return "PE"
        if d[:4] in (b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf"):
            return "Mach-O"
        if d[:2] == b"#!":
            return "Script"
        return "Unknown"

    # -- b. recon_v3 静态分析 ------------------------------------------------
    def recon(self) -> Dict[str, Any]:
        from lib.recon_v3 import ReconV3
        r = ReconV3(self.target)
        rep = r.report()
        self.report["recon"] = {
            "format": rep.get("format", {}),
            "size": rep.get("size", 0),
            "elf_sections": len(rep.get("elf", {}).get("sections", [])),
            "elf_imports": len(rep.get("elf", {}).get("imports", [])),
            "entry": rep.get("elf", {}).get("entry", ""),
        }
        return rep

    # -- c. 保护类型识别 -------------------------------------------------------
    def detect_protection(self, recon: Dict[str, Any]) -> List[str]:
        protections = []
        fmt = recon.get("format", {}).get("type", "")
        elf = recon.get("elf", {})
        # 加壳: UPX 特征字符串(可靠)
        d = open(self.target, "rb").read()
        if b"UPX!" in d or b"UPX0" in d:
            protections.append("加壳(UPX)")
        # 节表骤减仅在 ELF 有节表结构时辅助(自建无节表不算)
        if fmt == "ELF" and elf and "error" not in elf:
            n_sec = len(elf.get("sections", []))
            imports = elf.get("imports", [])
            if n_sec < 5 and len(imports) == 0 and n_sec > 0:
                protections.append("加壳(UPX)")
        # VMProtect
        if b"VMProtect" in d:
            protections.append("加壳(VMProtect)")
        # 反调试
        if b"IsDebuggerPresent" in d or b"ptrace" in d:
            protections.append("反调试")
        # 完整性
        if any(s in d for s in (b"checksum", b"self_check", b"integrity")):
            protections.append("完整性校验")
        # 反VM
        if b"VMware" in d or b"VirtualBox" in d:
            protections.append("反VM")
        self.report["protections"] = protections or ["无壳/无保护"]
        return protections

    # -- d. analysis_v2 校验点定位 ---------------------------------------------
    def analyze(self) -> Dict[str, Any]:
        from lib.analysis_v2 import AnalysisV2
        rep = AnalysisV2(self.target).report()
        self.report["static_checks"] = {
            "count": rep["static"]["count"],
            "apis": [a["api"] for a in rep["apis"]["apis"]],
            "behavior": [b["behavior"] for b in rep["behavior"]["behaviors"]],
        }
        return rep

    # -- e. llm_engine 策略生成 --------------------------------------------------
    def strategize(self, recon_rep: Dict[str, Any]) -> Dict[str, Any]:
        from lib.llm_engine import LLMAnalyzer, LLMClient
        ana = LLMAnalyzer(LLMClient())
        # 构造 recon 兼容输入
        fake_recon = {
            "packer": {"packed": "加壳(UPX)" in self.report.get(
                "protections", []), "verdict": "加壳",
                "markers": ["UPX"] if "加壳(UPX)" in self.report.get(
                    "protections", []) else []},
            "antidebug": {"detected": ["IsDebuggerPresent"]
                          if "反调试" in self.report.get("protections", [])
                          else []},
            "integrity": {"detected": ["checksum"]
                          if "完整性校验" in self.report.get(
                              "protections", []) else []},
        }
        rep = ana.analyze(fake_recon, target=self.target)
        self.report["strategy"] = {
            "engine": rep["engine"],
            "protections": rep["protections"],
            "strategies": rep["strategies"],
        }
        return rep

    # -- f. 自动选择处理方式 ------------------------------------------------------
    def plan(self) -> List[str]:
        protections = self.report.get("protections", [])
        steps = []
        if "加壳(UPX)" in protections:
            steps.append("unpack")  # 先脱壳
        if "反调试" in protections:
            steps.append("patch_antidebug")
        steps.append("patch_checks")  # 校验点
        self.report["plan"] = steps
        return steps

    # -- g/h. 实际 patch + 验证 ---------------------------------------------------
    def execute(self) -> Dict[str, Any]:
        steps = self.plan()
        cur = self.target
        work_files = []

        # 1. 脱壳
        if "unpack" in steps:
            unpacked = os.path.join(self.work, os.path.basename(cur) + "-unpacked")
            if os.path.exists(UPX):
                r = subprocess.run([UPX, "-d", "-o", unpacked, cur],
                                   capture_output=True, timeout=180)
                if r.returncode == 0 and os.path.exists(unpacked):
                    cur = unpacked
                    work_files.append(unpacked)
                    self.report["unpack"] = "成功"
                else:
                    self.report["unpack"] = "失败: " + r.stderr.decode(errors="ignore")[-100:]
            else:
                self.report["unpack"] = "UPX 不可用"

        # 2. capstone 反汇编 + patch 校验点
        from capstone import Cs, CS_ARCH_X86, CS_MODE_64
        from elftools.elf.elffile import ELFFile
        import io
        d = bytearray(open(cur, "rb").read())
        try:
            elf = ELFFile(io.BytesIO(bytes(d)))
            entry = elf.header["e_entry"]
            seg = None
            for s in elf.iter_segments():
                if s["p_type"] == "PT_LOAD" and s["p_flags"] & 1:
                    if s["p_vaddr"] <= entry < s["p_vaddr"] + s["p_filesz"]:
                        seg = s
                        break
            if seg:
                code = seg.data()
                vaddr = seg["p_vaddr"]
                off = seg["p_offset"]
                md = Cs(CS_ARCH_X86, CS_MODE_64)
                insns = list(md.disasm(code[entry - vaddr:], entry))
                # patch 策略: cmp eax, imm 后的 je/jne
                #   反调试 js(78 xx) -> NOP
                #   其他 je/jne(非 0x58) -> jmp(强制成功)
                #   0x58(排除X) -> NOP
                patched = []
                # 反调试 js: 只在 ptrace(mov eax, 0x65) 后的 js
                for i in range(len(insns) - 1):
                    ins = insns[i]
                    if ins.mnemonic == "mov" and "0x65" in ins.op_str:
                        for j in range(i + 1, min(i + 6, len(insns))):
                            if insns[j].mnemonic == "syscall":
                                for k in range(j + 1, min(j + 5, len(insns))):
                                    if insns[k].mnemonic == "js":
                                        foff = off + (insns[k].address - vaddr)
                                        # js 不跳会落入 exit9 段 -> 改成 jmp 跳过
                                        # 找 exit9 段后的第一条指令
                                        skip_to = None
                                        for m in range(k + 1,
                                                       min(k + 8, len(insns))):
                                            if insns[m].mnemonic == "syscall" \
                                               and insns[m - 1].mnemonic == "mov":
                                                skip_to = insns[m + 1].address \
                                                    if m + 1 < len(insns) else None
                                                break
                                        if skip_to:
                                            disp = skip_to - \
                                                (insns[k].address + 2)
                                            d[foff] = 0xEB
                                            d[foff + 1] = disp & 0xFF
                                            patched.append({
                                                "off": hex(foff),
                                                "what": "反调试js→jmp跳过exit9"})
                                        else:
                                            d[foff] = 0x90
                                            d[foff + 1] = 0x90
                                            patched.append({
                                                "off": hex(foff),
                                                "what": "反调试js→NOP"})
                                break
                    # 校验型: call 后 6 条内的 je/jne(call 返回校验)
                    if ins.mnemonic == "call":
                        for j in range(i + 1, min(i + 6, len(insns))):
                            nxt = insns[j]
                            if nxt.mnemonic in ("je", "jz"):
                                # 相等走成功 -> 强制 jmp 走目标
                                foff = off + (nxt.address - vaddr)
                                d[foff] = 0xEB
                                patched.append({"off": hex(foff),
                                                "what": f"call后{nxt.mnemonic}→jmp"})
                                break
                            if nxt.mnemonic in ("jne", "jnz"):
                                # 不等跳失败 -> NOP(不跳, 继续走成功)
                                foff = off + (nxt.address - vaddr)
                                d[foff] = 0x90
                                d[foff + 1] = 0x90
                                patched.append({"off": hex(foff),
                                                "what": f"call后{nxt.mnemonic}→NOP"})
                                break
                            if nxt.mnemonic.startswith("j"):
                                break
                    # cmp 后的 je/jne 处理 —— 只处理"校验型"cmp
                    # (循环里的 cmp 通常紧跟 jcc, 但不是校验; 用 call 后的 jcc 更准)
                    if ins.mnemonic == "cmp" and ins.op_str.startswith("eax"):
                        try:
                            imm = int(ins.op_str.split(",")[1].strip(), 16)
                        except Exception:
                            imm = None
                        # 只处理紧邻 je/jne 且 imm 明确(完整性/卡密/排除X)
                        if imm is not None:
                            for j in range(i + 1, min(i + 4, len(insns))):
                                nxt = insns[j]
                                if nxt.mnemonic in ("je", "jne"):
                                    foff = off + (nxt.address - vaddr)
                                    if imm == 0x58:
                                        d[foff] = 0x90
                                        d[foff + 1] = 0x90
                                        patched.append({"off": hex(foff),
                                                        "what": "排除X→NOP"})
                                    else:
                                        d[foff] = 0xEB
                                        patched.append({"off": hex(foff),
                                                        "what": "je→jmp"})
                                    break
                                if nxt.mnemonic.startswith("j"):
                                    break
                self.report["patches"] = patched
        except Exception as e:
            self.report["patch_error"] = str(e)

        # 输出破解版
        cracked = os.path.join(self.work, os.path.basename(self.target) + "-cracked")
        with open(cracked, "wb") as f:
            f.write(d)
        os.chmod(cracked, 0o755)
        self.report["cracked_path"] = cracked

        # 验证(尝试 argv + stdin 两种方式)
        self.report["verify"] = {}
        for inp in ["x", "abc", "test", "k", "p", "A", "o"]:
            try:
                out, rc = run([cracked, inp], timeout=10)
                self.report["verify"][f"argv:{inp}"] = {
                    "out": out.strip()[-40:], "rc": rc}
            except Exception:
                pass
            out, rc = run([cracked], inp=(inp + "\n").encode(), timeout=10)
            self.report["verify"][f"stdin:{inp}"] = {
                "out": out.strip()[-40:], "rc": rc}
        return self.report

    # -- 完整流程 ---------------------------------------------------------------
    def run(self) -> Dict[str, Any]:
        fmt = self.detect_format()
        self.report["format"] = fmt
        recon = self.recon()
        self.detect_protection(recon)
        self.analyze()
        self.strategize(recon)
        if fmt in ("ELF", "PE"):
            self.execute()
        else:
            self.report["note"] = f"格式 {fmt} 暂不支持自动 patch"
        return self.report


def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    p = argparse.ArgumentParser(prog="analysis-all")
    p.add_argument("target", help="目标文件")
    p.add_argument("--out", default="", help="输出目录")
    p.add_argument("--json", action="store_true", help="输出 JSON 报告")
    args = p.parse_args(argv)

    a = UnifiedAnalyzer(args.target, args.out)
    rep = a.run()
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2, default=str))
    else:
        print(f"=== 统一分析: {args.target} ===")
        print(f"格式: {rep.get('format')} | 大小: {rep.get('recon', {}).get('size', 0)}")
        print(f"保护: {rep.get('protections')}")
        print(f"校验点: {rep.get('static_checks', {}).get('count', 0)} 处")
        print(f"策略: {rep.get('strategy', {}).get('engine', '')} | "
              f"{[s.get('protection') for s in rep.get('strategy', {}).get('strategies', [])]}")
        print(f"计划: {rep.get('plan')}")
        if "patches" in rep:
            print(f"patches: {rep.get('patches')}")
        if "cracked_path" in rep:
            print(f"破解版: {rep['cracked_path']}")
        for k, v in rep.get("verify", {}).items():
            print(f"验证 '{k}': [{v.get('out', '')}] rc={v.get('rc')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
