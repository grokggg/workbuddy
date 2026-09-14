#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
process_dynamic.py —— M30 反调试/多校验点 crackme 处理

目标:
  ad1: ptrace 反调试 + 卡密
  ad2: ptrace 反调试 + 卡密 + 第二校验点
  mc1: 双校验点(卡密 + 排除 X)
  mc2: 完整性 + 卡密

策略:
  1. recon_v3 静态分析(capstone 反汇编)
  2. 识别保护类型(反调试/多校验/完整性)
  3. patch:
     - 反调试: NOP 掉 ptrace 后的 js(78 xx)
     - 多校验点: patch 每个校验的 je/jmp
     - 完整性: patch 完整性 je(74 xx) -> jmp(EB xx) 或 NOP
  4. 验证(正确密码 OK, 错误密码 NO 或破解后任意 OK)
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
UP_TOOLS = os.path.dirname(HERE)
sys.path.insert(0, UP_TOOLS)
sys.path.insert(0, os.path.join(UP_TOOLS, "lib"))

TARGETS = [
    ("ad1", "p", "ptrace 反调试 + 卡密"),
    ("ad2", "o", "ptrace 反调试 + 卡密 + 第二校验"),
    ("mc1", "k", "双校验点(卡密+排除X)"),
    ("mc2", "A", "完整性 + 卡密"),
]


def run(cmd, timeout=30, inp=None):
    r = subprocess.run(cmd, input=inp, capture_output=True, timeout=timeout)
    return r.stdout.decode(errors="ignore"), r.returncode


def disasm_binary(path):
    """capstone 反汇编(从入口点开始, 只反汇编代码区)。"""
    from capstone import Cs, CS_ARCH_X86, CS_MODE_64
    from elftools.elf.elffile import ELFFile
    import io
    d = open(path, "rb").read()
    elf = ELFFile(io.BytesIO(d))
    entry = elf.header["e_entry"]
    for seg in elf.iter_segments():
        if seg["p_type"] == "PT_LOAD" and seg["p_flags"] & 1:  # PF_X
            vaddr = seg["p_vaddr"]
            off = seg["p_offset"]
            if vaddr <= entry < vaddr + seg["p_filesz"]:
                code = seg.data()
                start = entry - vaddr
                md = Cs(CS_ARCH_X86, CS_MODE_64)
                insns = list(md.disasm(code[start:], entry))
                return insns, off, vaddr
    raise ValueError("无可执行段")


def patch_antidebug(insns, off, base, d):
    """patch ptrace 反调试: js 改 jmp(跳过 exit 9 段, 跳到后续代码)。"""
    patched = []
    for i in range(len(insns) - 1):
        ins = insns[i]
        # mov eax, 101(0x65) 后跟 syscall 后 test + js
        if ins.mnemonic == "mov" and ("0x65" in ins.op_str
                                      or "101" in ins.op_str):
            for j in range(i + 1, min(i + 6, len(insns))):
                if insns[j].mnemonic == "syscall":
                    # syscall 后找 test + js
                    for k in range(j + 1, min(j + 5, len(insns))):
                        if insns[k].mnemonic == "js":
                            foff = off + (insns[k].address - base)
                            # js 的目标是 exit9 段, js 不跳会落入 exit9
                            # -> 改成 jmp 跳过 exit9(找 exit9 段后的第一条指令)
                            # exit9 段 = [mov eax,60][mov edi,9][syscall], 12 字节
                            # js 在 exit9 前, 跳过 12 字节 = 跳到完整性校验
                            # 找到 js 后第 4 条指令(syscall 后)作为跳过目标
                            skip_to = None
                            for m in range(k + 1, min(k + 8, len(insns))):
                                if insns[m].mnemonic == "syscall" and \
                                   insns[m - 1].mnemonic == "mov":
                                    # exit9 的 syscall, 目标 = 它后面
                                    skip_to = insns[m + 1].address \
                                        if m + 1 < len(insns) else None
                                    break
                            if skip_to:
                                disp = skip_to - (insns[k].address + 2)
                                d[foff] = 0xEB
                                d[foff + 1] = disp & 0xFF
                                patched.append((foff, skip_to))
                            else:
                                d[foff] = 0x90
                                d[foff + 1] = 0x90
                                patched.append(foff)
                            break
        if patched:
            break
    return patched


def patch_all_jcc(insns, off, base, d, skip_addrs=()):
    """patch 策略(精准版):
    - 完整性校验 je(cmp 后紧跟) -> jmp 跳过 BAD
    - 卡密 je1 -> jmp 跳成功
    - 反调试 js -> NOP(patch_antidebug 处理)
    - 其他 jcc/jmp 不动(避免破坏控制流)
    效果: 完整性校验绕过 + 卡密强制通过。
    """
    patched = []
    # 找 cmp eax, imm32 后的 je(完整性 + 卡密 + 第二校验)
    for i in range(len(insns) - 1):
        ins = insns[i]
        if ins.mnemonic == "cmp" and ins.op_str.startswith("eax"):
            # 提取 cmp 立即数
            imm = None
            try:
                imm = int(ins.op_str.split(",")[1].strip(), 16)
            except Exception:
                imm = None
            for j in range(i + 1, min(i + 4, len(insns))):
                nxt = insns[j]
                if nxt.mnemonic in ("je", "jne"):
                    foff = off + (nxt.address - base)
                    if foff in skip_addrs:
                        continue
                    if imm == 0x58:
                        # 第二校验(排除 X): NOP 掉(不拒绝)
                        d[foff] = 0x90
                        d[foff + 1] = 0x90
                        patched.append((foff, nxt.mnemonic, "->NOP(排除X)"))
                    else:
                        # 完整性/卡密 je: -> jmp(强制走成功)
                        d[foff] = 0xEB
                        patched.append((foff, nxt.mnemonic, "->jmp"))
                    break
                if nxt.mnemonic.startswith("j"):
                    break
    return patched


