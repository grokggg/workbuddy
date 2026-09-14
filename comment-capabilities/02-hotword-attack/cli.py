#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
02-hotword-attack CLI —— 热词攻击: 热度污染分析 + 检索影响评估

用法示例:
  python3 cli.py analyze '今日召开重要会议, 会议部署了最新政策文件。'
  python3 cli.py analyze --file comment.txt --json
  python3 cli.py analyze --hotwords custom.yaml '自定义词表下的污染分析'
  python3 cli.py retrieve --query '会议政策' \
      --docs '会议部署了最新政策' '普通无关文本' --json
  python3 cli.py retrieve --query '人工智能' --docs-file docs.txt --top-k 5
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib.engine import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
