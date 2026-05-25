from data.fetch_historical import fetch_candles
from config.universe import get_universe
from config.universe import get_tradeable_stocks

import pandas as pd
from indicators.technical import add_all_indicators

def get_candles(session, symbol, interval, from_date, to_date):
    df = fetch_candles(session, symbol, interval, from_date, to_date)
    return df

def score_bar(row):
    score = 0

    if not pd.isna(row['ema_9']) and not pd.isna(row['ema_21']):
        if row['ema_9'] > row['ema_21']:    score += 1
        elif row['ema_9'] < row['ema_21']:  score -= 1

    if not pd.isna(row['rsi']):
        if 50 <= row['rsi'] < 70:   score += 1
        elif 30 < row['rsi'] < 50:  score -= 1

    if not pd.isna(row['macd']) and not pd.isna(row['macd_signal']):
        if row['macd'] > row['macd_signal']:    score += 1
        elif row['macd'] < row['macd_signal']:  score -= 1

    return score

def score_to_label(score):
    if score >= 3:      return 'STRONG BUY'
    elif score == 2:    return 'BUY'
    elif score == -2:   return 'SELL'
    elif score <= -3:   return 'STRONG SELL'
    else:               return 'NEUTRAL'

def add_scores(df):
    df = df.copy()
    df['signal_score'] = df.apply(score_bar, axis=1)
    df['signal_label'] = df['signal_score'].apply(score_to_label)
    return df

def generate_signals(df):
    df = add_scores(df)
    df['signal'] = 0
    df.loc[df['signal_score'] >= 3, 'signal'] = 1
    df.loc[df['signal_score'] <= -3, 'signal'] = -1
    return df


def get_latest_signal(df, symbol):
    row = df.iloc[-1]
    atr = row.get('atr', None)
    return {
        'symbol': symbol,
        'date': df.index[-1].strftime('%Y-%m-%d'),
        'close': round(row['close'], 2),
        'ema_9': round(row['ema_9'], 2),
        'ema_21': round(row['ema_21'], 2),
        'rsi': round(row['rsi'], 1),
        'macd': round(row['macd'], 2),
        'atr': round(atr, 2),
        'signal_score': int(row['signal_score']),
        'signal_label': row['signal_label'],
        'stop_long': round(row['close'] - 1.5 * atr, 2),
        'stop_short': round(row['close'] + 1.5 * atr, 2),
    }

def run_signal_engine(session, interval, from_date, to_date):
    universe = get_universe()
    print(f"\nFetching data for {len(universe)} Nifty 50 stocks ...")

    print(f"Interval : {interval}")
    print(f"Period   : {from_date}  →  {to_date}\n")

    data_dict = {}

    for symbol in universe:
        try:
            df = get_candles(session=session, symbol=symbol, interval=interval, from_date=from_date, to_date=to_date)
            df = add_all_indicators(df)
            data_dict[symbol] = df
        except Exception as ex:
            print(f"Symbol {symbol} skipped due to {ex}.")

        print(f"\nApplying filters ...")
        tradeable_stocks = get_tradeable_stocks(data_dict)
        print(f"{len(tradeable_stocks)} of {len(universe)} stocks passed filters")

        print("\nGenerating signals ...")
        summary = []
        for symbol in tradeable_stocks:
            df = generate_signals(data_dict[symbol])
            data_dict[symbol] = df
            summary.append(get_latest_signal(df, symbol))
            print(f"{symbol:12}  score={summary[-1]['signal_score']:+d} -> {summary[-1]['signal_label']}")

    summary_df = pd.DataFrame(summary)
    if not summary_df.empty:
        summary_df = summary_df.sort_values('signal_score', ascending=False)
        summary_df = summary_df.reset_index(drop=True)

    return data_dict, summary_df


if __name__ == '__main__':
    universe = get_universe()
    print(f"\nFetching data for {len(universe)} Nifty 50 stocks ...")

    interval = '1d'
    from_date = '2024-01-01'
    to_date = '2024-12-31'

    # obj = get_session()
    data, summary = run_signal_engine(universe, interval, from_date, to_date)

    # ── Full summary table ────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("  SIGNAL SUMMARY")
    print("=" * 65)
    cols = ['symbol', 'close', 'rsi', 'signal_score', 'signal_label', 'stop_long']
    print(summary[cols].to_string(index=False))

    # ── Actionable signals only ───────────────────────────────────────────────
    buys  = summary[summary['signal_label'].isin(['STRONG BUY',  'BUY'])]
    sells = summary[summary['signal_label'].isin(['STRONG SELL', 'SELL'])]

    print("\n" + "=" * 65)
    print("  ACTIONABLE SIGNALS")
    print("=" * 65)

    if not buys.empty:
        print("\n  BUY candidates:")
        for _, row in buys.iterrows():
            print(f"    {row['symbol']:12} ₹{row['close']:8.2f}  "
                  f"RSI={row['rsi']:.1f}  "
                  f"Stop=₹{row['stop_long']:.2f}  "
                  f"Score={row['signal_score']:+d}")

    if not sells.empty:
        print("\n  SELL candidates:")
        for _, row in sells.iterrows():
            print(f"    {row['symbol']:12} ₹{row['close']:8.2f}  "
                  f"RSI={row['rsi']:.1f}  "
                  f"Stop=₹{row['stop_short']:.2f}  "
                  f"Score={row['signal_score']:+d}")

    if buys.empty and sells.empty:
        print("\n  No actionable signals — all stocks neutral.")
