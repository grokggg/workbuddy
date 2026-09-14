#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
js_crackme.py —— M33 JavaScript 混淆 crackme 处理

流程:
  1. 生成混淆 JS crackme(变量名混淆 + 字符串拆分)
  2. 反混淆(手写 AST/正则处理)
  3. 定位校验逻辑
  4. 修改(AST 变换: 校验恒真)
  5. 验证(node 运行)

不依赖外部库(纯 Python 正则级反混淆)。
"""
import os
import re
import subprocess
import sys


def make_js_crackme(path: str) -> None:
    """生成混淆 JS crackme。"""
    js = r"""
// 混淆 crackme: 变量名混淆 + 字符串拆分
var _0x1 = function(s) { return s.split('').reverse().join(''); };
var _0x2 = "4202-ssap-terces";  // "secret-pass-2024" 反转
var _0x3 = _0x1(_0x2);           // 还原
function _0x4(k) { return k === _0x3; }
var _0x5 = process.argv[2] || '';
console.log(_0x4(_0x5) ? 'OK' : 'NO');
"""
    open(path, "w").write(js)
    print(f"JS crackme 生成: {path} ({os.path.getsize(path)}B)")


def deobfuscate(path: str) -> str:
    """反混淆: 常量折叠 + 字符串还原。"""
    src = open(path).read()
    # 1. 找字符串反转函数调用: _0x1("...")
    def rev(m):
        s = m.group(1)
        return '"' + s[::-1] + '"'
    src = re.sub(r'_0x1\("([^"]*)"\)', rev, src)
    # 2. 折叠 _0x2 = "..." 反转: 实际直接看 _0x3
    # 3. 标记校验行
    src = src.replace("=== _0x3", "=== 'secret-pass-2024'  // 还原")
    return src


def patch_js(path: str, out_path: str) -> None:
    """修改: 校验恒真(把 === 改 === 且返回 true 或改比较)。"""
    src = open(path).read()
    # 把 check 函数改成恒真
    src = re.sub(
        r"function _0x4\(k\) \{ return k === _0x3; \}",
        "function _0x4(k) { return true; }  // PATCH: 恒真",
        src)
    open(out_path, "w").write(src)
    print(f"patched JS: {out_path}")


def verify(js_path: str, arg: str) -> tuple:
    """用 node 运行验证。"""
    r = subprocess.run(["node", js_path, arg], capture_output=True, timeout=10)
    return r.stdout.decode().strip(), r.returncode


def main():
    work = os.path.join(os.path.dirname(os.path.abspath(__file__)), "js-work")
    os.makedirs(work, exist_ok=True)
    js = os.path.join(work, "js_crackme.js")
    make_js_crackme(js)

    print("\n=== 原始行为 ===")
    out, rc = verify(js, "secret-pass-2024")
    print(f"  正确密码: {out}")
    out2, rc2 = verify(js, "wrong")
    print(f"  错误密码: {out2}")

    print("\n=== 反混淆 ===")
    de = deobfuscate(js)
    print(f"  还原后核心: {[l for l in de.splitlines() if 'secret' in l]}")

    print("\n=== 修改(AST 变换) ===")
    patched = os.path.join(work, "js_crackme_patched.js")
    patch_js(js, patched)

    print("\n=== 验证(破解) ===")
    out3, rc3 = verify(patched, "wrong")
    print(f"  错误密码: {out3} | 期望 OK")


if __name__ == "__main__":
    main()
