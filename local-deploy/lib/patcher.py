#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lib/patcher.py —— 修改器

输入: 原文件 + 偏移 + 原字节 + 新字节
输出: 副本 / 修改 / 校验 / 输出

只依赖 Python 3.8+ 标准库。
"""
from __future__ import annotations

import os
import shutil
from typing import Any, Dict, List, Optional


class Patcher:
    """通用补丁器: 只改副本, 不碰原件。"""

    def __init__(self, target: str, work_dir: str) -> None:
        self.target = target
        self.work_dir = work_dir
        self.copy_path = ""
        self.orig_data = b""

    def make_copy(self) -> Dict[str, Any]:
        """复制原件到工作目录(副本)。"""
        r = {"ok": False, "detail": ""}
        if not os.path.exists(self.target):
            r["detail"] = f"文件不存在: {self.target}"
            return r
        os.makedirs(self.work_dir, exist_ok=True)
        name = os.path.basename(self.target)
        self.copy_path = os.path.join(self.work_dir, f"{name}.patched")
        shutil.copy2(self.target, self.copy_path)
        with open(self.target, "rb") as f:
            self.orig_data = f.read()
        r["ok"] = True
        r["path"] = self.copy_path
        r["detail"] = f"副本: {self.copy_path}"
        return r

    def apply(self, offset: int, old: bytes, new: bytes) -> Dict[str, Any]:
        """在副本 offset 处, 校验 old 后替换为 new。"""
        r = {"ok": False, "detail": ""}
        if not self.copy_path:
            r["detail"] = "未创建副本"
            return r
        with open(self.copy_path, "r+b") as f:
            f.seek(offset)
            cur = f.read(len(old))
            if cur != old:
                r["detail"] = (f"校验失败 @ {offset:#x}: 期望 {old.hex()}, "
                               f"实际 {cur.hex()}")
                return r
            f.seek(offset)
            f.write(new)
        r["ok"] = True
        r["offset"] = offset
        r["old"] = old.hex()
        r["new"] = new.hex()
        r["detail"] = f"修改 @ {offset:#x}: {old.hex()} -> {new.hex()}"
        return r

    def verify(self, offset: int, expected: bytes) -> Dict[str, Any]:
        """验证副本指定位置字节。"""
        r = {"ok": False, "detail": ""}
        if not self.copy_path:
            r["detail"] = "未创建副本"
            return r
        with open(self.copy_path, "rb") as f:
            f.seek(offset)
            b = f.read(len(expected))
        if b == expected:
            r["ok"] = True
            r["detail"] = f"校验通过 @ {offset:#x}: {expected.hex()}"
        else:
            r["detail"] = f"校验失败 @ {offset:#x}: {b.hex()} != {expected.hex()}"
        return r

    def original_intact(self) -> bool:
        """原件未动检查。"""
        if not os.path.exists(self.target):
            return False
        with open(self.target, "rb") as f:
            return f.read() == self.orig_data


# ---------------------------------------------------------------- CLI
def main(argv: Optional[List[str]] = None) -> int:
    import argparse, json
    p = argparse.ArgumentParser(prog="patcher")
    p.add_argument("target", help="目标文件")
    p.add_argument("offset", type=lambda x: int(x, 0), help="偏移(hex)")
    p.add_argument("old", help="原字节(hex, 如 7405)")
    p.add_argument("new", help="新字节(hex, 如 9090)")
    p.add_argument("--work-dir", default=None, help="工作目录")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    import tempfile
    work = args.work_dir or os.path.join(tempfile.gettempdir(), "patcher")
    pt = Patcher(args.target, work)
    r = pt.make_copy()
    if not r["ok"]:
        print(r["detail"])
        return 1
    try:
        old = bytes.fromhex(args.old)
        new = bytes.fromhex(args.new)
    except ValueError as e:
        print(f"hex 解析失败: {e}")
        return 1
    r2 = pt.apply(args.offset, old, new)
    v = pt.verify(args.offset, new)
    intact = pt.original_intact()

    if args.json:
        print(json.dumps({"copy": r, "apply": r2, "verify": v,
                          "original_intact": intact},
                         ensure_ascii=False, indent=2))
    else:
        print(r["detail"])
        print(r2["detail"])
        print(v["detail"])
        print(f"原件未动: {intact}")
    return 0 if (r2["ok"] and v["ok"] and intact) else 1


if __name__ == "__main__":
    raise SystemExit(main())
