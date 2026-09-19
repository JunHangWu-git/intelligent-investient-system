#!/bin/bash
# 停止后台跑着的 moomoo OpenD。
PID=$(pgrep -f "\./OpenD login_account=" || true)
if [ -z "$PID" ]; then
    echo "没找到在跑的 OpenD 进程"
    exit 0
fi
kill "$PID"
echo "已发送停止信号给 OpenD (pid $PID)"
