#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""中转站管理 CLI: add / list / check / switch 子命令。"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib.engine import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
