#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lib/recon_v3.py —— 探测模块 v3(纯 Python 二进制分析库增强)

M28 增强(相对 recon_v2):
  1. capstone 反汇编(替代 objdump)
  2. pyelftools 解析 ELF 段/节/动态符号
  3. pefile 解析 PE 头/导入表/资源
  4. 统一格式检测(魔数 + 结构)

依赖: capstone, pyelftools, pefile(纯 Python, pip 安装)
"""
from __future__ import annotations

import os
import struct
from typing import Any, Dict, List, Optional

try:
    from capstone import Cs, CS_ARCH_X86, CS_MODE_64, CS_MODE_32, CS_ARCH_ARM
    CAPSTONE_OK = True
except ImportError:
    CAPSTONE_OK = False

try:
    from elftools.elf.elffile import ELFFile
    PYELFTOOLS_OK = True
except ImportError:
    PYELFTOOLS_OK = False

try:
    import pefile
    PEFILE_OK = True
except ImportError:
    PEFILE_OK = False


class ReconV3:
    """探测 v3: 真实二进制深度解析。"""

    def __init__(self, path: str) -> None:
        self.path = path
        self.data = b""
        self.report_data: Dict[str, Any] = {}

    def load(self) -> bool:
        if not os.path.exists(self.path):
            self.report_data["error"] = f"文件不存在: {self.path}"
            return False
        try:
            with open(self.path, "rb") as f:
                self.data = f.read()
        except OSError as e:
            self.report_data["error"] = str(e)
            return False
        return True

    # -- 格式检测 ------------------------------------------------------------
    def detect_format(self) -> Dict[str, Any]:
        d = self.data
        if d[:4] == b"\x7fELF":
            return {"type": "ELF", "bits": 64 if d[4] == 2 else 32,
                    "endian": "LE" if d[5] == 1 else "BE"}
        if d[:2] == b"MZ" and b"PE\x00\x00" in d[:0x400]:
            return {"type": "PE", "bits": 64 if b"PE\x00\x00\x64" in d[:0x400] else 32}
        if d[:4] in (b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf",
                     b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xce"):
            return {"type": "Mach-O"}
        return {"type": "Unknown"}

    # -- ELF 深度解析(pyelftools) -------------------------------------------
    def elf_parse(self) -> Dict[str, Any]:
        if not PYELFTOOLS_OK:
            return {"error": "pyelftools 未安装"}
        try:
            with open(self.path, "rb") as f:
                elf = ELFFile(f)
                result = {
                    "class": "ELF64" if elf.elfclass == 64 else "ELF32",
                    "machine": elf.header["e_machine"],
                    "type": elf.header["e_type"],
                    "entry": hex(elf.header["e_entry"]),
                    "sections": [],
                    "segments": [],
                    "imports": [],
                }
                # 节表
                for sec in elf.iter_sections():
                    result["sections"].append({
                        "name": sec.name, "size": sec.data_size,
                        "type": str(sec["sh_type"]),
                    })
                # 段表
                for seg in elf.iter_segments():
                    result["segments"].append({
                        "type": str(seg["p_type"]),
                        "offset": seg["p_offset"],
                        "vaddr": hex(seg["p_vaddr"]),
                        "filesz": seg["p_filesz"],
                    })
                # 动态符号(导入)
                try:
                    dynsym = elf.get_section_by_name(".dynsym")
                    if dynsym:
                        for sym in dynsym.iter_symbols():
                            if sym.entry.st_shndx == "SHN_UNDEF":
                                result["imports"].append(sym.name)
                except Exception:
                    pass
                return result
        except Exception as e:
            return {"error": str(e)}

    # -- PE 深度解析(pefile) ------------------------------------------------
    def pe_parse(self) -> Dict[str, Any]:
        if not PEFILE_OK:
            return {"error": "pefile 未安装"}
        try:
            pe = pefile.PE(self.path, fast_load=False)
            result = {
                "machine": hex(pe.FILE_HEADER.Machine),
                "sections": [],
                "imports": [],
                "entry": hex(pe.OPTIONAL_HEADER.AddressOfEntryPoint),
            }
            for sec in pe.sections:
                result["sections"].append({
                    "name": sec.Name.rstrip(b"\x00").decode(errors="ignore"),
                    "vsize": sec.Misc_VirtualSize,
                    "rsize": sec.SizeOfRawData,
                    "entropy": round(sec.get_entropy(), 2),
                })
            if hasattr(pe, "DIRECTORY_ENTRY_IMPORT"):
                for entry in pe.DIRECTORY_ENTRY_IMPORT:
                    dll = entry.dll.decode(errors="ignore")
                    for imp in entry.imports:
                        if imp.name:
                            result["imports"].append(f"{dll}:{imp.name.decode(errors='ignore')}")
            return result
        except Exception as e:
            return {"error": str(e)}

    # -- capstone 反汇编 ------------------------------------------------------
    def disassemble(self, code: bytes, base: int = 0, count: int = 20,
                    bits: int = 64) -> List[Dict[str, Any]]:
        if not CAPSTONE_OK:
            return [{"error": "capstone 未安装"}]
        mode = CS_MODE_64 if bits == 64 else CS_MODE_32
        md = Cs(CS_ARCH_X86, mode)
        insns = []
        for i in md.disasm(code[:count * 16], base):
            insns.append({
                "addr": hex(i.address),
                "bytes": i.bytes.hex(" "),
                "mnemonic": i.mnemonic,
                "op_str": i.op_str,
            })
            if len(insns) >= count:
                break
        return insns

    # -- 入口点反汇编 ----------------------------------------------------------
    def entry_disasm(self, count: int = 20) -> Dict[str, Any]:
        fmt = self.detect_format()
        if fmt["type"] == "ELF":
            try:
                with open(self.path, "rb") as f:
                    elf = ELFFile(f)
                    entry = elf.header["e_entry"]
                    # 找含入口的段, 从段内偏移取代码
                    for seg in elf.iter_segments():
                        if seg["p_type"] == "PT_LOAD":
                            vaddr = seg["p_vaddr"]
                            off = seg["p_offset"]
                            if vaddr <= entry < vaddr + seg["p_filesz"]:
                                f.seek(off + (entry - vaddr))
                                code = f.read(count * 16)
                                insns = self.disassemble(code, entry, count,
                                                         elf.elfclass)
                                return {"entry": hex(entry), "insns": insns}
            except Exception as e:
                return {"error": str(e)}
        return {"error": "仅支持 ELF 入口反汇编"}

    # -- 完整报告 ------------------------------------------------------------
    def report(self) -> Dict[str, Any]:
        if not self.load():
            return self.report_data
        fmt = self.detect_format()
        rep = {"path": self.path, "format": fmt, "size": len(self.data)}
        if fmt["type"] == "ELF":
            rep["elf"] = self.elf_parse()
            rep["entry_disasm"] = self.entry_disasm()
        elif fmt["type"] == "PE":
            rep["pe"] = self.pe_parse()
        return rep


# ---------------------------------------------------------------- CLI
def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    import json

    p = argparse.ArgumentParser(prog="recon-v3")
    p.add_argument("target", help="目标文件")
    p.add_argument("--json", action="store_true")
    p.add_argument("--disasm", type=int, default=20, help="反汇编条数")
    args = p.parse_args(argv)

    r = ReconV3(args.target)
    rep = r.report()
    if "error" in rep and len(rep) == 1:
        print(f"错误: {rep['error']}")
        return 1

    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2, default=str))
        return 0

    fmt = rep["format"]
    print(f"=== 探测 v3: {args.target} ===")
    print(f"格式: {fmt['type']} | 大小: {rep['size']} B")
    if "elf" in rep:
        e = rep["elf"]
        if "error" in e:
            print(f"ELF 解析错误: {e['error']}")
        else:
            print(f"ELF: {e['class']} | machine={e['machine']} | "
                  f"entry={e['entry']}")
            print(f"  节表({len(e['sections'])}): "
                  f"{[s['name'] for s in e['sections'][:10]]}")
            print(f"  段表({len(e['segments'])}): "
                  f"{[s['type'] for s in e['segments'][:5]]}")
            print(f"  导入({len(e['imports'])}): "
                  f"{e['imports'][:8]}")
        d = rep.get("entry_disasm", {})
        if d and "insns" in d:
            print(f"\n入口反汇编(前 {len(d['insns'])} 条):")
            for i in d["insns"]:
                print(f"  {i['addr']}: {i['bytes']:<24} {i['mnemonic']} {i['op_str']}")
    elif "pe" in rep:
        p_ = rep["pe"]
        if "error" in p_:
            print(f"PE 解析错误: {p_['error']}")
        else:
            print(f"PE: machine={p_['machine']} entry={p_['entry']}")
            print(f"  节表: {[s['name'] for s in p_['sections']]}")
            print(f"  导入({len(p_['imports'])}): {p_['imports'][:8]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
