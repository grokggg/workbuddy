#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v4-jailbreak-leak CLI

用法:
  python3 cli.py jailbreak <method> "<问题>"
  python3 cli.py leak <method>
  python3 cli.py all "<问题>"
  python3 cli.py --system "<系统提示词>" ...

只依赖 Python 3.8+ 标准库。
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
