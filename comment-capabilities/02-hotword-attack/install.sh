#!/usr/bin/env sh
# 02-hotword-attack 安装脚本: 环境自检 + 跑测试 (纯 Python 3.8+ 标准库, 无需第三方依赖)
set -eu

HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

echo "==> 1/5 Python 环境自检"
command -v python3 >/dev/null 2>&1 || { echo "错误: 未找到 python3"; exit 1; }
PYVER="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
echo "    python3 版本: $PYVER ($(command -v python3))"
python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 8) else 1)' \
  || { echo "错误: 需要 Python >= 3.8"; exit 1; }

echo "==> 2/5 语法检查"
python3 -m py_compile lib/engine.py cli.py tests/test_engine.py

echo "==> 3/5 单元测试"
python3 tests/test_engine.py

echo "==> 4/5 CLI 冒烟测试"
python3 cli.py analyze '今日召开重要会议, 会议部署了最新政策文件, 会议强调落实。'
python3 cli.py retrieve --query '会议政策' \
    --docs '会议部署了最新政策' '普通无关文本, 没有热词。' --json >/dev/null

echo "==> 5/5 完成"
echo "安装成功: 环境自检通过, 单元测试全绿, CLI 冒烟通过"
