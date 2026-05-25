import pandas as pd

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

def get_universe():
    return NIFTY_50.copy()

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