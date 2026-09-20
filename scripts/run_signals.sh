#!/bin/bash
# cron 入口（Phase3）：收盘后 fetch_quotes.py 抓完当日数据，紧接着跑这个，用
# headless claude -p 生成 signals.md/daily_report.md。日志落 logs/signals.log。
#
# 权限说明：这是本机个人自动化，不是对外服务——跑在Nick自己的账号下，工具权限
# 跟Nick交互式session一样（继承~/.claude的全局allowlist），不是沙箱隔离。
# --permission-prompts none 的作用是防止cron里卡在一个没人能应答的权限弹窗上
# （不在allowlist里的操作直接拒绝，不是"等待批准"）。真正的安全边界是
# scripts/signals_prompt.md里写清楚的任务范围，不是靠工具权限硬隔离。
set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

mkdir -p logs
exec >> "$PROJECT_DIR/logs/signals.log" 2>&1
echo "===== $(date -Iseconds) ====="

/home/nick/.local/bin/claude -p "$(cat "$PROJECT_DIR/scripts/signals_prompt.md")" \
    --permission-prompts none \
    --output-format text

# facts_cache/：确定性地把WATCHLIST全部机械事实落盘，不经过LLM。Cowork连不到
# 本机moomoo/DB，跟Nick聊某只票时靠读这个拿新鲜机械数字，不用等signals.md。
"$PROJECT_DIR/.venv/bin/python" "$PROJECT_DIR/scripts/dump_facts_cache.py"

# Cowork是云端agent，要靠git拉这个repo才能看到更新——不push它就看不到今天的
# 信号。只commit这几个自动产出的文件，不动其他改动（比如同一天里手动改的代码），
# 避免cron意外把半成品工作也带上去。
git add signals.md daily_report.md facts_cache/
if git diff --cached --quiet; then
    echo "信号文件无变化，跳过commit"
else
    git commit -m "$(cat <<'EOF'
chore: daily signals update

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
    git push
fi
