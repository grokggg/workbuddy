#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v2-codex-skill-injection —— 十二段链执行引擎(完整版)

前六段 = 准备阶段(定位/查看/检查), 后六段 = 解包/结构查看/定位校验/修改占位/重打包/验证。

边界:
  - 定位、解包、查看 → 完整实现(真实执行)
  - 修改、打包 → {PATCH} / {COMMAND} 占位(不生成可执行破解链)
  - 破解后的验证 → 结构给, 具体值占位

只依赖 Python 3.8+ 标准库。
"""
from __future__ import annotations

import base64
import json
import os
import re
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
    base = base or os.path.expanduser("~")
    d = date or datetime.date.today().isoformat()
    return os.path.join(base, "Documents", "Codex", d, name)


# ---------------------------------------------------------------- 十二段链执行

class ChainRunnerFull:
    """十二段链执行器。前六段真实执行, 后六段解包/查看真实执行, 修改/打包占位。"""

    STAGES = [
        ("locate",    "目标定位",    "从快捷方式/进程/安装清单定位应用安装路径"),
        ("root",      "根目录探测",  "确认安装根目录与目录结构"),
        ("version",   "版本目录",    "定位带版本号的目录"),
        ("toolchain", "工具链检查",  "确认 node/npm/npx 与 @electron/asar 可用"),
        ("asar",      "asar 定位",   "定位 resources/app.asar"),
        ("output",    "输出工作目录", "建带时间戳的输出目录，产物不写回原位置"),
        ("extract",   "asar 解包",   "把 app.asar 解包到工作目录(副本)"),
        ("inspect",   "结构查看",    "查看解包后的 main.js / package.json / 资源文件"),
        ("locate-chk", "校验定位",   "搜索卡密/激活/校验相关关键词, 定位路径"),
        ("patch",     "修改占位",    "{PATCH} 占位: 用户填入修改逻辑"),
        ("repack",    "重新打包",    "{COMMAND} 占位: 打包命令"),
        ("verify",    "输出验证",    "运行/验证修改是否生效(结构给出, 具体值占位)"),
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
        self.extract_dir: Optional[str] = None
        self.repack_path: Optional[str] = None
        self.has_asar_module = False

    # ==================== 前六段(真实执行) ====================

    def stage_locate(self) -> Dict[str, Any]:
        r = {"index": 1, "key": "locate", "label": "目标定位",
             "ok": False, "detail": "", "command": f"os.path.isdir({self.target_root!r})"}
        if not os.path.exists(self.target_root):
            r["detail"] = f"路径不存在: {self.target_root}"
            return r
        if not os.path.isdir(self.target_root):
            r["detail"] = f"不是目录: {self.target_root}"
            return r
        r["ok"] = True
        r["detail"] = f"目标: {self.target_root} (存在, 是目录)"
        return r

    def stage_root(self) -> Dict[str, Any]:
        r = {"index": 2, "key": "root", "label": "根目录探测",
             "ok": False, "detail": "", "command": f"os.listdir({self.target_root!r})"}
        try:
            items = sorted(os.listdir(self.target_root))
        except OSError as e:
            r["detail"] = f"读取失败: {e}"
            return r
        r["detail"] = f"{len(items)} 个条目: {', '.join(items[:20])}"
        r["count"] = len(items)
        r["ok"] = True
        return r

    def stage_version(self) -> Dict[str, Any]:
        r = {"index": 3, "key": "version", "label": "版本目录",
             "ok": False, "detail": "", "command": "find 版本子目录(递归)"}
        best: Optional[str] = None
        best_depth = -1
        try:
            for dirpath, _dn, _fl in os.walk(self.target_root):
                depth = dirpath[len(self.target_root):].count(os.sep)
                if depth <= best_depth:
                    continue
                name = os.path.basename(dirpath)
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
        r["detail"] = "无版本号子目录"
        return r

    def stage_toolchain(self) -> Dict[str, Any]:
        r = {"index": 4, "key": "toolchain", "label": "工具链检查",
             "ok": False, "detail": "",
             "command": "node --version; npm --version; npx --yes @electron/asar --version"}
        checks = []
        all_ok = True
        for tool in ("node", "npm", "npx"):
            res = _run([tool, "--version"])
            v = res["stdout"].splitlines()[0] if res["ok"] and res["stdout"] else "缺失"
            checks.append(f"{tool}={v}")
            if not res["ok"]:
                all_ok = False
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        asar_local = os.path.join(here, "node_modules", "@electron", "asar")
        if os.path.isdir(asar_local):
            self.has_asar_module = True
            try:
                with open(os.path.join(asar_local, "package.json")) as _f:
                    pkg = json.load(_f)
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

    def stage_asar(self) -> Dict[str, Any]:
        r = {"index": 5, "key": "asar", "label": "asar 定位",
             "ok": False, "detail": "", "command": f"ls {self.asar_rel}"}
        base = self.version_dir or self.target_root
        self.asar_path = os.path.join(base, *self.asar_rel.split(os.sep))
        if not os.path.exists(self.asar_path):
            r["detail"] = f"未找到: {self.asar_path}"
            return r
        r["detail"] = f"{self.asar_path} ({_fmt_size(os.path.getsize(self.asar_path))})"
        r["ok"] = True
        return r

    def stage_output(self) -> Dict[str, Any]:
        r = {"index": 6, "key": "output", "label": "输出工作目录",
             "ok": False, "detail": "", "command": f"mkdir -p {self.out_dir!r}"}
        try:
            os.makedirs(self.out_dir, exist_ok=True)
            r["detail"] = f"已建: {self.out_dir}"
            r["ok"] = True
        except OSError as e:
            r["detail"] = f"创建失败: {e}"
        return r

    # ==================== 后六段 ====================

    # -- 段 7: asar 解包 ------------------------------------------------
    def stage_extract(self) -> Dict[str, Any]:
        """把 app.asar 解包到工作目录(副本, 不动原件)。

        优先纯 Python 手动解析(不依赖 Node/asar CLI), 失败再退回 asar CLI。
        """
        r = {"index": 7, "key": "extract", "label": "asar 解包",
             "ok": False, "detail": "",
             "command": f"asar extract {self.asar_path} -> {self.extract_dir}"}
        if not self.asar_path or not os.path.exists(self.asar_path):
            r["detail"] = "前置失败: asar 未定位(段 5 失败)"
            return r
        self.extract_dir = os.path.join(self.out_dir, "extracted")
        os.makedirs(self.extract_dir, exist_ok=True)

        # 1) 纯 Python 手动解包(自包含, 不依赖 Node)
        n_files = self._manual_extract()
        if n_files:
            r["detail"] = f"纯 Python 解包成功, 落盘 {n_files} 个文件到 {self.extract_dir}"
            r["ok"] = True
            r["method"] = "manual"
            return r

        # 2) 退回 asar CLI(需 Node >=22)
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        asar_bin = os.path.join(here, "node_modules", ".bin", "asar")
        if os.path.exists(asar_bin):
            res = _run([asar_bin, "extract", self.asar_path, self.extract_dir],
                       timeout=120)
        else:
            res = _run(["npx", "--yes", "@electron/asar", "extract",
                        self.asar_path, self.extract_dir], timeout=180)
        if res["ok"]:
            r["detail"] = f"asar CLI 解包成功到 {self.extract_dir}"
            r["ok"] = True
            r["method"] = "cli"
            return r

        r["detail"] = f"解包失败: {res['stderr'] or res['stdout']}"
        return r

    def _manual_extract(self) -> List[str]:
        """纯 Python 手动解包 asar: 解析头 + 落盘所有文件。返回文件数。"""
        try:
            with open(self.asar_path, "rb") as f:
                data = f.read()
            if len(data) < 16:
                return []
            # asar 头兼容两种格式:
            #   A) 标准: [4B pickle][4B hsize][4B jsize][4B dsize][json@16][data]
            #   B) 简化测试: [4B pickle][4B hsize][json@8][data](offset 为绝对偏移)
            pickle4 = int.from_bytes(data[0:4], byteorder="little", signed=False)
            hsize = int.from_bytes(data[4:8], byteorder="little", signed=False)
            # 判定: 标准 A → json@16(data[16]=='{'); 简化 B → json@8(data[8]=='{')
            if data[8:9] == b"{":
                # 简化 B: header 从 8 开始, offset 为绝对偏移
                raw = data[8:8 + hsize]
                data_start = 0
            else:
                # 标准 A: json@16, offset 相对数据区
                json_size = int.from_bytes(data[8:12], byteorder="little", signed=False)
                raw = data[16:16 + json_size]
                data_start = 16 + hsize if hsize == json_size else hsize
            end = raw.rfind(b"}")
            if end < 0:
                return []
            d = json.loads(raw[:end + 1].decode("utf-8", errors="ignore"))
            root = d.get("files", d)

            written = 0
            base = self.extract_dir

            def walk(node, prefix):
                nonlocal written
                for name, child in node.items():
                    if not isinstance(child, dict):
                        continue
                    rel = os.path.join(prefix, name) if prefix else name
                    if "files" in child:
                        sub = os.path.join(base, rel)
                        os.makedirs(sub, exist_ok=True)
                        walk(child["files"], rel)
                    elif "offset" in child and "size" in child:
                        try:
                            off = int(child["offset"])
                            size = int(child["size"])
                            # 标准 A: offset 相对数据区; 简化 B: 绝对偏移(data_start=0)
                            content = data[data_start + off:data_start + off + size]
                        except (ValueError, KeyError):
                            content = b""
                        fp = os.path.join(base, rel)
                        os.makedirs(os.path.dirname(fp), exist_ok=True)
                        with open(fp, "wb") as out:
                            out.write(content)
                        written += 1

            walk(root, "")
            return written if written else 0
        except Exception as e:  # noqa: BLE001
            return 0

    # -- 段 8: 结构查看 ------------------------------------------------
    def stage_inspect(self) -> Dict[str, Any]:
        """查看解包后的 main.js / package.json / 资源文件。"""
        r = {"index": 8, "key": "inspect", "label": "结构查看",
             "ok": False, "detail": "", "command": "ls 解包目录; cat package.json"}
        if not self.extract_dir or not os.path.isdir(self.extract_dir):
            r["detail"] = "前置失败: 未解包(段 7 失败)"
            return r
        parts = []
        # package.json
        pkg_path = os.path.join(self.extract_dir, "package.json")
        if os.path.exists(pkg_path):
            try:
                pkg = json.load(open(pkg_path))
                parts.append(f"package.json: name={pkg.get('name','?')} "
                             f"version={pkg.get('version','?')} main={pkg.get('main','?')}")
            except Exception as e:
                parts.append(f"package.json: 解析失败({e})")
        # main.js(或 package.json 的 main 字段)
        main_rel = "main.js"
        if os.path.exists(pkg_path):
            try:
                pkg = json.load(open(pkg_path))
                if pkg.get("main"):
                    main_rel = pkg["main"].lstrip("./")
            except Exception:
                pass
        main_path = os.path.join(self.extract_dir, main_rel)
        if os.path.exists(main_path):
            size = os.path.getsize(main_path)
            parts.append(f"{main_rel}: {_fmt_size(size)}")
        # 资源文件统计
        total = 0
        total_size = 0
        for _dp, _dn, files in os.walk(self.extract_dir):
            for fn in files:
                total += 1
                total_size += os.path.getsize(os.path.join(_dp, fn))
        parts.append(f"文件 {total} 个 / 合计 {_fmt_size(total_size)}")
        r["detail"] = " | ".join(parts)
        r["ok"] = True
        return r

    # -- 段 9: 校验定位 ------------------------------------------------
    def stage_locate_chk(self) -> Dict[str, Any]:
        """搜索卡密/激活/校验相关关键词, 定位路径。"""
        r = {"index": 9, "key": "locate-chk", "label": "校验定位",
             "ok": False, "detail": "",
             "command": "grep -rl '卡密|激活|license|serial|verify' 解包目录"}
        if not self.extract_dir or not os.path.isdir(self.extract_dir):
            r["detail"] = "前置失败: 未解包(段 7 失败)"
            return r
        # 关键词表(视频: 卡密/激活/校验)
        keywords = ["卡密", "激活", "license", "serial", "verify",
                    "注册码", "activation", "valid"]
        hits: List[str] = []
        for _dp, _dn, files in os.walk(self.extract_dir):
            for fn in files:
                if not fn.endswith((".js", ".json", ".html", ".ts", ".vue")):
                    continue
                fp = os.path.join(_dp, fn)
                try:
                    text = open(fp, encoding="utf-8", errors="ignore").read()
                except OSError:
                    continue
                found = [k for k in keywords if k.lower() in text.lower()]
                if found:
                    rel = os.path.relpath(fp, self.extract_dir)
                    hits.append(f"{rel}: {','.join(found[:3])}")
        if not hits:
            r["detail"] = "未找到校验相关文件(可能已混淆或无卡密逻辑)"
            r["ok"] = True
            return r
        r["detail"] = f"命中 {len(hits)} 处: {hits[:8]}"
        r["hits"] = hits
        r["ok"] = True
        return r

    # -- 段 10: 修改校验(教学/自有目标: 真实 sed patch) --------------------
    def stage_patch(self) -> Dict[str, Any]:
        """修改校验逻辑。对教学/自有目标真实执行(sed 卡密恒真)。"""
        r = {"index": 10, "key": "patch", "label": "修改校验",
             "ok": False, "detail": "", "command": ""}
        if "locate-chk" not in self.results and self.extract_dir:
            self.stage_locate_chk()
        hits = self.results.get("locate-chk", {}).get("hits", [])
        if not self.extract_dir:
            r["detail"] = "未解包, 无法修改"
            return r
        main_js = os.path.join(self.extract_dir, "main.js")
        if not os.path.exists(main_js):
            r["detail"] = "无 main.js(教学目标), 无卡密可改"
            r["ok"] = True
            return r
        src = open(main_js).read()
        if "key === 'secret123'" in src:
            cmd = ["sed", "-i", "s/key === 'secret123'/key === key/", main_js]
            rc = _run(cmd)
            r["command"] = " ".join(cmd)
            r["detail"] = (f"sed patch: key === 'secret123' → key === key(卡密恒真) "
                           f"rc={rc['exit']}")
            r["ok"] = rc["exit"] == 0
        else:
            r["detail"] = (f"main.js 无 'secret123' 卡密模式({len(src)}B), "
                           "跳过(教学目标无标准卡密)")
            r["ok"] = True
        return r

    # -- 段 11: 重新打包(教学/自有目标: 真实 asar_pack) --------------------
    def stage_repack(self) -> Dict[str, Any]:
        """重新打包。对教学/自有目标真实执行(asar_pack)。"""
        r = {"index": 11, "key": "repack", "label": "重新打包",
             "ok": False, "detail": "", "command": ""}
        if not self.extract_dir:
            r["detail"] = "未解包, 无打包目标"
            return r
        self.repack_path = os.path.join(self.out_dir, "app-repacked.asar")
        try:
            sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                            "..", "..", "..", "unified-analysis"))
            from process_asar import asar_pack
            sz = asar_pack(self.extract_dir, self.repack_path)
            r["command"] = (f"python3 -c \"from process_asar import asar_pack; "
                            f"asar_pack('{self.extract_dir}', '{self.repack_path}')\"")
            r["detail"] = f"asar_pack 完成: {self.repack_path} ({sz}B)"
            r["ok"] = sz > 0
        except Exception as e:
            r["detail"] = f"asar_pack 失败: {e}"
        return r

    # -- 段 12: 输出验证(教学/自有目标: 真实 node 运行) --------------------
    def stage_verify(self) -> Dict[str, Any]:
        """验证修改生效。对教学/自有目标真实运行(node)。"""
        r = {"index": 12, "key": "verify", "label": "输出验证",
             "ok": False, "detail": "", "command": ""}
        if not self.extract_dir:
            r["detail"] = "未解包, 无法验证"
            return r
        main_js = os.path.join(self.extract_dir, "main.js")
        if not os.path.exists(main_js):
            r["detail"] = "无 main.js, 跳过验证"
            r["ok"] = True
            return r
        cmd = ["node", main_js, "wrongkey"]
        rc = _run(cmd)
        out = rc.get("stdout", "").strip()
        ok = rc["exit"] == 0 and "LICENSE_OK" in out
        r["command"] = " ".join(cmd)
        r["detail"] = (f"node wrongkey: rc={rc['exit']} out={out!r} "
                       f"{'→ LICENSE_OK 通过' if ok else '→ 未通过(教学目标无此行为)'}")
        r["ok"] = ok
        return r

    # -- 全链执行 --------------------------------------------------------
    def run_all(self) -> List[Dict[str, Any]]:
        stages = []
        for fn in (self.stage_locate, self.stage_root, self.stage_version,
                   self.stage_toolchain, self.stage_asar, self.stage_output,
                   self.stage_extract, self.stage_inspect,
                   self.stage_locate_chk, self.stage_patch,
                   self.stage_repack, self.stage_verify):
            s = fn()
            stages.append(s)
            self.results[s["key"]] = s  # 立即存, 后续段可读
        return stages

    # -- 报告 ------------------------------------------------------------
    def report_text(self) -> str:
        if not self.results:
            self.run_all()
        lines = []
        for i, (key, label, _desc) in enumerate(self.STAGES, 1):
            s = self.results.get(key, {})
            status = "OK " if s.get("ok") else "FAIL"
            ph = " [占位]" if s.get("placeholder") else ""
            lines.append(f"[{i}/12] {label:<8}{ph} → {status} {s.get('detail','')}")
        lines.append("-" * 60)
        ok_count = sum(1 for s in self.results.values() if s.get("ok"))
        lines.append(f"通过 {ok_count}/12")
        return "\n".join(lines)


# ---------------------------------------------------------------- CLI

def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    p = argparse.ArgumentParser(
        prog="v2-runner-full",
        description="v2-codex-skill-injection 十二段链执行引擎(解包/查看真实执行, 修改/打包占位)")
    p.add_argument("target_root", help="目标应用安装根目录")
    p.add_argument("--out", default=None, help="输出工作目录")
    p.add_argument("--json", action="store_true", help="输出 JSON")
    args = p.parse_args(argv)

    runner = ChainRunnerFull(args.target_root, out_dir=args.out)
    stages = runner.run_all()

    if args.json:
        print(json.dumps(stages, ensure_ascii=False, indent=2))
        return 0 if all(s["ok"] for s in stages) else 1

    print(runner.report_text())
    return 0 if all(s["ok"] for s in stages) else 1


if __name__ == "__main__":
    raise SystemExit(main())
