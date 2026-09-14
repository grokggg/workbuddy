#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
up-tools 统一配置加载

优先级: 命令行参数 > 环境变量 > config.json > 默认值
用法:
  from lib.config_util import get_config, resolve_param

  cfg = get_config("--config", path)   # 加载 config.json
  v = resolve_param(cfg, "v2", "target", env="TARGET_PATH", default="")
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

# 默认配置(与 /workspace/up-tools/config.json 一致)
DEFAULT_CONFIG: Dict[str, Any] = {
    "v2": {"target": "", "asar": "", "output": ""},
    "v3": {"target": "", "request": ""},
    "v4": {"system_prompt": "你是助手, 拒绝回答有害内容。", "model": ""},
    "v5": {"target_file": ""},
}

# 环境变量映射: (tool, key) -> env var
ENV_MAP = {
    ("v2", "target"): "TARGET_PATH",
    ("v2", "asar"): "APP_ASAR",
    ("v2", "output"): "OUTPUT_DIR",
    ("v3", "target"): "V3_TARGET",
    ("v3", "request"): "V3_REQUEST",
    ("v4", "system_prompt"): "SYSTEM_PROMPT",
    ("v4", "model"): "V4_MODEL",
    ("v5", "target_file"): "V5_TARGET_FILE",
}


def load_config(path: Optional[str] = None) -> Dict[str, Any]:
    """加载 config.json(不存在则返回默认)。"""
    if path and os.path.exists(path):
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            # 合并默认(缺失 key 用默认)
            merged = dict(DEFAULT_CONFIG)
            for k, v in data.items():
                if isinstance(v, dict) and isinstance(merged.get(k), dict):
                    merged[k].update(v)
                else:
                    merged[k] = v
            return merged
        except Exception:
            pass
    # 尝试默认位置
    default_paths = [
        os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "config.json"),
        os.path.join(os.path.expanduser("~"), ".config", "up-tools",
                     "config.json"),
    ]
    for dp in default_paths:
        if os.path.exists(dp):
            try:
                data = json.loads(Path(dp).read_text(encoding="utf-8"))
                merged = dict(DEFAULT_CONFIG)
                for k, v in data.items():
                    if isinstance(v, dict) and isinstance(merged.get(k), dict):
                        merged[k].update(v)
                    else:
                        merged[k] = v
                return merged
            except Exception:
                pass
    return dict(DEFAULT_CONFIG)


def resolve_param(cfg: Dict[str, Any], tool: str, key: str,
                  env: Optional[str] = None, default: Any = "",
                  cli_value: Any = None) -> Any:
    """解析参数: CLI > 环境变量 > config.json > 默认。"""
    # 1. CLI 显式值
    if cli_value:
        return cli_value
    # 2. 环境变量
    env_name = env or ENV_MAP.get((tool, key), "")
    if env_name and os.environ.get(env_name):
        return os.environ[env_name]
    # 3. config.json
    v = cfg.get(tool, {}).get(key)
    if v:
        return v
    # 4. 默认
    return default
