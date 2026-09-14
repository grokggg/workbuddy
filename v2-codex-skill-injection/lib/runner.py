#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v2-codex-skill-injection —— 六段链执行引擎

把视频 BV15y3U6oEmt 第 6 步的 PowerShell 六段链, 用 Python 真正执行。
每段都是"定位/查看/检查"性质(只读), 不写回、不打补丁。

与 workflow.render_chain 的区别:
  render_chain 生成命令**文本**(给人看/给模型执行)
  runner       实际**执行**每段命令, 返回每步结果

只依赖 Python 3.8+ 标准库。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import datetime
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------- 工具函数

def _run(cmd: List[str], timeout: int = 30) -> Dict[str, Any]:
    """执行命令, 返回 {ok, stdout, stderr, exit}。失败不抛异常。"""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout)
        return {
            "ok": p.returncode == 0,
            "stdout": (p.stdout or "").strip(),
            "stderr": (p.stderr or "").strip(),
            "exit": p.returncode,
        }
    except FileNotFoundError:
        return {"ok": False, "stdout": "", "stderr": f"命令不存在: {cmd[0]}", "exit": 127}
    except subprocess.TimeoutExpired:
        return {"ok": False, "stdout": "", "stderr": f"超时(>{timeout}s)", "exit": 124}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "stdout": "", "stderr": str(e), "exit": 1}


def _fmt_size(n: Optional[int]) -> str:
    if n is None:
        return "?"
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


def work_dir(base: Optional[str] = None, date: Optional[str] = None,
             name: str = "work") -> str:
    """输出目录: ~/Documents/Codex/<日期>/work/ —— 与视频第 6 步一致。"""
    base = base or os.path.expanduser("~")
    d = date or datetime.date.today().isoformat()
    return os.path.join(base, "Documents", "Codex", d, name)


# ---------------------------------------------------------------- 六段链执行

