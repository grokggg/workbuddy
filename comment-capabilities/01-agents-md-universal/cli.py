#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
01-agents-md-universal CLI

用法:
  python3 cli.py [--framework generic|claude|codex|cursor] [--name 助手名] [--dry-run]
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "lib"))

from lib.engine import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
