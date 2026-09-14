#!/usr/bin/env bash
# v2-codex-skill-injection —— 安装脚本（POSIX：Linux / macOS / WSL / Git Bash）
#
# 复现 BV15y3U6oEmt（by茶，197s）的 Codex Skill 目录注入：
#   SKILL.md 落盘 → 激活词触发 → 模型自读 SKILL.md → 能力声明 → 工具链
#
# Windows 原生 PowerShell 请用 install.ps1。
# 本脚本是薄封装，逻辑全在 cli.py + lib/injector.py，与 install.ps1 共用。
#
# 用法：
#   ./install.sh                     # 装到 codex（默认，视频原框架）
#   ./install.sh --framework all     # 四个框架都装
#   ./install.sh --dry-run           # 只看会往哪写，不落盘
#   ./install.sh --uninstall         # 卸载（只删自己写的块）
#   ./install.sh --force             # 重置自读探针 token
#   ./install.sh --with-node-deps    # 顺带装 @electron/asar（asar 解包用）
#
# 退出码：0 = 通过；1 = 有失败；2 = 参数错误
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SUB="install"
ARGS=()
NODE_DEPS=""

while [ $# -gt 0 ]; do
  case "$1" in
    --framework)      ARGS+=(--framework "${2:-}"); shift 2 ;;
    --dry-run)        ARGS+=(--dry-run); shift ;;
    --uninstall)      SUB="uninstall"; shift ;;
    --force)          ARGS+=(--force); shift ;;
    --with-node-deps) NODE_DEPS="1"; shift ;;
    -h|--help)        sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "未知参数：$1（用 --help 看用法）"; exit 2 ;;
  esac
done

PY="$(command -v python3 || command -v python || true)"
[ -n "$PY" ] || { echo "需要 python3（3.8+）"; exit 1; }

"$PY" "$HERE/cli.py" "$SUB" "${ARGS[@]}"
rc=$?

if [ -n "$NODE_DEPS" ]; then
  echo
  echo "────────────────────────────────────────────────"
  echo "装 @electron/asar（asar 解包用，可选）"
  if command -v npm >/dev/null 2>&1; then
    (cd "$HERE" && npm install @electron/asar --no-audit --no-fund)
  else
    echo "  [skip] 没找到 npm。用 npx --yes @electron/asar 也能跑 extract。"
  fi
elif [ "$SUB" = "install" ]; then
  echo
  echo "提示：asar 解包需要 @electron/asar。"
  echo "      跑 ./install.sh --with-node-deps 装，或用 npx 临时拉。"
fi

exit $rc
