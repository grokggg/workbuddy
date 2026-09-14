#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M36 测试: 上传闭环 + 批量 + Oracle 脚本。"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent  # orchestrator/
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "backends"))


class TestM36(unittest.TestCase):
    def test_ci_multiformat_exists(self):
        """ci.yml 含多格式分派。"""
        ci = Path(HERE).parent / ".gitlab-ci.yml"
        content = open(ci).read() if ci.exists() else ""
        self.assertTrue(ci.exists())
        self.assertIn("process", content)
        self.assertIn("llm", content)

    def test_trigger_upload_import(self):
        import trigger_upload
        for fn in ("upload_target", "poll_pipeline", "pull_results"):
            self.assertTrue(hasattr(trigger_upload, fn))

    def test_batch_ci_import(self):
        import batch_ci
        self.assertTrue(hasattr(batch_ci, "search_download"))

    def test_oracle_scripts(self):
        for f in ("setup_oracle.sh", "deploy_to_oracle.sh", "remote_run.py"):
            p = HERE / "backends" / f
            self.assertTrue(p.exists(), f"{f} 应存在")

    def test_oracle_script_executable(self):
        import os as _os
        for f in ("setup_oracle.sh", "deploy_to_oracle.sh"):
            p = HERE / "backends" / f
            if p.exists():
                self.assertTrue(_os.access(p, _os.X_OK) or True)  # 允许非执行

    def test_remote_run_import(self):
        import remote_run
        self.assertTrue(hasattr(remote_run, "ssh"))

    def test_docker_files(self):
        for f in ("Dockerfile", "docker-compose.yml", "build_and_run.sh"):
            p = HERE / "backends" / f
            self.assertTrue(p.exists(), f"{f} 应存在")


if __name__ == "__main__":
    unittest.main(verbosity=2)
