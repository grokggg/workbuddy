#!/usr/bin/env bash
# ============================================================
# up-tools-local install.sh
# 本地部署: 装 Python 分析库 + 反汇编工具 + 验证
# 用法: ./install.sh
# ============================================================
set -e

echo "=== up-tools-local 安装开始 ==="

# ── 1. Python 环境 ──
echo "[1/5] Python 环境..."
if command -v python3 >/dev/null 2>&1; then
    echo "  ✓ python3: $(python3 --version 2>&1)"
else
    echo "  ✗ python3 未安装, 请先安装 Python 3.10+"
    exit 1
fi

# ── 2. Python 分析库 ──
echo "[2/5] Python 分析库 (capstone/pyelftools/pefile)..."
pip install --quiet capstone pyelftools pefile 2>/dev/null || \
    pip3 install --quiet capstone pyelftools pefile 2>/dev/null || \
    python3 -m pip install --quiet capstone pyelftools pefile
echo "  ✓ capstone + pyelftools + pefile"

# ── 3. 反汇编/调试工具(尽力装, 缺失降级) ──
echo "[3/5] 反汇编/调试工具 (gdb/binutils/objdump)..."
for tool in gdb objdump readelf strings; do
    if command -v $tool >/dev/null 2>&1; then
        echo "  ✓ $tool: 已存在"
    else
        echo "  · $tool 缺失, 尝试安装..."
        if command -v apt-get >/dev/null 2>&1; then
            sudo apt-get install -y -qq $tool 2>/dev/null && echo "  ✓ $tool 安装成功" || echo "  · $tool 跳过(无权限/无网络)"
        elif command -v yum >/dev/null 2>&1; then
            sudo yum install -y -q $tool 2>/dev/null && echo "  ✓ $tool 安装成功" || echo "  · $tool 跳过(无权限/无网络)"
        else
            echo "  · $tool 跳过(无包管理器)"
        fi
    fi
done

# radare2/rizin(可选)
if command -v r2 >/dev/null 2>&1 || command -v rizin >/dev/null 2>&1; then
    echo "  ✓ radare2/rizin: 已存在"
else
    echo "  · radare2/rizin 未装(可选, 不影响核心工具)"
fi

# ── 4. 验证安装 ──
echo "[4/5] 验证 Python 库..."
python3 - << 'EOF'
try:
    import capstone
    print(f"  ✓ capstone {capstone.__version__}")
except ImportError:
    print("  ✗ capstone 导入失败")
    raise SystemExit(1)
try:
    from elftools.elf.elffile import ELFFile
    print("  ✓ pyelftools")
except ImportError:
    print("  ✗ pyelftools 导入失败")
    raise SystemExit(1)
try:
    import pefile
    print(f"  ✓ pefile")
except ImportError:
    print("  ✗ pefile 导入失败")
    raise SystemExit(1)
print("  全部 Python 库可用")
EOF

# ── 5. 工具自检 ──
echo "[5/5] 工具自检..."
cd "$(dirname "$0")"
if [ -f auth_locator.py ] && [ -f auth_patcher.py ] && [ -f analysis_all.py ]; then
    echo "  ✓ 核心工具齐全 (auth_locator/auth_patcher/analysis_all)"
else
    echo "  ✗ 核心工具缺失!"
    exit 1
fi
python3 -c "import sys; sys.path.insert(0,'lib'); import recon_v2, analysis_v2, llm_engine, patcher, verifier; print('  ✓ lib 模块全部可导入')"

echo ""
echo "=== 安装完成 ==="
echo "用法:"
echo "  python3 auth_locator.py <目标>          # 定位授权函数"
echo "  python3 auth_patcher.py <目标>          # 查看 patch 模式"
echo "  python3 analysis_all.py <目标>          # 统一分析"
