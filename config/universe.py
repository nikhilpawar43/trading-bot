# =============================================================================
# Defines all trading universes and sector health detection.
#
# Architecture:
#   FULL_UNIVERSE  — all stocks from all indices combined (deduplicated)
#   SECTOR_GROUPS  — which stocks belong to which sector
#   get_universe() — returns the right stock list based on mode
#   check_sector_health() — detects which sectors are currently strong
# =============================================================================

import pandas as pd

# ── Nifty 50
NIFTY_50 = [
    "ADANIENT",   "ADANIPORTS",  "APOLLOHOSP",  "ASIANPAINT",  "AXISBANK",
    "BAJAJ-AUTO", "BAJFINANCE",  "BAJAJFINSV",  "BEL",         "BHARTIARTL",
    "CIPLA",      "COALINDIA",   "DRREDDY",     "EICHERMOT",   "ETERNAL",
    "GRASIM",     "HCLTECH",     "HDFCBANK",    "HDFCLIFE",    "HINDALCO",
    "HINDUNILVR", "ICICIBANK",   "INDIGO",      "INFY",        "ITC",
    "JIOFIN",     "JSWSTEEL",    "KOTAKBANK",   "LT",          "LTIM",
    "M&M",        "MARUTI",      "MAXHEALTH",   "NESTLEIND",   "NTPC",
    "ONGC",       "POWERGRID",   "RELIANCE",    "SBILIFE",     "SBIN",
    "SHRIRAMFIN", "SUNPHARMA",   "TCS",         "TATACONSUM",  "TATAMOTORS",
    "TATASTEEL",  "TECHM",       "TITAN",       "ULTRACEMCO",  "WIPRO",
]

# ── Nifty Bank
NIFTY_BANK = [
    "AXISBANK",   "BANDHANBNK",  "FEDERALBNK",  "HDFCBANK",   "ICICIBANK",
    "IDFCFIRSTB", "INDUSINDBK",  "KOTAKBANK",   "PNB",        "SBIN",
    "AUBANK",     "BANKBARODA",
]

# ── Nifty IT
NIFTY_IT = [
    "TCS",        "INFY",        "WIPRO",       "HCLTECH",    "TECHM",
    "LTIM",       "MPHASIS",     "COFORGE",     "PERSISTENT", "OFSS",
]

# ── Nifty Pharma
NIFTY_PHARMA = [
    "SUNPHARMA",  "DRREDDY",     "CIPLA",       "DIVISLAB",   "APOLLOHOSP",
    "TORNTPHARM", "AUROPHARMA",  "LUPIN",       "ALKEM",      "IPCALAB",
    "ABBOTINDIA", "GLAXO",       "PFIZER",      "BIOCON",     "ZYDUSLIFE",
]

# ── Nifty Auto
NIFTY_AUTO = [
    "MARUTI",     "TATAMOTORS",  "BAJAJ-AUTO",  "EICHERMOT",  "M&M",
    "HEROMOTOCO", "TVSMOTOR",    "BOSCHLTD",    "BALKRISIND", "MOTHERSON",
    "EXIDEIND",   "AMARAJABAT",
]

# ── Nifty FMCG
NIFTY_FMCG = [
    "HINDUNILVR", "ITC",         "NESTLEIND",   "BRITANNIA",  "DABUR",
    "MARICO",     "COLPAL",      "GODREJCP",    "TATACONSUM", "EMAMILTD",
    "RADICO",     "UBL",
]

# ── Nifty Midcap (selected liquid stocks)
NIFTY_MIDCAP = [
    "PIIND",      "CHOLAFIN",    "MFSL",        "SAIL",       "NMDC",
    "GODREJPROP", "SUPREMEIND",  "AAPL",        "LALPATHLAB", "METROPOLIS",
    "KANSAINER",  "ASTRAL",      "LINDEINDIA",  "APLAPOLLO",  "DIXON",
    "INDIAMART",  "NAUKRI",      "POLICYBZR",   "DELHIVERY",  "ZOMATO",
]

# ── Sector grouping — used for health detection ───────────────────────────────
# Maps a sector name to the stocks that represent it.
# Stocks can appear in multiple sectors (e.g. HDFCBANK in both BANKING and NIFTY_50).
SECTOR_GROUPS = {
    "BANKING":  NIFTY_BANK,
    "IT":       NIFTY_IT,
    "PHARMA":   NIFTY_PHARMA,
    "AUTO":     NIFTY_AUTO,
    "FMCG":     NIFTY_FMCG,
}

# ── Universe modes ────────────────────────────────────────────────────────────
_ALL_STOCKS = list(dict.fromkeys(
    NIFTY_50 + NIFTY_BANK + NIFTY_IT +
    NIFTY_PHARMA + NIFTY_AUTO + NIFTY_FMCG
))   # dict.fromkeys preserves order and removes duplicates

