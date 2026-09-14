#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M35 测试: 后端切换器。"""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent  # orchestrator/
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "backends"))

from backend_manager import BackendManager  # noqa: E402


class TestBackendManager(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mgr = BackendManager()
        cls.mgr.status_all()

    def test_config_exists(self):
        cfg = json.load(open(HERE / "backends" / "config_backends.json"))
        self.assertIn("priority", cfg)
        self.assertIn("gitlab", cfg)
        self.assertIn("github", cfg)
        self.assertIn("docker", cfg)
        self.assertIn("oracle", cfg)

    def test_status_all_keys(self):
        st = self.mgr.status_all()
        for k in ("gitlab", "github", "docker", "oracle"):
            self.assertIn(k, st)
            self.assertIn("available", st[k])

    def test_select_returns_backend(self):
        sel = self.mgr.select()
        self.assertIn("backend", sel)
        self.assertIn("all", sel)

    def test_select_priority(self):
        """无 token 时 gitlab/github 应不可用, docker/oracle 检测正常。"""
        st = self.mgr.status_all()
        # 无 GITLAB_TOKEN/GITHUB_TOKEN 时应报不可用
        if not os.environ.get("GITLAB_TOKEN"):
            self.assertFalse(st["gitlab"]["available"])
        if not os.environ.get("GITHUB_TOKEN"):
            self.assertFalse(st["github"]["available"])

    def test_quota_estimate(self):
        q = self.mgr.quota_estimate()
        self.assertIn("gitlab", q)
        self.assertIn("github", q)

    def test_docker_check_no_crash(self):
        """docker 检测不崩溃(无论有没有 docker)。"""
        st = self.mgr.check_docker()
        self.assertIn("available", st)


if __name__ == "__main__":
    unittest.main(verbosity=2)
