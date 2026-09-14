#!/usr/bin/env bash
# 01-agents-md-universal 安装/自检
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"
echo "== 01-agents-md-universal 安装/自检 =="
PY=python3
"$PY" -c "import sys; assert sys.version_info >= (3,8)"
for f in cli.py lib/engine.py tests/test_engine.py README.md; do
  [ -f "$f" ] || { echo "缺 $f" >&2; exit 1; }
done
echo "结构完整"
"$PY" tests/test_engine.py 2>&1 | tail -3
echo "完成。示例: python3 cli.py --name Leila --dry-run"