class ChainRunner:
    """六段链执行器。每段真实运行, 返回结构化结果。"""

    STAGES = [
        ("locate",    "目标定位",   "从快捷方式/进程/安装清单定位应用安装路径"),
        ("root",      "根目录探测", "确认安装根目录与目录结构"),
        ("version",   "版本目录",   "定位带版本号的目录"),
        ("toolchain", "工具链检查", "确认 node/npm/npx 与 @electron/asar 可用"),
        ("asar",      "asar 定位",  "定位 resources/app.asar"),
        ("output",    "输出工作目录", "建带时间戳的输出目录，产物不写回原位置"),
    ]

    def __init__(self, target_root: str,
                 out_dir: Optional[str] = None,
                 asar_rel: str = os.path.join("resources", "app.asar")) -> None:
        self.target_root = os.path.abspath(target_root)
        self.out_dir = out_dir or work_dir()
        self.asar_rel = asar_rel
        self.results: Dict[str, Dict[str, Any]] = {}
        self.version_dir: Optional[str] = None
        self.asar_path: Optional[str] = None

    # -- 段 1: 目标定位 ------------------------------------------------
    def stage_locate(self) -> Dict[str, Any]:
        """定位目标: 确认 target_root 存在且是目录。"""
        r = {
            "index": 1, "key": "locate", "label": "目标定位",
            "ok": False, "detail": "", "command": f"os.path.isdir({self.target_root!r})",
        }
        if not os.path.exists(self.target_root):
            r["detail"] = f"路径不存在: {self.target_root}"
            return r
        if not os.path.isdir(self.target_root):
            r["detail"] = f"不是目录: {self.target_root}"
            return r
        r["ok"] = True
        r["detail"] = f"目标: {self.target_root} (存在, 是目录)"
        return r

    # -- 段 2: 根目录探测 ------------------------------------------------
    def stage_root(self) -> Dict[str, Any]:
        """列根目录内容(前 20 项)。"""
        r = {
            "index": 2, "key": "root", "label": "根目录探测",
            "ok": False, "detail": "", "command": f"os.listdir({self.target_root!r})",
        }
        try:
            items = sorted(os.listdir(self.target_root))
        except OSError as e:
            r["detail"] = f"读取失败: {e}"
            return r
        if not items:
            r["detail"] = "空目录"
            r["ok"] = True
            return r
        shown = items[:20]
        r["detail"] = f"{len(items)} 个条目: {', '.join(shown)}"
        r["count"] = len(items)
        r["ok"] = True
        return r

    # -- 段 3: 版本目录 ------------------------------------------------
    def stage_version(self) -> Dict[str, Any]:
        """定位带版本号的子目录(递归找最深, 形如 x64/4.2.0)。"""
        r = {
            "index": 3, "key": "version", "label": "版本目录",
            "ok": False, "detail": "", "command": "find 版本子目录(递归)",
        }
        import re
        # BFS 找所有子目录, 取"含版本号模式且最深"的
        # 版本号模式: 纯数字(4.2.0) 或 平台/数字(x64/4.2.0) —— 避免目录名含随机数字误判
        best: Optional[str] = None
        best_depth = -1
        try:
            for dirpath, dirnames, _files in os.walk(self.target_root):
                depth = dirpath[len(self.target_root):].count(os.sep)
                if depth <= best_depth:
                    continue
                name = os.path.basename(dirpath)
                # 版本号: 纯数字段(4.2.0 / 2024.1) 或 x64/4.2.0 形态
                if (re.fullmatch(r"\d+(\.\d+)*", name)
                        or re.fullmatch(r"v?\d+\.\d+(\.\d+)*", name, re.I)
                        or (depth >= 1 and re.fullmatch(r"\d+(\.\d+)*",
                            os.path.basename(os.path.dirname(dirpath)))
                            and re.fullmatch(r"\d+(\.\d+)*", name))):
                    best = dirpath
                    best_depth = depth
        except OSError as e:
            r["detail"] = f"读取失败: {e}"
            return r
        if best:
            self.version_dir = best
            r["detail"] = f"版本目录: {best}"
            r["ok"] = True
            return r
        # 退化: 任意最深子目录
        deepest: Optional[str] = None
        deep = -1
        try:
            for dirpath, _dirnames, _files in os.walk(self.target_root):
                depth = dirpath[len(self.target_root):].count(os.sep)
                if depth > deep:
                    deepest = dirpath
                    deep = depth
        except OSError:
            pass
        if deepest and deepest != self.target_root:
            self.version_dir = deepest
            r["detail"] = f"无版本号目录, 取最深子目录: {deepest}"
            r["ok"] = True
            return r
        r["detail"] = "无子目录"
        return r

    # -- 段 4: 工具链检查 ------------------------------------------------
    def stage_toolchain(self) -> Dict[str, Any]:
        """检查 node/npm/npx 与 @electron/asar。"""
        r = {
            "index": 4, "key": "toolchain", "label": "工具链检查",
            "ok": False, "detail": "", "command": "node --version; npm --version; npx --yes @electron/asar --version",
        }
        checks = []
        all_ok = True
        for tool in ("node", "npm", "npx"):
            res = _run([tool, "--version"])
            v = res["stdout"].splitlines()[0] if res["ok"] and res["stdout"] else "缺失"
            checks.append(f"{tool}={v}")
            if not res["ok"]:
                all_ok = False
        # asar 检查: 本地 node_modules 里有即可(版本不强制, 视频语义是"可选依赖")
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        asar_local = os.path.join(here, "node_modules", "@electron", "asar")
        if os.path.isdir(asar_local):
            try:
                import json as _json
                pkg = _json.load(open(os.path.join(asar_local, "package.json")))
                asar_v = pkg.get("version", "?")
            except Exception:
                asar_v = "?"
            checks.append(f"@electron/asar={asar_v} (local)")
        else:
            res = _run(["npx", "--yes", "@electron/asar", "--version"], timeout=60)
            asar_v = res["stdout"].splitlines()[0] if res["ok"] and res["stdout"] else "缺失"
            checks.append(f"@electron/asar={asar_v}")
            if not res["ok"]:
                all_ok = False
        r["detail"] = " | ".join(checks)
        r["ok"] = all_ok
        return r

    # -- 段 5: asar 定位 ------------------------------------------------
    def stage_asar(self) -> Dict[str, Any]:
        """定位 resources/app.asar。"""
        r = {
            "index": 5, "key": "asar", "label": "asar 定位",
            "ok": False, "detail": "", "command": f"ls {self.asar_rel}",
        }
        base = self.version_dir or self.target_root
        self.asar_path = os.path.join(base, *self.asar_rel.split(os.sep))
        if not os.path.exists(self.asar_path):
            r["detail"] = f"未找到: {self.asar_path}"
            return r
        size = os.path.getsize(self.asar_path)
        r["detail"] = f"{self.asar_path} ({_fmt_size(size)})"
        r["ok"] = True
        return r

    # -- 段 6: 输出工作目录 ------------------------------------------------
    def stage_output(self) -> Dict[str, Any]:
        """建带时间戳的输出目录, 不写回原位置。"""
        r = {
            "index": 6, "key": "output", "label": "输出工作目录",
            "ok": False, "detail": "", "command": f"mkdir -p {self.out_dir!r}",
        }
        try:
            os.makedirs(self.out_dir, exist_ok=True)
            r["detail"] = f"已建: {self.out_dir}"
            r["ok"] = True
        except OSError as e:
            r["detail"] = f"创建失败: {e}"
        return r

    # -- 全链执行 --------------------------------------------------------
    def run_all(self) -> List[Dict[str, Any]]:
        """执行全部六段, 返回每步结果。"""
        stages = [
            self.stage_locate(),
            self.stage_root(),
            self.stage_version(),
            self.stage_toolchain(),
            self.stage_asar(),
            self.stage_output(),
        ]
        self.results = {s["key"]: s for s in stages}
        return stages

    # -- 报告 ------------------------------------------------------------
    def report_text(self) -> str:
        """生成与视频状态栏一致的文本报告。"""
        if not self.results:
            self.run_all()
        lines = []
        for i, (key, label, _desc) in enumerate(self.STAGES, 1):
            s = self.results.get(key, {})
            status = "OK " if s.get("ok") else "FAIL"
            lines.append(f"[{i}/6] {label:<8} → {status} {s.get('detail','')}")
        lines.append("-" * 50)
        ok_count = sum(1 for s in self.results.values() if s.get("ok"))
        lines.append(f"通过 {ok_count}/6")
        return "\n".join(lines)


# ---------------------------------------------------------------- CLI

def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    p = argparse.ArgumentParser(
        prog="v2-runner",
        description="v2-codex-skill-injection 六段链执行引擎(真实执行, 只读查看)")
    p.add_argument("target_root", help="目标应用安装根目录")
    p.add_argument("--out", default=None, help="输出工作目录(默认 ~/Documents/Codex/<日期>/work)")
    p.add_argument("--json", action="store_true", help="输出 JSON")
    args = p.parse_args(argv)

    runner = ChainRunner(args.target_root, out_dir=args.out)
    stages = runner.run_all()

    if args.json:
        import json
        print(json.dumps(stages, ensure_ascii=False, indent=2))
        return 0 if all(s["ok"] for s in stages) else 1

    print(runner.report_text())
    return 0 if all(s["ok"] for s in stages) else 1


if __name__ == "__main__":
    raise SystemExit(main())