UNIVERSE_MODES = {
    "NIFTY50":        NIFTY_50,
    "LARGE_CAP":      list(dict.fromkeys(NIFTY_50 + NIFTY_BANK + NIFTY_IT)),
    "MULTI_SECTOR":   _ALL_STOCKS,
    "PHARMA_FOCUS":   list(dict.fromkeys(NIFTY_PHARMA + NIFTY_50)),
    "BANKING_FOCUS":  list(dict.fromkeys(NIFTY_BANK + NIFTY_50)),
}



def get_universe(mode="MULTI_SECTOR"):
    """
        Return a deduplicated list of stocks for the given mode.

        Modes
        -----
        NIFTY50       : 50 stocks — conservative, lowest noise
        LARGE_CAP     : ~70 stocks — Nifty 50 + Bank + IT
        MULTI_SECTOR  : ~130 stocks — all defined sectors combined (default)
        PHARMA_FOCUS  : Nifty 50 + Pharma stocks
        BANKING_FOCUS : Nifty 50 + Banking stocks
        """
    return UNIVERSE_MODES.get(mode, _ALL_STOCKS).copy()

def check_sector_health(data_dict, bullish_threshold=0.60):
    """
    Detect which sectors are currently healthy (in uptrend) using
    the data already fetched by the signal engine — no extra API calls.

    A sector is considered healthy if more than bullish_threshold
    (default 60%) of its stocks have EMA9 > EMA21.

    Parameters
    ----------
    data_dict         : {symbol: DataFrame} from signal engine
    bullish_threshold : fraction of stocks that must be bullish (0.0 to 1.0)

    Returns
    -------
    dict : {sector_name: {"healthy": bool, "bullish_pct": float}}
    """
    results = {}

    for sector_name, stocks in SECTOR_GROUPS.items():
        bullish = 0
        total   = 0

        for sym in stocks:
            if sym not in data_dict or data_dict[sym].empty:
                continue
            last = data_dict[sym].iloc[-1]
            ema9  = last.get("ema_9",  None)
            ema21 = last.get("ema_21", None)
            if ema9 is None or ema21 is None:
                continue
            total   += 1
            if ema9 > ema21:
                bullish += 1

        if total == 0:
            results[sector_name] = {"healthy": False, "bullish_pct": 0.0}
            continue

        pct = bullish / total
        results[sector_name] = {
            "healthy":     pct >= bullish_threshold,
            "bullish_pct": round(pct * 100, 1),
        }

    return results

def filter_by_sector_health(summary_df, sector_health, data_dict):
    """
    Remove stocks from weak sectors from the signal summary.
    Stocks from Nifty 50 core are always kept (blue chips).
    Only sector-specific additions are filtered.

    Parameters
    ----------
    summary_df    : signal engine output DataFrame
    sector_health : output from check_sector_health()
    data_dict     : needed to know which sector each stock belongs to

    Returns
    -------
    Filtered summary DataFrame
    """
    # Build set of symbols to EXCLUDE (from unhealthy sectors)
    # A symbol is excluded only if it is not in Nifty 50
    # (Nifty 50 stocks are always kept as the core universe)
    exclude = set()

    for sector, health in sector_health.items():
        if not health["healthy"]:
            for sym in SECTOR_GROUPS[sector]:
                if sym not in NIFTY_50:    # don't exclude Nifty 50 stocks
                    exclude.add(sym)

    before = len(summary_df)
    filtered = summary_df[~summary_df["symbol"].isin(exclude)]
    removed  = before - len(filtered)

    if removed > 0:
        print(f"Sector filter removed {removed} stock(s) "
              f"from weak sectors")

    return filtered.reset_index(drop=True)

def get_tradeable_stocks(data_dict, min_avg_volume = 1_000_000, min_atr_pct = 0.5):
    tradeable_stocks = []

    for symbol, df in data_dict.items():
        if df.empty or len(df) < 20:
            continue

        avg_volume = df['volume'].tail(20).mean()
        if avg_volume < min_avg_volume:
            print(f"    x {symbol:12} skipped - low volume (avg {avg_volume/1e5:.1f}L < {min_avg_volume/1e5:.0f}L)")
            continue

        latest_close = df['close'].iloc[-1]
        latest_atr = df['atr'].iloc[-1]

        if pd.isna(latest_atr) or latest_close == 0:
            continue

        atr_pct = (latest_atr / latest_close) * 100
        if atr_pct < min_atr_pct:
            print(f"    x {symbol:12} skipped - low volatility (ATR {atr_pct:.2f}% < {min_atr_pct:.2f}%)")
            continue

        tradeable_stocks.append(symbol)

    return tradeable_stocks