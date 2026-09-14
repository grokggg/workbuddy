#!/usr/bin/env bash
# 03-relay-manager 安装脚本: 纯标准库, 无需 pip 依赖。
set -euo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="${RELAY_BIN_DIR:-$HOME/.local/bin}"
PKG_DIR="$BIN_DIR/relay-manager-pkg"

mkdir -p "$BIN_DIR"

# 复制代码包: cli.py + lib, 放到 <bin>/relay-manager-pkg/
rm -rf "$PKG_DIR"
mkdir -p "$PKG_DIR"
cp "$SRC_DIR/cli.py" "$PKG_DIR/cli.py"
cp -r "$SRC_DIR/lib" "$PKG_DIR/lib"

# 生成可执行启动器: <bin>/relay-manager
LAUNCHER="$BIN_DIR/relay-manager"
cat > "$LAUNCHER" <<EOF
#!/usr/bin/env bash
exec python3 "$PKG_DIR/cli.py" "\$@"
EOF
chmod +x "$LAUNCHER"

# 自检: 跑一遍单元测试
echo "==> 自检单元测试..."
python3 "$SRC_DIR/tests/test_engine.py" >/dev/null 2>&1 || {
    echo "自检失败: 单元测试未通过"; exit 1; }

echo "==> 安装完成"
echo "    入口: $LAUNCHER (代码在 $PKG_DIR)"
echo "    用法:"
echo "      relay-manager add --name main --base-url https://api.example.com/v1 --api-key-env OPENAI_API_KEY"
echo "      relay-manager list --stats"
echo "      relay-manager check"
echo "      relay-manager switch --strategy health"
echo "    若 $BIN_DIR 不在 PATH, 请执行: export PATH=\"$BIN_DIR:\$PATH\""
