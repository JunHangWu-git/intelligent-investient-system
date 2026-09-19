#!/bin/bash
# cron 入口：确保 OpenD 在跑，再执行 fetch_quotes.py。日志落 logs/fetch.log。
# 日志重定向写脚本自己身上（exec 换 stdout/stderr），不管谁调用它（cron、手动跑）
# 都会记日志，不依赖调用方在外面加 >> logs/fetch.log。
set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

mkdir -p logs
exec >> "$PROJECT_DIR/logs/fetch.log" 2>&1
echo "===== $(date -Iseconds) ====="

"$PROJECT_DIR/scripts/start_opend.sh"
sleep 3  # OpenD 刚启动/已在跑都留点时间稳定连接

"$PROJECT_DIR/.venv/bin/python" "$PROJECT_DIR/scripts/fetch_quotes.py"
