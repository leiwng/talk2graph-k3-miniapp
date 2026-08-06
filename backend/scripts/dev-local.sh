#!/usr/bin/env bash
# 本机开发启动后端（macOS + Homebrew）。
# PNG 导出依赖 cairosvg -> cairo 动态库；brew 已装 cairo，但 uv 装的 Python
# 默认不搜 /opt/homebrew/lib，必须在进程启动前注入 DYLD_FALLBACK_LIBRARY_PATH
#（进程启动后再改 os.environ 对 dyld 无效，所以不要写进 Python 代码里）。
set -euo pipefail
cd "$(dirname "$0")/.."
export DYLD_FALLBACK_LIBRARY_PATH="/opt/homebrew/lib:${DYLD_FALLBACK_LIBRARY_PATH:-}"
exec .venv/bin/uvicorn app.main:app --port 8080 --reload
