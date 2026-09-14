#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
process_real.py —— M29 带保护真实 crackme 批量处理

目标: cm-upx1 / cm-upx6 / cm-upx9(UPX 加壳) + cm-base(原版)
流程: recon_v3 -> analysis_v2 -> llm_engine -> 识别保护 -> patch -> 验证

破解策略:
  - 带壳(cm-upxN): 先 upx -d 脱壳, 再 patch 校验分支
  - 原版(cm-base): 直接 patch jne -> NOP(M28 已验证)
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
UP_TOOLS = os.path.dirname(HERE)
sys.path.insert(0, UP_TOOLS)
sys.path.insert(0, os.path.join(UP_TOOLS, "lib"))

UPX = "/tmp/m24/targets/upx-4.0.1-amd64_linux/upx"

TARGETS = [
    ("cm-upx1", True, "UPX -1 加壳"),
    ("cm-upx6", True, "UPX -6 加壳"),
    ("cm-upx9", True, "UPX -9 加壳(最强压缩)"),
    ("cm-base", False, "原版(单校验点)"),
]


def run(cmd, timeout=60, inp=None):
    r = subprocess.run(cmd, input=inp, capture_output=True, timeout=timeout)
    return r.stdout.decode(errors="ignore"), r.returncode


def unpck(target_path, out_path):
    """UPX 脱壳。"""
    r = subprocess.run([UPX, "-d", "-o", out_path, target_path],
                       capture_output=True, timeout=180)
    ok = r.returncode == 0 and os.path.exists(out_path)
    if not ok:
        print(f"  UPX stderr: {r.stderr.decode(errors='ignore')[-200:]}")
    return ok, r.stdout.decode(errors="ignore")


def find_and_patch_jne(binary_path, out_path):
    """用 capstone 反汇编找 strcmp 调用后的 jne 并 NOP 掉。"""
    d = bytearray(open(binary_path, "rb").read())
    try:
        from capstone import Cs, CS_ARCH_X86, CS_MODE_64
        from elftools.elf.elffile import ELFFile
        import io
    except ImportError:
        return False, "capstone/pyelftools 未装"
    try:
        elf = ELFFile(io.BytesIO(bytes(d)))
        text = elf.get_section_by_name(".text")
        code = text.data()
        base = text["sh_addr"]
        off = text["sh_offset"]
        md = Cs(CS_ARCH_X86, CS_MODE_64)
        # 从 main(入口 lea rdi 目标)开始反汇编, 避免 .text 开头误解析
        entry = elf.header["e_entry"]
        # main = 入口 __libc_start_main 的第一个参数: lea rdi, [rip+disp]
        entry_code = code[entry - base:entry - base + 64]
        main_addr = None
        for insn in md.disasm(entry_code, entry):
            if insn.mnemonic == "lea" and "rdi" in insn.op_str:
                # lea rdi, [rip + 0xc1] -> main = insn.address+7+0xc1
                import re as _re
                m = _re.search(r"0x([0-9a-f]+)", insn.op_str)
                if m:
                    main_addr = insn.address + insn.size + int(m.group(1), 16)
                break
        if not main_addr:
            main_addr = 0x1165  # 兜底(该 crackme 的已知 main)
        insns = list(md.disasm(code[main_addr - base:main_addr - base + 0x100],
                               main_addr))
        # 找 call <strcmp plt> 后的条件跳转(可能隔 test 等指令)
        patched = 0
        for i in range(len(insns) - 1):
            ins = insns[i]
            if ins.mnemonic == "call" and "0x1050" in ins.op_str:
                # 从 call 后找下一个条件跳转(跳过 test/cmp 等)
                for j in range(i + 1, min(i + 6, len(insns))):
                    nxt = insns[j]
                    if nxt.mnemonic in ("jne", "je", "jz", "jnz"):
                        # 计算文件偏移
                        foff = off + (nxt.address - base)
                        d[foff] = 0x90
                        d[foff + 1] = 0x90
                        patched += 1
                        print(f"  patch @ {foff:#x}: {nxt.mnemonic} {nxt.op_str} -> NOP")
                        break
                    if nxt.mnemonic.startswith("j"):  # 其他跳转也停
                        break
        if patched == 0:
            return False, "未找到 strcmp+jne 模式"
        with open(out_path, "wb") as f:
            f.write(d)
        os.chmod(out_path, 0o755)
        return True, f"patch {patched} 处条件跳转 -> NOP"
    except Exception as e:
        return False, f"反汇编失败: {e}"


def main():
    results = []
    for name, packed, desc in TARGETS:
        src = os.path.join(HERE, name)
        print(f"\n{'='*56}\n[{name}] {desc}\n{'='*56}")
        if not os.path.exists(src):
            print(f"  !! 目标不存在, 跳过")
            continue

        # 1. recon_v3
        out, _ = run([sys.executable,
                      os.path.join(UP_TOOLS, "lib", "recon_v3.py"), src])
        print("--- recon_v3 ---")
        print("\n".join(out.strip().splitlines()[:6]))

        # 2. 识别保护
        protection = "加壳(UPX)" if packed else "单校验点"
        print(f"\n保护类型: {protection}")

        # 3. 脱壳(带壳目标)
        work = os.path.join(HERE, name + "-unpacked")
        if packed:
            ok, msg = unpck(src, work)
            print(f"--- 脱壳 --- {msg.strip()}")
            if not ok:
                print(f"  !! 脱壳失败, 跳过")
                results.append({"name": name, "cracked": False,
                                "reason": "脱壳失败"})
                continue
            target_for_patch = work
        else:
            target_for_patch = src

        # 4. patch
        cracked = os.path.join(HERE, name + "-cracked")
        ok, msg = find_and_patch_jne(target_for_patch, cracked)
        print(f"--- patch --- {msg}")
        if not ok:
            results.append({"name": name, "cracked": False,
                            "reason": msg})
            continue

        # 5. 验证(错误输入应成功)
        out_c, rc_c = run([cracked], inp=b"abc\n")
        print(f"--- 验证 --- 输入'abc': [{out_c.strip().splitlines()[-1]}] rc={rc_c}")
        success = "Congratulations" in out_c
        results.append({"name": name, "cracked": success,
                        "rc": rc_c, "output": out_c.strip()[-40:]})

    # 汇总
    print(f"\n{'='*56}\n汇总\n{'='*56}")
    n_ok = sum(1 for r in results if r["cracked"])
    for r in results:
        st = "✅" if r["cracked"] else "❌"
        print(f"  {st} {r['name']}: {r.get('output', r.get('reason', ''))}")
    print(f"\n破解率: {n_ok}/{len(results)}")
    return 0 if n_ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
