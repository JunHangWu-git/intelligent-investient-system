"""
Phase 1 数据层：定时抓 watchlist 行情 + K线，存本地 sqlite。

直接连 moomoo OpenD（不经过 Claude MCP，本机 cron 独立跑）。
跑之前确认 OpenD 在监听: ss -tln | grep 11111
用法: .venv/bin/python scripts/fetch_quotes.py
"""

import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from moomoo import OpenQuoteContext, RET_OK, SubType

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import (  # noqa: E402
    AUTYPE,
    DB_PATH,
    KLINE_TYPES,
    MAX_COUNT,
    OPEND_HOST,
    OPEND_PORT,
    WATCHLIST,
)


def init_db(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS quotes (
            code TEXT NOT NULL,
            fetched_at TEXT NOT NULL,
            data_date TEXT,
            data_time TEXT,
            last_price REAL,
            open_price REAL,
            high_price REAL,
            low_price REAL,
            prev_close_price REAL,
            volume INTEGER,
            turnover REAL,
            PRIMARY KEY (code, fetched_at)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS klines (
            code TEXT NOT NULL,
            ktype TEXT NOT NULL,
            autype TEXT NOT NULL,
            time_key TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER,
            turnover REAL,
            change_rate REAL,
            PRIMARY KEY (code, ktype, autype, time_key)
        )
    """)
    conn.commit()


def fetch_quotes(ctx, conn):
    ret, msg = ctx.subscribe(WATCHLIST, [SubType.QUOTE])
    if ret != RET_OK:
        print(f"[quote] 订阅失败: {msg}")
        return
    ret, df = ctx.get_stock_quote(WATCHLIST)
    if ret != RET_OK:
        print(f"[quote] 抓取失败: {df}")
        return
    now = datetime.now().isoformat(timespec="seconds")
    for _, row in df.iterrows():
        conn.execute(
            """INSERT OR REPLACE INTO quotes
               (code, fetched_at, data_date, data_time, last_price, open_price,
                high_price, low_price, prev_close_price, volume, turnover)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                row["code"], now, row.get("data_date"), row.get("data_time"),
                row.get("last_price"), row.get("open_price"), row.get("high_price"),
                row.get("low_price"), row.get("prev_close_price"),
                row.get("volume"), row.get("turnover"),
            ),
        )
    conn.commit()
    print(f"[quote] 抓到 {len(df)} 只，{now}")


def fetch_klines(ctx, conn):
    # 本脚本按 cron 每交易日一次的频率设计（收盘后跑）。K线接口有独立的每日
    # 拉取配额，如果以后改成盘中高频调用本脚本，要把 quote 和 kline 拆开跑，
    # kline 部分仍保持每日一次，否则会把配额提前用光。
    for code in WATCHLIST:
        for ktype in KLINE_TYPES:
            ret, df, _ = ctx.request_history_kline(
                code, ktype=ktype, autype=AUTYPE, max_count=MAX_COUNT,
            )
            if ret != RET_OK:
                print(f"[kline] {code} {ktype} 抓取失败: {df}")
                continue
            for _, row in df.iterrows():
                conn.execute(
                    """INSERT OR REPLACE INTO klines
                       (code, ktype, autype, time_key, open, high, low, close,
                        volume, turnover, change_rate)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        code, ktype, AUTYPE, row["time_key"], row["open"], row["high"],
                        row["low"], row["close"], row["volume"], row["turnover"],
                        row.get("change_rate"),
                    ),
                )
            conn.commit()
            print(f"[kline] {code} {ktype} 存了 {len(df)} 根")


def main():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

    ctx = OpenQuoteContext(host=OPEND_HOST, port=OPEND_PORT)
    try:
        conn = sqlite3.connect(DB_PATH)
        try:
            init_db(conn)
            fetch_quotes(ctx, conn)
            fetch_klines(ctx, conn)
        finally:
            conn.close()
    finally:
        ctx.close()


if __name__ == "__main__":
    main()
