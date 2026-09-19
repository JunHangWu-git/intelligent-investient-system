#!/bin/bash
# 后台启动 moomoo OpenD（CLI版），不占终端。
# 前提：至少交互登录过一次并选了 "记住密码"（login_by_remember），
# 否则 console=0 后台模式拿不到密码输入，会启动失败。
set -e

OPEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/moomoo_OpenD_10.11.7108_Ubuntu18.04/moomoo_OpenD_10.11.7108_Ubuntu18.04"
LOGIN_ACCOUNT="77109680"
LOG_FILE="$OPEND_DIR/opend.log"

if ss -tln 2>/dev/null | grep -q ':11111 '; then
    echo "OpenD 已经在跑了（端口11111被占用），不重复启动"
    exit 0
fi

cd "$OPEND_DIR"
nohup ./OpenD login_account="$LOGIN_ACCOUNT" login_by_remember=1 console=0 > "$LOG_FILE" 2>&1 &
disown

sleep 2
if ss -tln 2>/dev/null | grep -q ':11111 '; then
    echo "OpenD 启动成功，监听 127.0.0.1:11111，日志: $LOG_FILE"
else
    echo "OpenD 启动失败，看日志: $LOG_FILE"
    tail -20 "$LOG_FILE"
    exit 1
fi
