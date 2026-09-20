"""
Phase 2 一次性历史回补：拉 WATCHLIST 全部可用历史K线（日/周/月 x 前复权/后复权），
存进 data/quotes.db 的 klines 表（与 Phase 1 fetch_quotes.py 共用同一张表，
主键 code+ktype+autype+time_key 天然不冲突）。

只跑一次（或数据缺口变大时重跑，INSERT OR REPLACE 幂等）。日常增量抓取仍用
fetch_quotes.py（cron），不要把本脚本接进 cron。

用法: .venv/bin/python scripts/backfill_klines.py
"""

import sqlite3
import sys
import time
from datetime import date
from pathlib import Path

from moomoo import AuType, OpenQuoteContext, RET_OK

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import DB_PATH, KLINE_TYPES, WATCHLIST  # noqa: E402
from fetch_quotes import init_db  # noqa: E402

# 拉全部可用历史：起点设够早（moomoo 有多少给多少，早于上市日会被服务端截断）。
# 注意：start给了、end不给的话，moomoo默认end=start+365天（不是"到今天"），
# 所以end必须显式传今天，否则分页只会在一年窗口里转，拉不到近期数据。
BACKFILL_START = "2000-01-01"
PAGE_MAX_COUNT = 1000
MAX_PAGES = 200  # 防 page_req_key 不推进时死循环（正常情况几十年数据也就几页）
REQUEST_INTERVAL_SEC = 1.0  # 每次历史K线请求之间的间隔，含首次请求前
AUTYPES = [AuType.QFQ, AuType.HFQ]


def backfill_one(ctx, conn, code, ktype, autype):
    """拉全量历史并写库。中途任何一页失败或分页不收敛都直接抛异常——回补是
    一次性脚本，宁可整体失败重跑（INSERT OR REPLACE幂等），也不要把失败静默
    截断成一段看起来正常、实际残缺的历史留在库里。
    """
    page_req_key = None
    total = 0
    pages = 0
    end = date.today().isoformat()
    while True:
        time.sleep(REQUEST_INTERVAL_SEC)
        ret, df, page_req_key = ctx.request_history_kline(
            code,
            start=BACKFILL_START,
            end=end,
            ktype=ktype,
            autype=autype,
            max_count=PAGE_MAX_COUNT,
            page_req_key=page_req_key,
        )
        if ret != RET_OK:
            raise RuntimeError(
                f"{code} {ktype} {autype} 第{pages + 1}页失败，已写入{total}根"
                f"（数据不完整，需重跑）: {df}"
            )
        for _, row in df.iterrows():
            conn.execute(
                """INSERT OR REPLACE INTO klines
                   (code, ktype, autype, time_key, open, high, low, close,
                    volume, turnover, change_rate)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    code, ktype, autype, row["time_key"], row["open"], row["high"],
                    row["low"], row["close"], row["volume"], row["turnover"],
                    row.get("change_rate"),
                ),
            )
        conn.commit()
        total += len(df)
        pages += 1
        if page_req_key is None:
            break
        if pages > MAX_PAGES:
            raise RuntimeError(f"{code} {ktype} {autype} 分页超过{MAX_PAGES}页，疑似page_req_key不推进")
    print(f"[backfill] {code} {ktype} {autype} 共 {total} 根")
    return total


def main():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    ctx = OpenQuoteContext(host="127.0.0.1", port=11111)
    try:
        conn = sqlite3.connect(DB_PATH)
        try:
            init_db(conn)
            for code in WATCHLIST:
                for ktype in KLINE_TYPES:
                    for autype in AUTYPES:
                        backfill_one(ctx, conn, code, ktype, autype)
        finally:
            conn.close()
    finally:
        ctx.close()


if __name__ == "__main__":
    main()
