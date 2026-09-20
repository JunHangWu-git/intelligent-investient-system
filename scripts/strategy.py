"""
Phase 2 策略层：MACD(12,26,9) + 状态A/开窗/绿柱日/参考价/突破 + 止损/周K有效低点。

纯函数实现，不碰数据库/网络，方便单测和被 backtest.py / 未来 Phase3 signals 脚本复用。
规则依据 holdle-knowledge/investment-system/ 六件套（03/05/06号文档），标注章节号
的地方是文档写死的机械规则，没标章节号的地方（周K有效低点的精确起止点）是对
文档描述性规则的工程化实现，属于合理推断，不是文档给的机械定义——用前建议先用
training-log 的实战校对方法核对几个真实案例。

MACD 公式对齐 holdle_data.py 的 calc_macd（EMA span, adjust=False 递推），
柱 = (DIF-DEA)*2，跟 moomoo/国内看盘软件显示口径一致。
"""

from dataclasses import dataclass

BAR_CREDIBLE_THRESHOLD = 0.5  # 03号文档"贴0轴"阈值
BREAKOUT_CHASE_LIMIT = 1.05  # 超参考价5%不追
BREAKOUT_EXPIRE_DAYS_MAX = 60  # 文档给50-60天区间，取上界
NEW_LISTING_MIN_MONTHS = 30

STOP_LOSS_INITIAL = 0.80  # 入场价 * 0.8
STOP_LOSS_STAGE2 = 0.90  # 涨超20% -> 入场价 * 0.9
STOP_LOSS_STAGE2_TRIGGER = 1.20
STOP_LOSS_STAGE3_BREAKEVEN = 1.00  # 涨超30% -> 保本
STOP_LOSS_STAGE3_TRIGGER = 1.30


def ema(values, span):
    """标准递推EMA，等价 pandas .ewm(span=span, adjust=False).mean()。"""
    alpha = 2 / (span + 1)
    out = []
    prev = None
    for v in values:
        prev = v if prev is None else alpha * v + (1 - alpha) * prev
        out.append(prev)
    return out


def macd(closes, fast=12, slow=26, signal=9):
    """返回 (dif, dea, hist) 三个等长列表。"""
    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)
    dif = [f - s for f, s in zip(ema_fast, ema_slow)]
    dea = ema(dif, signal)
    hist = [(d - e) * 2 for d, e in zip(dif, dea)]
    return dif, dea, hist


def is_state_a(dif, dea, hist):
    """03号文档第一步：双线≥0轴 且 柱红，两者"且"关系。"""
    return dif >= 0 and dea >= 0 and hist > 0


def _is_red(h):
    """03号文档"贴0轴不算数"：|柱|<0.5 一律按绿柱处理（不算红），只有|柱|>=0.5
    才算可信红柱。这是逐月判色，不是把贴0轴的月份从序列里剔除——holdle_get_rules
    (round f4cab17e, 2026-09-20) 明确："别因为数据是红的就说它已经红过、后面不算
    绿转红而错过"，即 红→贴0轴(按绿处理)→红 这种情况，第二个红月要算一次新的
    绿转红事件。用逐月判色天然满足这条，不需要额外的"顺延"逻辑。
    """
    return h >= BAR_CREDIBLE_THRESHOLD


@dataclass(frozen=True)
class WindowEvent:
    month_index: int  # 对应传入月K列表的下标
    kind: str  # "绿转红" | "矮转高"


def detect_window_events(hist):
    """03号文档第二步①：柱子状态变化事件（绿转红/矮转高）。
    不在这里做②③(双线/柱≤DEA)校验，校验交给 evaluate_windows。
    """
    events = []
    for i in range(1, len(hist)):
        red = _is_red(hist[i])
        prev_red = _is_red(hist[i - 1])
        if red and not prev_red:
            events.append(WindowEvent(i, "绿转红"))
        elif red and prev_red and i >= 2 and _is_red(hist[i - 2]):
            if hist[i - 1] < hist[i - 2] and hist[i] > hist[i - 1]:
                events.append(WindowEvent(i, "矮转高"))
    return events


@dataclass(frozen=True)
class Window:
    open_month_index: int
    open_kind: str
    open_hist: float
    close_month_index: int | None  # None = 仍开着（对到序列末尾未关闭）


def evaluate_windows(dif, dea, hist):
    """03号文档第二步②③ + 窗口关闭规则。
    次新股(上市不足30个月，即事件月下标<30，同时也是MACD(12,26,9)预热期)的
    事件不参与判定；否则对每个事件月校验双线≥0且柱≤DEA才算开窗，窗口在事件月
    的次月（自然月+1，不是下个红柱月）若柱变矮则立即关闭。
    """
    events = detect_window_events(hist)
    windows = []
    for ev in events:
        i = ev.month_index
        if i < NEW_LISTING_MIN_MONTHS:
            continue
        if not is_state_a(dif[i], dea[i], hist[i]):
            continue
        if not (hist[i] <= dea[i]):
            continue
        close_idx = None
        nxt = i + 1
        if nxt < len(hist) and hist[nxt] < hist[i]:
            close_idx = nxt
        windows.append(Window(i, ev.kind, hist[i], close_idx))
    return windows


