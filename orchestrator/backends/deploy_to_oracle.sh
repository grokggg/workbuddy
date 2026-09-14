#!/usr/bin/env bash
# deploy_to_oracle.sh —— M36 一键部署工具链到 Oracle VM
# 用法: ./deploy_to_oracle.sh <公网IP> [SSH密钥]
set -e

HOST="${1:?用法: $0 <公网IP> [SSH密钥]}"
KEY="${2:-~/.ssh/oracle_arm}"
USER="ubuntu"
REMOTE="~/up-tools"

echo "=== [1/3] 上传工具链 ==="
scp -i "$KEY" -o StrictHostKeyChecking=no -r \
  ../../real-binaries ../../dynamic-crackmes ../../lib \
  ../../unified-analysis ../../orchestrator "$USER@$HOST:$REMOTE/"

echo "=== [2/3] 远程验证 ==="
ssh -i "$KEY" "$USER@$HOST" "cd $REMOTE && ls lib/ | head -5 && echo '部署 OK'"

echo "=== [3/3] 测试运行 ==="
ssh -i "$KEY" "$USER@$HOST" "cd $REMOTE && python3 unified-analysis/analysis_all.py real-binaries/crackme-angr --out /tmp/o --json 2>&1 | head -8 || true"

echo "Oracle 部署完成 ✅"
