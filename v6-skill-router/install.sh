#!/usr/bin/env bash
# v6-skill-router 安装/自检脚本
# 用法: ./install.sh [--check-only | --test | --demo]
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

echo "== v6-skill-router 安装/自检 =="

# 1. 环境自检
echo "[1/3] Python 环境..."
PY=python3
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "错误: 找不到 python3" >&2; exit 1
fi
"$PY" -c "import sys; assert sys.version_info >= (3,8), '需要 Python 3.8+'; print('  Python', sys.version.split()[0])"

# 2. 结构自检
echo "[2/3] 目录结构..."
for f in cli.py lib/router.py router_table.yaml tests/test_router.py README.md; do
  [ -f "$f" ] || { echo "错误: 缺 $f" >&2; exit 1; }
done
echo "  结构完整"

# 3. 跑测试
echo "[3/3] 运行单元测试..."
if [ "${1:-}" = "--check-only" ]; then
  echo "  (--check-only 跳过测试)"
  exit 0
fi
"$PY" tests/test_router.py 2>&1 | tail -5

echo
echo "完成。示例:"
echo "  python3 cli.py demo"
echo "  python3 cli.py route \"用 iv8 补环境生成脚本\""
