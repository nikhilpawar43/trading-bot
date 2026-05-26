import time
import pandas as pd
from config.connect import get_session
from data.instruments import get_token

# AngelOne rate limit: ~1 request per second for historical data
API_CALL_DELAY = 2.0   # seconds to wait after every getCandleData call

def fetch_candles(obj, symbol, interval, from_date, to_date):
    """
    Fetch OHLCV candle data for a given NSE symbol.

    Parameters
    ----------
    obj       : SmartConnect session from get_session()
    symbol    : Stock name, e.g. "RELIANCE", "HDFCBANK", "INFY"
    interval  : "ONE_MINUTE" | "FIVE_MINUTE" | "ONE_HOUR" | "ONE_DAY" etc.
    from_date : "YYYY-MM-DD HH:MM"
    to_date   : "YYYY-MM-DD HH:MM"

    Returns
    -------
    pandas DataFrame with columns: open, high, low, close, volume
    Index: timestamp (datetime)
    """
    token, trading_symbol = get_token(symbol)

    params = {
        "exchange":    "NSE",
        "symboltoken": token,
        "interval":    interval,
        "fromdate":    from_date,
        "todate":      to_date,
    }

    print(f"Fetching {interval} candles for {symbol} ({trading_symbol}) ...")
    res = obj.getCandleData(params)

    # Always wait after every API call — rate limit guard
    time.sleep(API_CALL_DELAY)

    if not res["status"]:
        raise Exception(f"getCandleData failed for {symbol}: {res['message']}")

    df = pd.DataFrame(
        res["data"],
        columns=["timestamp", "open", "high", "low", "close", "volume"]
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df.set_index("timestamp", inplace=True)

    print(f"✓ {len(df)} candles fetched  "
          f"({df.index[0].date()} → {df.index[-1].date()})")
    return df


def fetch_multiple(obj, symbols, interval, from_date, to_date):
    """Fetch candles for a list of symbols. Returns dict of DataFrames."""
    result = {}
    for sym in symbols:
        try:
            result[sym] = fetch_candles(obj, sym, interval, from_date, to_date)
        except Exception as e:
            print(f"✗ Skipping {sym}: {e}")
    return result


if __name__ == "__main__":
    # ── Test: fetch daily candles for 3 Nifty 50 stocks ──────────────────────
    obj = get_session()

    symbols   = ["RELIANCE", "HDFCBANK", "INFY"]
    from_date = "2024-01-01 09:15"
    to_date   = "2024-12-31 15:30"

    data = fetch_multiple(obj, symbols, "ONE_DAY", from_date, to_date)

    for sym, df in data.items():
        print(f"\n{'='*40}")
        print(f"  {sym}")
        print(f"{'='*40}")
        print(df.tail(5).to_string())