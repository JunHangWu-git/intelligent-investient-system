"""Phase 1 数据层配置。参数写死在这，不做动态可调（见 AGENTS.md）。"""

# 监控股票列表（moomoo 代码格式）。BTC 暂不支持（moomoo 只读接口无 crypto 现货），跳过。
WATCHLIST = [
    "US.NVDA",
    "US.AMD",
    "US.STZ",
    "US.QQQ",
]

OPEND_HOST = "127.0.0.1"
OPEND_PORT = 11111

# K线抓取参数
KLINE_TYPES = ["K_DAY", "K_WEEK", "K_MON"]  # 日/周/月，够 Phase2 状态A判断用
AUTYPE = "qfq"  # 前复权，跟腾讯API口径一致（见 AGENTS.md 复权口径踩坑记录）
MAX_COUNT = 250  # 单次拉取根数，覆盖约1年日K

from pathlib import Path as _Path

# 锚定项目根目录，不管从哪个目录跑脚本，db 路径都一样。
DB_PATH = str(_Path(__file__).resolve().parent.parent / "data" / "quotes.db")