def find_green_bar_day(daily_rows, start_index):
    """03号文档第四步②：从start_index起（开窗次月第一个交易日），按日期升序找
    第一个柱<0的交易日，只看符号不看幅度。daily_rows已含算好的hist字段。
    找不到就顺延到后面月份（本函数天然支持，因为daily_rows是全量日K，不按月截断）。
    """
    for i in range(start_index, len(daily_rows)):
        if daily_rows[i]["hist"] < 0:
            return i
    return None


def compute_reference_price(daily_rows, window_start_index, green_bar_index):
    """03号文档第四步③：[开窗月首日, 绿柱日] 闭区间日K最高。"""
    highs = [r["high"] for r in daily_rows[window_start_index:green_bar_index + 1]]
    return max(highs)


@dataclass(frozen=True)
class EntrySignal:
    entry_index: int
    entry_price: float
    valid: bool
    reason: str


def find_breakout(daily_rows, green_bar_index, reference_price):
    """03号文档第四步④+错过/失效规则：绿柱日后首个盘中high>参考价即突破，
    买入价按参考价记录。50-60个交易日不突破则失效（文档给区间，这里取上界60）。

    "超5%不追"判的是开盘价而非盘中high：买入价本就按参考价挂单记录，只要开盘价
    没有跳空超参考价5%，盘中冲高多少都不影响能否在参考价成交；真正追不到的是
    跳空高开。这是工程化推断（文档没写清楚判断基准是high还是open），不是
    holdle_get_rules机械定义确认过的规则。
    """
    deadline = green_bar_index + BREAKOUT_EXPIRE_DAYS_MAX
    for i in range(green_bar_index + 1, min(len(daily_rows), deadline + 1)):
        if daily_rows[i]["high"] > reference_price:
            if daily_rows[i]["open"] > reference_price * BREAKOUT_CHASE_LIMIT:
                return EntrySignal(i, reference_price, False, "开盘价已超参考价5%,不追")
            return EntrySignal(i, reference_price, True, "突破")
        if i - green_bar_index >= BREAKOUT_EXPIRE_DAYS_MAX:
            return EntrySignal(i, reference_price, False, "超60个交易日未突破,入场失效")
    return None


def stop_loss_price(entry_price, running_max_price):
    """05号文档三阶止损：单向只上不下（running_max_price需为入场后至今的最高价）。"""
    if running_max_price >= entry_price * STOP_LOSS_STAGE3_TRIGGER:
        return entry_price * STOP_LOSS_STAGE3_BREAKEVEN
    if running_max_price >= entry_price * STOP_LOSS_STAGE2_TRIGGER:
        return entry_price * STOP_LOSS_STAGE2
    return entry_price * STOP_LOSS_INITIAL


def weekly_position_tracker(weekly_rows, entry_index, entry_price):
    """05号文档持仓期管理：逐周产出(止损线, 生效中的有效低点)，供 backtest.py
    和未来 Phase3 实盘信号脚本按周推进时调用同一份规则，不重复实现。

    从入场当周（entry_index本身）开始检查，不豁免入场头几周——文档"入场→切
    换到周K→检查止损"没有豁免期。止损线用"上一周为止"的running_high计算再
    yield，本周high对running_high的抬高效果要到下一周才反映到止损线上，避免
    "本周high先把止损抬到保本、又用本周low去撞"这种单周内的前视。

    有效低点定义是工程化实现（文档只给了描述性规则，没有03号绿柱日那种机械
    定义）：新高后开始算回撤，回撤期内不管某周柱子是红是绿都跟踪最低价（只是
    绿柱触发"进入回撤"状态，回撤一旦开始就跟到结束，不会因中间某周转红而漏记
    更低的点），回撤期最低价>入场价才记为有效低点；再创新高可再上调。用前
    建议按 training-log 方法核对几个真实案例。
    """
    running_high = entry_price
    effective_low = None
    in_pullback = False
    pullback_low = None

    for i in range(entry_index, len(weekly_rows)):
        row = weekly_rows[i]
        stop = stop_loss_price(entry_price, running_high)
        yield i, stop, effective_low

        made_new_high = row["high"] > running_high
        if made_new_high:
            running_high = row["high"]
            if in_pullback and pullback_low is not None and pullback_low > entry_price:
                if effective_low is None or pullback_low > effective_low:
                    effective_low = pullback_low
            in_pullback = False
            pullback_low = None
        elif in_pullback or row["hist"] < 0:
            in_pullback = True
            pullback_low = row["low"] if pullback_low is None else min(pullback_low, row["low"])
