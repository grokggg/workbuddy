#!/usr/bin/env python3
"""用 ptrace 单步定位 crackme 崩溃点。"""
import ctypes
import os
import signal
import struct
import sys

# 用 ptrace 系统调用
libc = ctypes.CDLL(None, use_errno=True)
PTRACE_TRACEME = 0
PTRACE_SINGLESTEP = 9
PTRACE_CONT = 7
PTRACE_GETREGS = 12
PTRACE_PEEKTEXT = 1
PTRACE_ATTACH = 16


def ptrace(req, pid, addr, data):
    return libc.ptrace(req, pid, addr, data)


class Regs(ctypes.Structure):
    _fields_ = [
        ("r15", ctypes.c_ulonglong), ("r14", ctypes.c_ulonglong),
        ("r13", ctypes.c_ulonglong), ("r12", ctypes.c_ulonglong),
        ("rbp", ctypes.c_ulonglong), ("rbx", ctypes.c_ulonglong),
        ("r11", ctypes.c_ulonglong), ("r10", ctypes.c_ulonglong),
        ("r9", ctypes.c_ulonglong), ("r8", ctypes.c_ulonglong),
        ("rax", ctypes.c_ulonglong), ("rcx", ctypes.c_ulonglong),
        ("rdx", ctypes.c_ulonglong), ("rsi", ctypes.c_ulonglong),
        ("rdi", ctypes.c_ulonglong), ("orig_rax", ctypes.c_ulonglong),
        ("rip", ctypes.c_ulonglong), ("cs", ctypes.c_ulonglong),
        ("eflags", ctypes.c_ulonglong), ("rsp", ctypes.c_ulonglong),
        ("ss", ctypes.c_ulonglong), ("fs_base", ctypes.c_ulonglong),
        ("gs_base", ctypes.c_ulonglong), ("ds", ctypes.c_ulonglong),
        ("es", ctypes.c_ulonglong), ("fs", ctypes.c_ulonglong),
        ("gs", ctypes.c_ulonglong),
    ]


pid = os.fork()
if pid == 0:
    # 子进程: 请求被跟踪
    libc.ptrace(PTRACE_TRACEME, 0, 0, 0)
    os.execv('./crackme', ['./crackme', 'k'])
else:
    # 父进程: 等待子进程停止, 然后单步
    _, status = os.waitpid(pid, 0)
    if not os.WIFSTOPPED(status):
        print("子进程未停止:", status)
        sys.exit(1)
    print("子进程已停止, 开始单步...")
    step = 0
    last_rip = 0
    while step < 200:
        libc.ptrace(PTRACE_SINGLESTEP, pid, 0, 0)
        _, status = os.waitpid(pid, 0)
        if os.WIFEXITED(status):
            print(f"子进程正常退出 rc={os.WEXITSTATUS(status)}, 步数={step}")
            break
        if os.WIFSIGNALED(status):
            print(f"子进程被信号 {os.WTERMSIG(status)} 杀死, 步数={step}, "
                  f"上一条 RIP={last_rip:#x}")
            break
        # 读寄存器
        regs = Regs()
        libc.ptrace(PTRACE_GETREGS, pid, 0, ctypes.byref(regs))
        step += 1
        if step % 20 == 0 or regs.rip == 0x400078:
            print(f"  step {step}: rip={regs.rip:#x}")
        last_rip = regs.rip
