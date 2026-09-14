#!/usr/bin/env bash
# setup_oracle.sh —— M36 一键在 Oracle VM 装全套工具
# 用法: ./setup_oracle.sh <公网IP> [SSH密钥]
set -e

HOST="${1:?用法: $0 <公网IP> [SSH密钥]}"
KEY="${2:-~/.ssh/oracle_arm}"
USER="ubuntu"

echo "=== [1/5] SSH 连通性 ==="
ssh -i "$KEY" -o StrictHostKeyChecking=no "$USER@$HOST" "uname -m && echo 'SSH OK'"

echo "=== [2/5] 系统依赖 ==="
ssh -i "$KEY" "$USER@$HOST" "sudo apt-get update -qq && sudo apt-get install -y -qq gcc gdb binutils python3-pip git"

echo "=== [3/5] Python 库 ==="
ssh -i "$KEY" "$USER@$HOST" "pip3 install --quiet capstone pyelftools pefile angr unicorn"

echo "=== [4/5] 验证 ==="
ssh -i "$KEY" "$USER@$HOST" "python3 -c 'import capstone, elftools, pefile; print(\"deps OK\")'"

echo "=== [5/5] 完成 ==="
echo "Oracle VM 工具链就绪 ✅"
