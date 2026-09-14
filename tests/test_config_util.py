#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""config_util.py 单元测试"""
from __future__ import annotations

import json
import copy
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent  # up-tools 根
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "lib"))

from lib.config_util import (  # noqa: E402
    DEFAULT_CONFIG,
    ENV_MAP,
    load_config,
    resolve_param,
)


class TestLoadConfig(unittest.TestCase):
    def test_default(self):
        cfg = load_config(None)
        self.assertIn("v2", cfg)
        self.assertIn("v3", cfg)
        self.assertIn("v4", cfg)
        self.assertIn("v5", cfg)

    def test_load_file(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "config.json"
            p.write_text(json.dumps({"v2": {"target": "/tmp/app"}}))
            cfg = load_config(str(p))
            self.assertEqual(cfg["v2"]["target"], "/tmp/app")
            # 默认合并
            self.assertIn("asar", cfg["v2"])

    def test_load_missing(self):
        cfg = load_config("/nonexistent.json")
        self.assertEqual(cfg["v2"]["target"], "")


class TestResolve(unittest.TestCase):
    def setUp(self):
        self.cfg = copy.deepcopy(DEFAULT_CONFIG)
        # 清环境变量
        for k in set(ENV_MAP.values()):
            os.environ.pop(k, None)

    def test_cli_priority(self):
        r = resolve_param(self.cfg, "v2", "target", env="TARGET_PATH",
                          default="", cli_value="/cli")
        self.assertEqual(r, "/cli")

    def test_env_priority(self):
        os.environ["TARGET_PATH"] = "/env"
        r = resolve_param(self.cfg, "v2", "target", env="TARGET_PATH",
                          default="")
        self.assertEqual(r, "/env")

    def test_config_value(self):
        self.cfg["v2"]["target"] = "/cfg"
        r = resolve_param(self.cfg, "v2", "target", env="TARGET_PATH",
                          default="")
        self.assertEqual(r, "/cfg")

    def test_default(self):
        r = resolve_param(self.cfg, "v2", "target", env="TARGET_PATH",
                          default="")
        self.assertEqual(r, "")

    def test_env_map_entries(self):
        self.assertEqual(ENV_MAP[("v2", "target")], "TARGET_PATH")
        self.assertEqual(ENV_MAP[("v2", "asar")], "APP_ASAR")
        self.assertEqual(ENV_MAP[("v5", "target_file")], "V5_TARGET_FILE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
