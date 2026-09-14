#!/usr/bin/env bash
# v2-codex-skill-injection —— 验证脚本（POSIX）
#
# 三层校验：
#   1. kit 自身资产   —— assets 里的 SKILL.md / references 在不在
#   2. 安装点         —— skills 目录、SKILL.md 结构、探针 token、profile 块
#   3. 自读探针判据   —— 把模型刚才的回答传进来，判定 SKILL.md 是否真被加载
#
# 用法：
#   ./verify.sh                                  # 层 1 + 层 2
#   ./verify.sh --framework all
#   ./verify.sh --probe "模型的回答原文"          # 加层 3
#
# Windows 用 verify.ps1。
# 本脚本是薄封装，逻辑在 cli.py + lib/injector.py。
#
# 退出码：0 = 全部通过；1 = 有 high 级问题或探针未命中；2 = 参数错误
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

ARGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --framework) ARGS+=(--framework "${2:-}"); shift 2 ;;
    --probe)     ARGS+=(--probe "${2:-}"); shift 2 ;;
    -h|--help)   sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "未知参数：$1"; exit 2 ;;
  esac
done

PY="$(command -v python3 || command -v python || true)"
[ -n "$PY" ] || { echo "需要 python3（3.8+）"; exit 1; }

"$PY" "$HERE/cli.py" verify "${ARGS[@]}"
