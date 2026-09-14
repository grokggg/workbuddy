#!/usr/bin/env sh
# 05-network-verify-burn 安装脚本(纯 Python 3.8+ 标准库, 无需第三方依赖)
set -eu

HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

echo "==> 1/4 语法检查"
python3 -m py_compile lib/engine.py cli.py tests/test_engine.py

echo "==> 2/4 单元测试"
python3 tests/test_engine.py

echo "==> 3/4 CLI 冒烟(单进程完整生命周期: 签发 -> 验证 -> 烧毁 -> 审计)"
python3 cli.py demo

echo "==> 4/4 完成"
echo "安装成功: 全部测试通过, CLI 冒烟通过"
