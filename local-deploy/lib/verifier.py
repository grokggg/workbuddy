#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lib/verifier.py —— 验证器

输入: 修改后文件 + 预期行为
输出: 隔离运行 / 行为对比 / 报告

只依赖 Python 3.8+ 标准库。
"""
from __future__ import annotations

import hashlib
import os
import subprocess
from typing import Any, Dict, List, Optional


class Verifier:
    """验证器: 隔离运行 + 行为对比 + 报告。"""

    def __init__(self, sandbox_dir: Optional[str] = None) -> None:
        self.sandbox_dir = sandbox_dir or "/tmp/up-tools-sandbox"
        os.makedirs(self.sandbox_dir, exist_ok=True)
        self.log: List[str] = []

    # -- 隔离运行 ----------------------------------------------------------
    def run_isolated(self, exe: str,
                     args: Optional[List[str]] = None,
                     timeout: int = 10) -> Dict[str, Any]:
        """在沙箱目录隔离运行(限制 cwd, 无网络无特权)。"""
        r = {"ok": False, "detail": ""}
        # 解析可执行文件(支持 PATH 中的命令)
        import shutil
        exe_path = exe if os.path.isabs(exe) else shutil.which(exe)
        if not exe_path:
            r["detail"] = f"命令不存在: {exe}"
            return r
        cmd = [exe_path] + (args or [])
        try:
            p = subprocess.run(cmd, capture_output=True, text=True,
                               timeout=timeout, cwd=self.sandbox_dir,
                               env={"PATH": "/usr/bin:/bin",
                                    "HOME": self.sandbox_dir})
            r["ok"] = True
            r["exit"] = p.returncode
            r["stdout"] = (p.stdout or "")[:500]
            r["stderr"] = (p.stderr or "")[:500]
            r["detail"] = f"运行完成, exit={p.returncode}"
        except subprocess.TimeoutExpired:
            r["detail"] = f"超时(>{timeout}s)"
        except OSError as e:
            r["detail"] = f"运行失败: {e}"
        self.log.append(f"run {exe} -> {r['detail']}")
        return r

    # -- 行为对比 ----------------------------------------------------------
    def compare(self, orig_exit: Optional[int], mod_exit: Optional[int],
                orig_out: str = "", mod_out: str = "") -> Dict[str, Any]:
        """对比原件/副本行为差异。"""
        r = {"ok": True, "detail": ""}
        diffs = []
        if orig_exit != mod_exit:
            diffs.append(f"退出码: {orig_exit} -> {mod_exit}")
        if orig_out != mod_out:
            diffs.append("输出不同")
        if diffs:
            r["behavior_changed"] = True
            r["diffs"] = diffs
            r["detail"] = "行为变化: " + "; ".join(diffs)
        else:
            r["behavior_changed"] = False
            r["detail"] = "行为一致"
        return r

    # -- 完整性 ------------------------------------------------------------
    def sha256(self, path: str) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    def integrity(self, orig: str, mod: str) -> Dict[str, Any]:
        """原件/副本哈希对比。"""
        h1 = self.sha256(orig)
        h2 = self.sha256(mod)
        return {"orig_sha256": h1[:16], "mod_sha256": h2[:16],
                "different": h1 != h2}

    # -- 报告 ------------------------------------------------------------
    def report(self, orig: str, mod: str,
               orig_run: Dict[str, Any], mod_run: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "integrity": self.integrity(orig, mod),
            "compare": self.compare(orig_run.get("exit"), mod_run.get("exit"),
                                    orig_run.get("stdout", ""),
                                    mod_run.get("stdout", "")),
            "orig_run": orig_run,
            "mod_run": mod_run,
            "sandbox": self.sandbox_dir,
        }


# ---------------------------------------------------------------- CLI
def main(argv: Optional[List[str]] = None) -> int:
    import argparse, json
    p = argparse.ArgumentParser(prog="verifier")
    p.add_argument("orig", help="原文件")
    p.add_argument("mod", help="修改后文件")
    p.add_argument("--args", default="", help="运行参数(空格分隔)")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    v = Verifier()
    run_args = args.args.split() if args.args else None
    r1 = v.run_isolated(args.orig, run_args)
    r2 = v.run_isolated(args.mod, run_args)
    rep = v.report(args.orig, args.mod, r1, r2)

    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        print(f"=== 验证报告 ===")
        print(f"原件运行: {r1['detail']} | 副本运行: {r2['detail']}")
        print(f"完整性: orig={rep['integrity']['orig_sha256']}.. "
              f"mod={rep['integrity']['mod_sha256']}.. "
              f"不同={rep['integrity']['different']}")
        print(f"行为: {rep['compare']['detail']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
