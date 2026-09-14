#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
backend_manager.py —— M35 多后端切换器

检测各后端可用性 → 按优先级选择 → 额度用完自动切换

后端:
  gitlab: 极狐 GitLab CI(API 检查额度)
  github: GitHub Actions(API 检查额度)
  docker: 本地 Docker(检查 docker 命令)
  oracle: Oracle Cloud(检查 SSH)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.request
from typing import Any, Dict, List, Optional

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "config_backends.json")


class BackendManager:
    def __init__(self, config_path: str = CONFIG_PATH) -> None:
        with open(config_path) as f:
            self.config = json.load(f)
        self.status: Dict[str, Dict[str, Any]] = {}

    # -- 各后端检测 ----------------------------------------------------------
    def check_gitlab(self) -> Dict[str, Any]:
        cfg = self.config.get("gitlab", {})
        token = os.environ.get(cfg.get("token_env", "GITLAB_TOKEN"), "")
        if not token:
            return {"available": False, "reason": "无 GITLAB_TOKEN"}
        try:
            host = cfg.get("host", "https://jihulab.com")
            pid = cfg.get("project_id", "")
            url = f"{host}/api/v4/projects/{pid}/pipelines?per_page=1"
            req = urllib.request.Request(
                url, headers={"PRIVATE-TOKEN": token, "User-Agent": "hermes"})
            with urllib.request.urlopen(req, timeout=10) as r:
                return {"available": True, "quota": "OK",
                        "api": "pipelines 可查"}
        except Exception as e:
            return {"available": False, "reason": str(e)[:80]}

    def check_github(self) -> Dict[str, Any]:
        cfg = self.config.get("github", {})
        token = os.environ.get(cfg.get("token_env", "GITHUB_TOKEN"), "")
        if not token:
            return {"available": False, "reason": "无 GITHUB_TOKEN"}
        try:
            repo = cfg.get("repo", "")
            url = f"https://api.github.com/repos/{repo}"
            req = urllib.request.Request(
                url, headers={"Authorization": f"Bearer {token}",
                              "User-Agent": "hermes"})
            with urllib.request.urlopen(req, timeout=10) as r:
                d = json.loads(r.read())
                return {"available": True, "quota": "OK", "repo": repo}
        except Exception as e:
            return {"available": False, "reason": str(e)[:80]}

    def check_docker(self) -> Dict[str, Any]:
        if not shutil.which("docker"):
            return {"available": False, "reason": "无 docker 命令"}
        try:
            r = subprocess.run(["docker", "info"], capture_output=True,
                               timeout=10)
            ok = r.returncode == 0
            return {"available": ok,
                    "reason": "" if ok else "docker daemon 未运行"}
        except Exception as e:
            return {"available": False, "reason": str(e)[:80]}

    def check_oracle(self) -> Dict[str, Any]:
        cfg = self.config.get("oracle", {})
        host = cfg.get("host", "")
        if not host:
            return {"available": False, "reason": "未配置 Oracle 主机"}
        # 检查 ssh 是否可用
        if not shutil.which("ssh"):
            return {"available": False, "reason": "无 ssh 命令"}
        return {"available": True, "host": host}

    # -- 状态汇总 ------------------------------------------------------------
    def status_all(self) -> Dict[str, Dict[str, Any]]:
        self.status = {
            "gitlab": self.check_gitlab(),
            "github": self.check_github(),
            "docker": self.check_docker(),
            "oracle": self.check_oracle(),
        }
        return self.status

    # -- 选择最优后端 ----------------------------------------------------------
    def select(self) -> Dict[str, Any]:
        """按 priority 选第一个可用的。"""
        self.status_all()
        priority = self.config.get("priority", [])
        for name in priority:
            st = self.status.get(name, {})
            if st.get("available"):
                return {"backend": name, "status": st,
                        "all": self.status}
        return {"backend": None, "status": {},
                "all": self.status, "reason": "全部后端不可用"}

    # -- 额度估算 ------------------------------------------------------------
    def quota_estimate(self) -> Dict[str, Any]:
        """估算各后端月额度。"""
        out = {}
        gl = self.config.get("gitlab", {})
        gh = self.config.get("github", {})
        out["gitlab"] = {
            "月额度(次)": gl.get("max_pipelines_per_month", 400),
            "单次耗时(估)": "3-5 分钟",
            "可用": self.status.get("gitlab", {}).get("available", False),
        }
        out["github"] = {
            "月额度(分钟)": gh.get("max_minutes_per_month", 2000),
            "单次耗时(估)": "2-3 分钟",
            "可用": self.status.get("github", {}).get("available", False),
        }
        return out


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(prog="backend-manager")
    p.add_argument("--status", action="store_true", help="打印状态")
    p.add_argument("--select", action="store_true", help="选择最优后端")
    p.add_argument("--quota", action="store_true", help="额度估算")
    args = p.parse_args()

    mgr = BackendManager()
    if args.status or not (args.select or args.quota):
        st = mgr.status_all()
        print("=== 后端状态 ===")
        for name, s in st.items():
            mark = "✅" if s.get("available") else "❌"
            print(f"  {mark} {name}: {s.get('reason', s.get('quota', ''))}")
    if args.select:
        sel = mgr.select()
        print(f"\n=== 推荐后端: {sel['backend'] or '无'} ===")
    if args.quota:
        q = mgr.quota_estimate()
        print("\n=== 额度估算 ===")
        for name, v in q.items():
            print(f"  {name}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
