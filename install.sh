#!/bin/sh
# claude-usage-stat 安装脚本 —— 纯 Python,只需系统装有 python3。
# 用法: 克隆仓库后在仓库目录里运行  ./install.sh
set -e

SRC="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/.local/share/claude-usage-stat"
BINDIR="$HOME/.local/bin"
LAUNCHER="$BINDIR/claude-usage-stat"

if ! command -v python3 >/dev/null 2>&1; then
  echo "错误: 需要 Python 3。" >&2
  echo "  macOS:  xcode-select --install" >&2
  echo "  其他:   见 https://www.python.org/downloads/" >&2
  exit 1
fi

if [ ! -d "$SRC/claude_usage_stat" ]; then
  echo "错误: 当前目录找不到 claude_usage_stat/ 包,请在仓库根目录运行。" >&2
  exit 1
fi

echo "安装 claude-usage-stat ..."
mkdir -p "$DEST" "$BINDIR"
rm -rf "$DEST/claude_usage_stat"
cp -R "$SRC/claude_usage_stat" "$DEST/"

cat > "$LAUNCHER" <<EOF
#!/bin/sh
exec env PYTHONPATH="$DEST" python3 -m claude_usage_stat "\$@"
EOF
chmod +x "$LAUNCHER"

echo "✓ 已安装命令: $LAUNCHER"

# 确保 ~/.local/bin 在 PATH 中(自动写入 shell 配置)
case "$SHELL" in
  *zsh)  RC="$HOME/.zshrc" ;;
  *bash) RC="$HOME/.bash_profile" ;;
  *)     RC="$HOME/.profile" ;;
esac

if grep -qs "/.local/bin" "$RC" 2>/dev/null; then
  echo "✓ PATH 已在 $RC 配置好。重开终端即可运行:  claude-usage-stat"
else
  printf '\n# 本地安装的命令行工具\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$RC"
  echo "✓ 已把 ~/.local/bin 加入 PATH ($RC)。"
  echo "  重开终端,或运行:  source $RC"
fi

echo "卸载:  rm -rf \"$DEST\" \"$LAUNCHER\" ~/.config/claude-usage-stat"
