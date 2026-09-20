"""
Phase 2 历史回测：按 investment-system 六件套规则（状态A→开窗→绿柱日→参考价→
突破→止损/周K有效低点）跑 WATCHLIST 全历史后复权(hfq)数据，输出交易记录+统计到
data/backtest_results.md。

用法: .venv/bin/python scripts/backtest.py
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import DB_PATH, WATCHLIST  # noqa: E402
from strategy import (  # noqa: E402
    compute_reference_price,
    evaluate_windows,
    find_breakout,
    find_green_bar_day,
    macd,
    weekly_position_tracker,
)

AUTYPE = "hfq"  # 03号文档：回测/复盘用后复权


def load_rows(conn, code, ktype):
    cur = conn.execute(
        """SELECT time_key, open, high, low, close FROM klines
           WHERE code=? AND ktype=? AND autype=? ORDER BY time_key ASC""",
        (code, ktype, AUTYPE),
    )
    rows = [
        {"date": r[0][:10], "open": r[1], "high": r[2], "low": r[3], "close": r[4]}
        for r in cur.fetchall()
    ]
    closes = [r["close"] for r in rows]
    dif, dea, hist = macd(closes)
    for row, d, e, h in zip(rows, dif, dea, hist):
        row["dif"], row["dea"], row["hist"] = d, e, h
    return rows


def next_month_start(date_str):
    y, m, _ = date_str.split("-")
    y, m = int(y), int(m)
    m += 1
    if m > 12:
        m = 1
        y += 1
    return f"{y:04d}-{m:02d}-01"


def first_index_on_or_after(rows, date_str):
    for i, r in enumerate(rows):
        if r["date"] >= date_str:
            return i
    return None


def week_index_containing(weekly_rows, date_str):
    """找"包含"date_str的那一周（周K的time_key是周起始日）：取最后一个
    起始日<=date_str的周。入场若发生在周中，不能跳到下一周才开始监控止损——
    05号文档"入场→切周K"没有豁免期。
    """
    idx = None
    for i, r in enumerate(weekly_rows):
        if r["date"] <= date_str:
            idx = i
        else:
            break
    return idx


def simulate_code(code, monthly, weekly, daily):
    windows = evaluate_windows(
        [r["dif"] for r in monthly], [r["dea"] for r in monthly],
        [r["hist"] for r in monthly],
    )
    trades = []
    attempts = []
    blocked_until_date = None

    for w in windows:
        if w.close_month_index is not None:
            continue  # 次月柱变矮，窗口已关闭（03号文档第二步补充细则）

        window_month_start = monthly[w.open_month_index]["date"]
        month_start = next_month_start(window_month_start)
        if blocked_until_date is not None and month_start <= blocked_until_date:
            continue  # 老行情半路追高，不当新机会（03号文档第三步）

        # 参考价起点=开窗月首日，绿柱日起点=开窗次月首日——两者不是同一个点
        # （之前的实现把这两个起点合并成一个，会漏掉开窗月本身的高点，系统性
        # 压低参考价）。
        ref_start_idx = first_index_on_or_after(daily, window_month_start)
        start_idx = first_index_on_or_after(daily, month_start)
        if ref_start_idx is None or start_idx is None:
            continue
        # 日K数据(moomoo限2006年起)比月K/周K短，早于日K覆盖范围的开窗无法评估日K入场
        if daily[ref_start_idx]["date"][:7] != window_month_start[:7]:
            continue

        green_idx = find_green_bar_day(daily, start_idx)
        if green_idx is None:
            continue
        ref_price = compute_reference_price(daily, ref_start_idx, green_idx)
        signal = find_breakout(daily, green_idx, ref_price)
        if signal is None:
            attempts.append(
                {"code": code, "window_month": window_month_start,
                 "green_bar_day": daily[green_idx]["date"], "ref_price": ref_price,
                 "result": "数据截止时仍在等待突破"}
            )
            continue
        if not signal.valid:
            attempts.append(
                {"code": code, "window_month": window_month_start,
                 "green_bar_day": daily[green_idx]["date"], "ref_price": ref_price,
                 "result": signal.reason}
            )
            continue

        entry_date = daily[signal.entry_index]["date"]
        entry_price = ref_price
        weekly_entry_idx = week_index_containing(weekly, entry_date)
        if weekly_entry_idx is None:
            continue

        exit_date, exit_price, reason = None, None, None
        for i, stop, eff_low in weekly_position_tracker(weekly, weekly_entry_idx, entry_price):
            row = weekly[i]
            if row["low"] <= stop:
                # 跳空低开直接击穿止损线时，实际成交价是开盘价不是止损线本身
                exit_date, exit_price, reason = row["date"], min(stop, row["open"]), "止损"
                break
            if eff_low is not None and row["low"] < eff_low:
                exit_date, exit_price, reason = row["date"], min(eff_low, row["open"]), "周K有效低点跌破"
                break
        if exit_date is None:
            exit_date = weekly[-1]["date"]
            exit_price = weekly[-1]["close"]
            reason = "数据结束仍持有"

        ret_pct = (exit_price / entry_price - 1) * 100
        trades.append({
            "code": code, "entry_date": entry_date, "entry_price": entry_price,
            "exit_date": exit_date, "exit_price": exit_price, "return_pct": ret_pct,
            "reason": reason,
        })
        blocked_until_date = exit_date

    return trades, attempts


def render_report(all_trades, all_attempts):
    lines = ["# Phase 2 历史回测结果", "",
             "> 数据源：moomoo 后复权(hfq) K线，规则来自 investment-system 六件套。",
             "> 周K有效低点判定是对05号文档描述性规则的工程化实现，非机械定义，",
             "> 结果仅供参考，入场/出场机械部分（绿柱日/参考价/止损）已按文档精确实现。",
             "> 不构成投资建议。", ""]

    for code in WATCHLIST:
        trades = [t for t in all_trades if t["code"] == code]
        attempts = [a for a in all_attempts if a["code"] == code]
        lines.append(f"## {code}")
        lines.append("")
        if trades:
            lines.append("| 入场日 | 入场价 | 出场日 | 出场价 | 收益% | 出场原因 |")
            lines.append("|---|---|---|---|---|---|")
            for t in trades:
                lines.append(
                    f"| {t['entry_date']} | {t['entry_price']:.2f} | {t['exit_date']} | "
                    f"{t['exit_price']:.2f} | {t['return_pct']:+.1f}% | {t['reason']} |"
                )
            wins = [t for t in trades if t["return_pct"] > 0]
            avg_ret = sum(t["return_pct"] for t in trades) / len(trades)
            lines.append("")
            lines.append(
                f"共{len(trades)}笔，胜率{len(wins)}/{len(trades)}"
                f"({len(wins)/len(trades)*100:.0f}%)，平均单笔收益{avg_ret:+.1f}%"
            )
        else:
            lines.append("无成交记录。")
        if attempts:
            lines.append("")
            lines.append("未成交的开窗尝试：")
            for a in attempts:
                lines.append(
                    f"- {a['window_month']} 开窗，绿柱日{a['green_bar_day']}，"
                    f"参考价{a['ref_price']:.2f}：{a['result']}"
                )
        lines.append("")

    return "\n".join(lines)


def main():
    conn = sqlite3.connect(DB_PATH)
    try:
        all_trades, all_attempts = [], []
        for code in WATCHLIST:
            monthly = load_rows(conn, code, "K_MON")
            weekly = load_rows(conn, code, "K_WEEK")
            daily = load_rows(conn, code, "K_DAY")
            trades, attempts = simulate_code(code, monthly, weekly, daily)
            all_trades.extend(trades)
            all_attempts.extend(attempts)
            print(f"[backtest] {code}: {len(trades)} 笔交易, {len(attempts)} 次未成交尝试")
    finally:
        conn.close()

    report = render_report(all_trades, all_attempts)
    out_path = Path(__file__).resolve().parent.parent / "data" / "backtest_results.md"
    out_path.write_text(report, encoding="utf-8")
    print(f"[backtest] 报告写到 {out_path}")


if __name__ == "__main__":
    main()
