"""
Phase 3 事实层：给一只标的吐出 strategy.py 算出来的全部机械事实(JSON)，给实盘
信号agent(headless claude -p)当工具调用——agent自己判断"行情段自查"/"周K有效
低点"这两处没有机械定义的地方、以及怎么组织成人话，机械数字(状态A/开窗/绿柱日/
参考价/止损线)一律信这里输出的，不许agent自己重新推理这些数字。

用法: .venv/bin/python scripts/signal_facts.py US.NVDA
输出: JSON 到 stdout

现状判断用前复权(qfq)——跟backtest.py用后复权(hfq)是两套口径，互不复用数据，
见 investment-system/03号文档"数据准备：复权口径选择"。
"""

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import DB_PATH  # noqa: E402
from strategy import (  # noqa: E402
    evaluate_windows,
    find_breakout,
    find_green_bar_day,
    compute_reference_price,
    macd,
    stop_loss_price,
    weekly_position_tracker,
)

AUTYPE = "qfq"  # 03号文档：现状判断用前复权
MONTHLY_TAIL = 40  # 给agent看的月K条数（够看最近几段状态A，不用全部321条）
DAILY_TAIL = 90
WEEKLY_TAIL = 30


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
        row["dif"], row["dea"], row["hist"] = round(d, 4), round(e, 4), round(h, 4)
    return rows


def next_month_start(date_str):
    y, m, _ = date_str.split("-")
    y, m = int(y), int(m)
    m += 1
    if m > 12:
        m, y = 1, y + 1
    return f"{y:04d}-{m:02d}-01"


def first_index_on_or_after(rows, date_str):
    for i, r in enumerate(rows):
        if r["date"] >= date_str:
            return i
    return None


def build_facts(code, positions):
    conn = sqlite3.connect(DB_PATH)
    try:
        monthly = load_rows(conn, code, "K_MON")
        weekly = load_rows(conn, code, "K_WEEK")
        daily = load_rows(conn, code, "K_DAY")
    finally:
        conn.close()

    windows = evaluate_windows(
        [r["dif"] for r in monthly], [r["dea"] for r in monthly],
        [r["hist"] for r in monthly],
    )
    # 只给最近的窗口（含仍开着的），太老的窗口对当前判断没用
    recent_windows = []
    for w in windows[-6:]:
        recent_windows.append({
            "open_month": monthly[w.open_month_index]["date"],
            "kind": w.open_kind,
            "open_hist": round(w.open_hist, 4),
            "closed": w.close_month_index is not None,
            "close_month": monthly[w.close_month_index]["date"] if w.close_month_index else None,
        })

    latest_month = monthly[-1]
    facts = {
        "code": code,
        "autype": AUTYPE,
        "as_of": daily[-1]["date"] if daily else None,
        "latest_month": {
            "date": latest_month["date"], "dif": latest_month["dif"],
            "dea": latest_month["dea"], "hist": latest_month["hist"],
        },
        "state_a_now": latest_month["dif"] >= 0 and latest_month["dea"] >= 0 and latest_month["hist"] > 0,
        "recent_windows": recent_windows,
        "monthly_tail": monthly[-MONTHLY_TAIL:],
        "weekly_tail": weekly[-WEEKLY_TAIL:],
        "daily_tail": daily[-DAILY_TAIL:],
    }

    # 只看最新一个窗口(不管开没开着)——只有"最新窗口且未关闭"才评估日K入场链。
    # 之前的实现是"从后往前找第一个未关闭窗口"，如果最新窗口已关闭但更早年份
    # 有个从未被关闭判定命中过的老窗口(次月柱没变矮，但后来一直没再触发)，会
    # 把那个陈年老窗口错认成"当前开窗中"——已实测在STZ上复现过这个问题
    # (2026-09-20，误把2023-07的老窗口当成当前信号)。窗口关闭规则本来就只看
    # "事件月次月柱变矮"这一次性判定，不代表更晚的新窗口/新状态A段没有让它
    # 事实上作废——只取最新窗口，过期的旧窗口不再纳入"能不能入场"的评估。
    open_window = windows[-1] if windows and windows[-1].close_month_index is None else None
    if open_window is not None:
        month_start = next_month_start(monthly[open_window.open_month_index]["date"])
        ref_start_idx = first_index_on_or_after(daily, monthly[open_window.open_month_index]["date"])
        start_idx = first_index_on_or_after(daily, month_start)
        entry_chain = {"window_open_month": monthly[open_window.open_month_index]["date"]}
        if ref_start_idx is not None and start_idx is not None:
            green_idx = find_green_bar_day(daily, start_idx)
            if green_idx is not None:
                ref_price = compute_reference_price(daily, ref_start_idx, green_idx)
                signal = find_breakout(daily, green_idx, ref_price)
                entry_chain.update({
                    "green_bar_day": daily[green_idx]["date"],
                    "reference_price": round(ref_price, 4),
                    "breakout": None if signal is None else {
                        "date": daily[signal.entry_index]["date"],
                        "valid": signal.valid,
                        "reason": signal.reason,
                    },
                })
            else:
                entry_chain["green_bar_day"] = None
        facts["open_window_entry_chain"] = entry_chain
    else:
        facts["open_window_entry_chain"] = None

    # 已持仓：算到今天为止的止损线+有效低点轨迹，供agent核对
    pos = positions.get(code)
    if pos is not None:
        weekly_entry_idx = None
        for i, r in enumerate(weekly):
            if r["date"] <= pos["entry_date"]:
                weekly_entry_idx = i
            else:
                break
        trace = []
        latest_stop, latest_eff_low = None, None
        if weekly_entry_idx is not None:
            for i, stop, eff_low in weekly_position_tracker(weekly, weekly_entry_idx, pos["entry_price"]):
                trace.append({
                    "date": weekly[i]["date"], "low": weekly[i]["low"], "high": weekly[i]["high"],
                    "hist": weekly[i]["hist"], "stop": round(stop, 4),
                    "effective_low": None if eff_low is None else round(eff_low, 4),
                })
                latest_stop, latest_eff_low = stop, eff_low
        facts["position"] = {
            "entry_date": pos["entry_date"], "entry_price": pos["entry_price"],
            "current_stop_loss": None if latest_stop is None else round(latest_stop, 4),
            "current_effective_low": None if latest_eff_low is None else round(latest_eff_low, 4),
            "weekly_trace_since_entry": trace[-WEEKLY_TAIL:],
        }
    else:
        facts["position"] = None

    return facts


def main():
    if len(sys.argv) != 2:
        print("用法: signal_facts.py <code>", file=sys.stderr)
        sys.exit(1)
    code = sys.argv[1]

    positions_path = Path(__file__).resolve().parent.parent / "positions.json"
    positions = json.loads(positions_path.read_text(encoding="utf-8")) if positions_path.exists() else {}

    facts = build_facts(code, positions)
    print(json.dumps(facts, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
