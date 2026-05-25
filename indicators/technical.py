import pandas_ta as ta
from pandas import DataFrame
from config.connect import get_session
from data.fetch_historical import fetch_candles

def add_ema(df:DataFrame, periods= [9, 21, 50, 200]):
    for period in periods:
        df[f'ema_{period}'] = ta.ema(df['close'], length=period)
    return df

def add_rsi(df:DataFrame, period = 14):
    df['rsi'] = ta.rsi(df['close'], length=period)
    return df

def add_macd(df:DataFrame, fast=12, slow=26, signal=9):
    result = ta.macd(df['close'], fast, slow, signal)
    df['macd'] = result[f'MACD_{fast}_{slow}_{signal}']
    df['macd_signal'] = result[f'MACDs_{fast}_{slow}_{signal}']
    df['macd_hist'] = result[f'MACDh_{fast}_{slow}_{signal}']
    return df

def add_bollinger_band(df:DataFrame, period = 20, std = 2):
    result = ta.bbands(df['close'], length=period, lower_std=std, upper_std=std)
    df['bb_upper'] = result[f'BBU_{period}_{std}_{std}']
    df['bb_mid'] = result[f'BBM_{period}_{std}_{std}']
    df['bb_lower'] = result[f'BBL_{period}_{std}_{std}']
    df['bb_pct'] = result[f'BBP_{period}_{std}_{std}']
    return df

def add_atr(df:DataFrame, period = 14):
    df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=period)
    return df

def add_all_indicators(df:DataFrame, ema_period= [9, 21, 50, 200]):
    df = add_ema(df, periods=ema_period)
    df = add_rsi(df)
    df = add_macd(df)
    df = add_bollinger_band(df)
    df = add_atr(df)
    return df

def ema_crossover_signal(df:DataFrame):
    buy = (df['ema_9'] > df['ema_21']) & (df['ema_9'].shift(1) <= df['ema_21'].shift(1))
    sell = (df['ema_9'] < df['ema_21']) & (df['ema_9'].shift(1) >= df['ema_21'].shift(1))

    df['signal'] = 0
    df.loc[buy, 'signal'] = 1
    df.loc[sell, 'signal'] = -1

    return df

def rsi_signal(df:DataFrame, oversold = 30, overbought = 70):
    buy = (df['rsi'] > oversold) & (df['rsi'].shift(1) <= oversold)
    sell = (df['rsi'] < overbought) & (df['rsi'].shift(1) >= overbought)

    df['signal'] = 0
    df.loc[buy, 'signal'] = 1
    df.loc[sell, 'signal'] = -1

def macd_signal(df:DataFrame):
    buy = (df['macd'] > df['macd_signal']) & (df['macd'].shift(1) <= df['macd_signal'].shift(1))
    sell = (df['macd'] < df['macd_signal']) & (df['macd'].shift(1) >= df['macd_signal'].shift(1))

    df['signal'] = 0
    df.loc[buy, 'signal'] = 1
    df.loc[sell, 'signal'] = -1
    return df

def bbands_signal(df:DataFrame):
    buy = df['close'] <= df['bb_lower']
    sell = df['close'] >= df['bb_upper']

    df['signal'] = 0
    df.loc[buy, 'signal'] = 1
    df.loc[sell, 'signal'] = -1
    return df

def stop_loss_price(df:DataFrame, entry_price, direction, multiplier = 1.5):
    latest_atr = df['atr'].iloc[-1]
    if direction == 'long':
        return round(entry_price - (multiplier * latest_atr), 2)
    else:
        return round(entry_price + (multiplier * latest_atr), 2)

if __name__ == "__main__":
    obj = get_session()
    df = fetch_candles(obj, symbol="RELIANCE", interval="ONE_DAY", from_date="2024-01-01 09:15", to_date="2024-12-31 15:30")
    df = add_all_indicators(df)
    df = ema_crossover_signal(df)

    cols = ['close', 'ema_9', 'ema_21', 'rsi', 'macd', 'atr', 'signal']
    print("\n── Last 10 bars with indicators ──")
    print(df[cols].tail(10).round(2).to_string())

    # Summary
    buys = df[df['signal'] == 1]
    sells = df[df['signal'] == -1]
    print(f"\n── Signal summary ──")
    print(f"Buy signals  : {len(buys)}")
    print(f"Sell signals : {len(sells)}")

    entry = df['close'].iloc[-1]
    stop = stop_loss_price(df, entry, 'long')
    print(f"\n── Stop-loss example ──")
    print(f"Entry price  : ₹{entry:.2f}")
    print(f"ATR (14)     : ₹{df['atr'].iloc[-1]:.2f}")
    print(f"Stop at 1.5× : ₹{stop:.2f}")