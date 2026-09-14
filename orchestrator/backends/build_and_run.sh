#!/usr/bin/env bash
# build_and_run.sh —— M35 Docker 后端一键构建 + 运行
# 用法: ./build_and_run.sh [目标路径] [输出目录]
set -e

cd "$(dirname "$0")/../.."
TARGET="${1:-real-binaries/crackme-angr}"
OUT="${2:-orchestrator/backends/out}"

echo "=== [1/3] 构建镜像 ==="
docker build -f orchestrator/backends/Dockerfile -t up-tools:latest .

echo "=== [2/3] 运行分析 ==="
mkdir -p "$OUT"
docker run --rm \
  -v "$(pwd)/real-binaries:/workspace/real-binaries" \
  -v "$(pwd)/dynamic-crackmes:/workspace/dynamic-crackmes" \
  -v "$(pwd)/$OUT:/workspace/out" \
  up-tools:latest "$TARGET" --out /workspace/out

echo "=== [3/3] 结果 ==="
ls -la "$OUT/"
echo "完成 ✅"
