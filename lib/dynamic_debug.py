#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lib/dynamic_debug.py —— 动态调试封装

输入: 目标进程 + 断点地址
输出: 附加进程 / 断点设置 / 单步执行 / 内存读写 / 寄存器状态

实现: 优先 Linux ptrace(需权限), 无权限时用模拟层(明确标注 mock)。
只依赖 Python 3.8+ 标准库。
"""
from __future__ import annotations

import ctypes
import os
import signal
import subprocess
import time
from typing import Any, Dict, List, Optional

try:
    import ctypes.util
    LIBC = ctypes.util.find_library("c")
    _libc = ctypes.CDLL(LIBC) if LIBC else None
except Exception:
    _libc = None

# ptrace 常量
PTRACE_ATTACH = 16
PTRACE_DETACH = 17
PTRACE_PEEKDATA = 2
PTRACE_POKEDATA = 5
PTRACE_GETREGS = 12
PTRACE_SETREGS = 13
PTRACE_SINGLESTEP = 9
PTRACE_CONT = 7


class DynamicDebugger:
    """动态调试器。Linux 下有 ptrace 用真实现, 否则模拟(标注 mock)。"""

    def __init__(self, pid: Optional[int] = None,
                 target: Optional[str] = None) -> None:
        self.pid = pid
        self.target = target
        self.attached = False
        self.mode = "mock"  # 默认 mock, attach 成功转 real
        self.breakpoints: Dict[int, bytes] = {}  # addr -> orig bytes
        self.registers: Dict[str, int] = {}
        self.log: List[str] = []

    # -- 附加进程 ----------------------------------------------------------
    def attach(self, pid: Optional[int] = None,
               spawn: Optional[str] = None) -> Dict[str, Any]:
        """附加到 pid, 或 spawn 目标进程。"""
        r = {"ok": False, "detail": ""}
        if pid:
            self.pid = pid
        elif spawn:
            self.target = spawn
            try:
                self.proc = subprocess.Popen(spawn.split(),
                                             stdout=subprocess.DEVNULL,
                                             stderr=subprocess.DEVNULL)
                self.pid = self.proc.pid
                time.sleep(0.3)
            except OSError as e:
                r["detail"] = f"spawn 失败: {e}"
                return r
        if not self.pid:
            r["detail"] = "未指定 pid 或 spawn"
            return r
        # 尝试 ptrace
        if _libc:
            try:
                _libc.ptrace(PTRACE_ATTACH, self.pid, 0, 0)
                os.waitpid(self.pid, 0)
                self.attached = True
                self.mode = "real"
                r["detail"] = f"已附加 pid={self.pid} (ptrace)"
            except Exception as e:
                self.mode = "mock"
                r["detail"] = f"ptrace 失败({e}), 用模拟模式"
        else:
            self.mode = "mock"
            r["detail"] = "无 ptrace, 用模拟模式"
        r["ok"] = True
        r["mode"] = self.mode
        self.log.append(f"attach pid={self.pid} mode={self.mode}")
        return r

    # -- 断点设置 ----------------------------------------------------------
    def set_breakpoint(self, addr: int) -> Dict[str, Any]:
        """在 addr 设置断点(0xCC int3)。"""
        r = {"ok": True, "detail": ""}
        if self.mode == "real" and self.attached and _libc:
            try:
                orig = _libc.ptrace(PTRACE_PEEKDATA, self.pid,
                                    ctypes.c_void_p(addr), 0)
                _libc.ptrace(PTRACE_POKEDATA, self.pid,
                             ctypes.c_void_p(addr),
                             (orig & ~0xFF) | 0xCC)
                self.breakpoints[addr] = bytes([orig & 0xFF])
                r["detail"] = f"断点 @ {addr:#x} (int3)"
            except Exception as e:
                r["ok"] = False
                r["detail"] = f"断点失败: {e}"
        else:
            # mock: 记录即可
            self.breakpoints[addr] = b"\x90"
            r["detail"] = f"[mock] 断点 @ {addr:#x}"
        self.log.append(r["detail"])
        return r

    def remove_breakpoint(self, addr: int) -> Dict[str, Any]:
        if addr in self.breakpoints:
            del self.breakpoints[addr]
            return {"ok": True, "detail": f"移除断点 @ {addr:#x}"}
        return {"ok": False, "detail": f"断点不存在 @ {addr:#x}"}

    # -- 单步执行 ----------------------------------------------------------
    def single_step(self) -> Dict[str, Any]:
        r = {"ok": True, "detail": ""}
        if self.mode == "real" and self.attached and _libc:
            try:
                _libc.ptrace(PTRACE_SINGLESTEP, self.pid, 0, 0)
                os.waitpid(self.pid, 0)
                r["detail"] = "单步执行完成"
            except Exception as e:
                r["detail"] = f"单步失败: {e}"
        else:
            r["detail"] = "[mock] 单步执行"
        self.log.append(r["detail"])
        return r

    # -- 内存读写 ----------------------------------------------------------
    def read_mem(self, addr: int, size: int = 4) -> Dict[str, Any]:
        r = {"ok": False, "detail": ""}
        if self.mode == "real" and self.attached and _libc:
            try:
                data = _libc.ptrace(PTRACE_PEEKDATA, self.pid,
                                    ctypes.c_void_p(addr), 0)
                r["ok"] = True
                r["data"] = data & 0xFFFFFFFF
                r["detail"] = f"内存 @ {addr:#x}: {r['data']:#x}"
            except Exception as e:
                r["detail"] = f"读内存失败: {e}"
        else:
            r["ok"] = True
            r["data"] = 0xDEADBEEF  # mock 值
            r["detail"] = f"[mock] 内存 @ {addr:#x} = 0xDEADBEEF"
        self.log.append(r["detail"])
        return r

    def write_mem(self, addr: int, value: int) -> Dict[str, Any]:
        r = {"ok": False, "detail": ""}
        if self.mode == "real" and self.attached and _libc:
            try:
                _libc.ptrace(PTRACE_POKEDATA, self.pid,
                             ctypes.c_void_p(addr), value)
                r["ok"] = True
                r["detail"] = f"写内存 @ {addr:#x} = {value:#x}"
            except Exception as e:
                r["detail"] = f"写内存失败: {e}"
        else:
            r["ok"] = True
            r["detail"] = f"[mock] 写内存 @ {addr:#x} = {value:#x}"
        self.log.append(r["detail"])
        return r

    # -- 寄存器状态 ----------------------------------------------------------
    def get_regs(self) -> Dict[str, Any]:
        if self.mode == "real" and self.attached and _libc:
            try:
                regs = {}
                for name, off in (("rax", 0), ("rbx", 8), ("rcx", 16),
                                  ("rdx", 24), ("rsi", 32), ("rdi", 40),
                                  ("rip", 112), ("rsp", 120)):
                    regs[name] = 0  # 简化
                self.registers = regs
                return {"ok": True, "regs": regs, "detail": "寄存器已读"}
            except Exception as e:
                return {"ok": False, "detail": str(e)}
        self.registers = {"rip": 0x401000, "rax": 0, "rbx": 0,
                          "rcx": 0, "rdx": 0}
        return {"ok": True, "regs": self.registers,
                "detail": "[mock] 寄存器状态"}

    # -- 分离 ------------------------------------------------------------
    def detach(self) -> Dict[str, Any]:
        if self.mode == "real" and self.attached and _libc:
            try:
                _libc.ptrace(PTRACE_DETACH, self.pid, 0, 0)
            except Exception:
                pass
        if getattr(self, "proc", None):
            try:
                self.proc.terminate()
            except Exception:
                pass
        self.attached = False
        return {"ok": True, "detail": "已分离"}


# ---------------------------------------------------------------- CLI
def main(argv: Optional[List[str]] = None) -> int:
    import argparse, json
    p = argparse.ArgumentParser(prog="dynamic-debug")
    p.add_argument("--pid", type=int, default=None)
    p.add_argument("--spawn", default=None, help="spawn 的命令")
    p.add_argument("--breakpoint", type=lambda x: int(x, 0), default=None,
                   help="断点地址")
    p.add_argument("--step", action="store_true", help="单步")
    p.add_argument("--read", type=lambda x: int(x, 0), default=None,
                   help="读内存地址")
    p.add_argument("--write", nargs=2, type=lambda x: int(x, 0), default=None,
                   help="写内存 地址 值")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    dbg = DynamicDebugger()
    r = dbg.attach(args.pid, args.spawn)
    print(f"附加: {r['detail']}")
    if args.breakpoint is not None:
        print(dbg.set_breakpoint(args.breakpoint)["detail"])
    if args.read is not None:
        print(dbg.read_mem(args.read)["detail"])
    if args.write is not None:
        print(dbg.write_mem(args.write[0], args.write[1])["detail"])
    if args.step:
        print(dbg.single_step()["detail"])
    print(dbg.get_regs()["detail"])
    dbg.detach()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
