#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pyc_crackme.py —— M33 Python 字节码 crackme 处理

流程:
  1. 生成/接收 .pyc(Python 字节码 crackme)
  2. 反编译(dis 模块, 纯标准库)
  3. 定位校验逻辑(COMPARE_OP/BINARY_SUBSCR)
  4. 修改字节码(改常量或比较)
  5. 验证

Python 字节码 crackme 示例:
  def check(key):
      return key == "secret-pass-2024"
"""
import dis
import marshal
import os
import struct
import sys
import types


def make_pyc_checkme(path: str) -> None:
    """生成 Python 字节码 crackme(.pyc)。"""
    code_str = (
        "def check(key):\n"
        "    return key == 'secret-pass-2024'\n"
        "def main():\n"
        "    import sys\n"
        "    k = sys.argv[1] if len(sys.argv) > 1 else ''\n"
        "    print('OK' if check(k) else 'NO')\n"
        "if __name__ == '__main__':\n"
        "    main()\n"
    )
    code = compile(code_str, "pyc_crackme.py", "exec")
    # 写 .pyc(py3.13: 16 字节 header: magic4 + flags4 + hash8)
    with open(path, "wb") as f:
        f.write(b"\x00" * 16)  # 占位 header(16 字节)
        f.write(marshal.dumps(code))
    print(f"pyc crackme 生成: {path} ({os.path.getsize(path)}B)")
    return code


def inspect_pyc(path: str) -> dict:
    """反编译查看校验逻辑。"""
    d = open(path, "rb").read()
    # 跳过 header(16 字节 py3.7+)
    code = marshal.loads(d[16:])
    result = {"consts": [], "bytecode": []}
    # 递归收集常量
    def walk(c):
        if isinstance(c, types.CodeType):
            for name in c.co_names:
                if name not in result["consts"]:
                    result["consts"].append(name)
            for const in c.co_consts:
                if isinstance(const, (str, int, bytes)):
                    if const not in result["consts"]:
                        result["consts"].append(const)
                walk(const)
    walk(code)
    # 反汇编 main 函数
    for const in code.co_consts:
        if isinstance(const, types.CodeType) and const.co_name == "main":
            result["bytecode"] = [
                {"opname": i.opname, "arg": i.argval}
                for i in dis.get_instructions(const)
            ]
    return result


def patch_pyc(path: str, out_path: str, new_const: str = "x") -> None:
    """修改字节码: 把校验常量替换(改密码)。"""
    d = open(path, "rb").read()
    code = marshal.loads(d[16:])
    # 修改 main 的 check 调用? 简化: 直接改 check 的常量
    def patch_code(c):
        new_consts = []
        for const in c.co_consts:
            if isinstance(const, str) and const == "secret-pass-2024":
                new_consts.append(new_const)
            else:
                new_consts.append(const)
            if isinstance(const, types.CodeType):
                new_consts[-1] = patch_code(const)
        return c.replace(co_consts=tuple(new_consts))
    new_code = patch_code(code)
    with open(out_path, "wb") as f:
        f.write(d[:16])
        f.write(marshal.dumps(new_code))
    print(f"patched pyc: {out_path} (常量 {new_const!r})")


def main():
    work = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pyc-work")
    os.makedirs(work, exist_ok=True)
    pyc = os.path.join(work, "pyc_checkme.pyc")
    make_pyc_checkme(pyc)
    print("\n=== 反编译 ===")
    info = inspect_pyc(pyc)
    print(f"常量: {info['consts']}")
    print(f"main 字节码:")
    for b in info["bytecode"][:15]:
        print(f"  {b['opname']} {b['arg']}")
    print("\n=== 修改字节码 ===")
    patched = os.path.join(work, "pyc_checkme_patched.pyc")
    patch_pyc(pyc, patched, new_const="x")
    # 验证: 加载 patched pyc 跑
    import importlib.util
    spec = importlib.util.spec_from_file_location("pyc_checkme", patched)
    mod = importlib.util.module_from_spec(spec)
    import types as _t
    # 直接用 exec 跑
    d = open(patched, "rb").read()
    code = marshal.loads(d[16:])
    ns = {}
    exec(code, ns)
    import subprocess
    # 通过 exec 验证
    r = subprocess.run([sys.executable, "-c",
                        f"import sys; sys.path.insert(0, {work!r}); "
                        f"import importlib.util; "
                        f"spec = importlib.util.spec_from_file_location('m', {patched!r}); "
                        f"mod = importlib.util.module_from_spec(spec); "
                        f"spec.loader.exec_module(mod); "
                        f"print(mod.check('x'))"],
                       capture_output=True, timeout=10)
    print(f"验证(check('x')): {r.stdout.decode().strip()} | 期望 True")


if __name__ == "__main__":
    main()