def main():
    results = []
    for name, pwd, desc in TARGETS:
        src = os.path.join(HERE, name)
        print(f"\n{'='*56}\n[{name}] {desc}\n{'='*56}")
        if not os.path.exists(src):
            print("  !! 目标不存在")
            continue

        # 1. recon_v3
        out, _ = run([sys.executable,
                      os.path.join(UP_TOOLS, "lib", "recon_v3.py"), src])
        print("--- recon_v3 ---")
        print("\n".join(out.strip().splitlines()[:4]))

        # 2. 原始行为
        _, rc_ok = run([src, pwd])
        _, rc_bad = run([src, "x"])
        print(f"--- 原始 --- 密码'{pwd}' rc={rc_ok} | 'x' rc={rc_bad}")

        # 3. 反汇编 + patch
        try:
            insns, off, base = disasm_binary(src)
        except Exception as e:
            print(f"  !! 反汇编失败: {e}")
            results.append({"name": name, "cracked": False, "reason": str(e)})
            continue

        d = bytearray(open(src, "rb").read())
        # 识别反调试(ptrace = mov eax, 0x65)
        has_ad = any("0x65" in i.op_str for i in insns if i.mnemonic == "mov")
        print(f"--- 保护识别 --- 反调试: {'是' if has_ad else '否'} | "
              f"完整性/多校验: 是")

        # patch 反调试 js
        ad_patched = patch_antidebug(insns, off, base, d) if has_ad else []
        if ad_patched:
            ad_str = [hex(p[0] if isinstance(p, tuple) else p)
                      for p in ad_patched]
            print(f"--- 反调试 patch --- js -> jmp 跳过 exit9 @ {ad_str}")

        # patch 条件跳转(完整性 je + 卡密 je + 第二校验)
        # 策略: 全部 jcc -> NOP(无条件走成功路径)
        skip = set(ad_patched)
        jcc_patched = patch_all_jcc(insns, off, base, d, skip_addrs=skip)
        # 但 NOP 全部 jcc 会把 fail 也放开——重新跑验证看效果
        print(f"--- patch --- {len(jcc_patched)} 处条件跳转 -> NOP")

        cracked = os.path.join(HERE, name + "-cracked")
        with open(cracked, "wb") as f:
            f.write(d)
        os.chmod(cracked, 0o755)

        # 4. 验证(若失败尝试互补 patch)
        out_c, rc_c = run([cracked, "x"])
        if rc_c != 0 or "NO" in out_c:
            # 互补: 把 jmp 改 NOP / NOP 改 jmp(暴力双方案)
            d2 = bytearray(open(src, "rb").read())
            if ad_patched:
                for p in ad_patched:
                    f = p[0] if isinstance(p, tuple) else p
                    d2[f] = 0x90
                    d2[f + 1] = 0x90
            # 用互补: 所有 cmp 后 je 一律 NOP(顺序执行到 ok)
            for i in range(len(insns) - 1):
                ins = insns[i]
                if ins.mnemonic == "cmp" and ins.op_str.startswith("eax"):
                    for j in range(i + 1, min(i + 4, len(insns))):
                        nxt = insns[j]
                        if nxt.mnemonic in ("je", "jne"):
                            foff2 = off + (nxt.address - base)
                            d2[foff2] = 0x90
                            d2[foff2 + 1] = 0x90
                            break
                        if nxt.mnemonic.startswith("j"):
                            break
            # 同时 NOP 掉 jmp_fail 和 jl
            for ins in insns:
                if ins.mnemonic == "jmp":
                    foff2 = off + (ins.address - base)
                    d2[foff2] = 0x90
                    d2[foff2 + 1] = 0x90
            alt = os.path.join(HERE, name + "-cracked")
            with open(alt, "wb") as f:
                f.write(d2)
            os.chmod(alt, 0o755)
            out_c2, rc_c2 = run([alt, "x"])
            if rc_c2 == 0 and "NO" not in out_c2:
                out_c, rc_c = out_c2, rc_c2
                print(f"  (互补方案生效)")

        print(f"--- 破解验证 --- 'x'->[{out_c.strip()}]rc={rc_c} | "
              f"'{pwd}'->[{run([cracked, pwd])[0].strip()}]rc={run([cracked, pwd])[1]}")
        success = rc_c == 0 or (out_c.strip() and "NO" not in out_c)
        results.append({"name": name, "cracked": success, "rc": rc_c,
                        "out": out_c.strip()[-20:]})

    # 汇总
    print(f"\n{'='*56}\n汇总\n{'='*56}")
    n = sum(1 for r in results if r["cracked"])
    for r in results:
        st = "✅" if r["cracked"] else "❌"
        print(f"  {st} {r['name']}: {r.get('out', r.get('reason', ''))}")
    print(f"\n破解率: {n}/{len(results)}")
    return 0 if n == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
