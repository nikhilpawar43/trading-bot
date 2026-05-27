import json
import time
import sys
from pathlib import Path
import datetime as dt
import pandas as pd

from config.connect import get_session
from data.instruments import get_token
from orders.order_manager import OrderManager
from strategy.signal_engine import run_signal_engine
from utils.telegram_notifier import notify

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Program Settings
TEST_MODE = True
CAPITAL = 100_000
RISK_PER_TRADE = 0.02
DAILY_LOSS_LIMIT = 0.05
REWARD_RATIO = 2.0
MAX_HOLD_DAYS = 15
MAX_POSITIONS = 5

PAPER = True

DATA_INTERVAL = "ONE_DAY"
LOOKBACK_DAYS = 180

BASE_DIR = Path(__file__).parent
POSITIONS_FILE = BASE_DIR / "positions.json"
LOGS_DIR = BASE_DIR / "logs"

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))

def now_ist():
    return dt.datetime.now(tz=IST)


def is_market_open():
    now = now_ist()
    if now.weekday() >= 5:
        return False
    return dt.time(9, 15) <= now.time() <= dt.time(15, 30)


def load_positions():
    if not POSITIONS_FILE.exists():
        return {}
    try:
        with open(POSITIONS_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, Exception) as ex:
        print(f"Could not load positions.json: {ex}")
        return {}

def save_positions(positions):
    try:
        LOGS_DIR.mkdir(exist_ok=True)
        with open(POSITIONS_FILE, "w") as f:
            json.dump(positions, f, indent=2)
    except (json.JSONDecodeError, Exception) as ex:
        print(f"Could not save positions.json: {ex}")

def renew_stop_orders(order_manager, data_dict=None):
    if not order_manager.positions:
        return

    print(f"\n── Renewing stop orders for "
          f"{len(order_manager.positions)} position(s) ──")

    for symbol in list(order_manager.positions.keys()):
        position = order_manager.positions[symbol]
        side = position['side']
        stop = position['stop_price']
        qty = position['qty']

        if data_dict and symbol in data_dict:
            last = data_dict[symbol].iloc[-1]
            high = float(last["high"])
            low = float(last["low"])

            if side == "BUY" and low < stop:
                print(f"{symbol} — overnight low {low:.2f} "
                      f"< stop {stop:.2f} — exiting")
                order_manager.exit_trade(symbol, stop, reason="STOP_LOSS_OVERNIGHT")
                continue

            if side == "SELL" and high > stop:
                print(f"{symbol} — overnight high {high:.2f} "
                      f"> stop {stop:.2f} — exiting")
                order_manager.exit_trade(symbol, stop, reason="STOP_LOSS_OVERNIGHT")
                continue
        try:
            token, trading_symbol = get_token(symbol)
        except Exception as ex:
            print(f"{symbol} — token lookup failed: {ex}")
            continue

        stop_direction = "SELL" if side == "BUY" else "BUY"
        stop_result = order_manager._place_stop_order(symbol, trading_symbol, token, qty, stop, stop_direction)

        if stop_result and stop_result.get("status", True):
            order_manager.positions[symbol]["stop_order_id"] = \
                stop_result.get("orderId", "")
            print(f"{symbol} — stop order renewed at ₹{stop:.2f}")
        else:
            print(f"{symbol} — stop order renewal failed, "
                  f"exit_checker will monitor manually")

        time.sleep(1)

def main():
    LOGS_DIR.mkdir(exist_ok=True)
    now = now_ist()

    print(f"\n{'=' * 70}")
    print(f"TRADING BOT")
    print(f"{now.strftime('%A, %d %b %Y  %H:%M:%S IST')}")
    print(f"Mode: {'PAPER TRADING' if PAPER else 'LIVE TRADING'}")
    print(f"Capital: ₹{CAPITAL:,.0f}  |  "
          f"Max positions: {MAX_POSITIONS}  |  "
          f"Per slot: ₹{CAPITAL / MAX_POSITIONS:,.0f}")
    print(f"{'=' * 70}")

    # 1) Market hours check
    if not TEST_MODE and not is_market_open():
        print(f"\nMarket closed at {now.strftime('%H:%M')} IST")
        print(f"Trading hours: 09:15 – 15:30 IST, Monday – Friday")
        print(f"Schedule this script with cron to run at 09:30 IST on weekdays.\n")
        return

    # 2) Authenticate with the broker
    print(f"\n── Step 1: Authenticating ──")
    try:
        session = get_session()
        time.sleep(2)  # let the session settle before first data call
    except Exception as ex:
        print(f"\n✗ Authentication failed: {ex}")
        print(f"Check API key, MPIN and TOTP secret in your .env file.\n")
        return

    # 3) Initialize OrderManager and restore open positions
    print(f"\n── Step 2: Initialising order manager ──")
    order_manager = OrderManager(session=session,
                                 capital=CAPITAL,
                                 risk_per_trade=RISK_PER_TRADE,
                                 daily_loss_limit=DAILY_LOSS_LIMIT,
                                 reward_ratio=REWARD_RATIO,
                                 max_hold_days=MAX_HOLD_DAYS,
                                 max_positions=MAX_POSITIONS,
                                 paper=PAPER)

    order_manager.positions = load_positions()

    notify(f"<b>Bot started</b> — {now.strftime('%d %b %Y %H:%M')} IST\n"
           f"Slots: {len(order_manager.positions)}/{MAX_POSITIONS} used")

    if order_manager.positions:
        print(f"Restored {len(order_manager.positions)} open position(s): "
              f"{list(order_manager.positions.keys())}")
    else:
        print(f"No existing positions — starting fresh")

    print(f"Slots: {len(order_manager.positions)} used  /  "
          f"{order_manager.available_slots} free  /  {MAX_POSITIONS} total")

    # 4) Run signal engine
    print(f"\n── Step 3: Running signal engine ──")
    today = dt.date.today()
    from_date = (today - dt.timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d 09:15")
    to_date = today.strftime("%Y-%m-%d 15:30")

    try:
        data, summary = run_signal_engine(session=session, interval=DATA_INTERVAL, from_date=from_date, to_date=to_date)
        renew_stop_orders(order_manager, data_dict=data)
        save_positions(order_manager.positions)
    except Exception as ex:
        print(f"\nSignal engine error: {ex}")
        save_positions(order_manager.positions)
        return

    if summary.empty:
        print("\nNo data returned — exiting")
        save_positions(order_manager.positions)
        return

    # 5) Check exits for all open positions
    print(f"\n── Step 4: Checking exits for "
          f"{len(order_manager.positions)} open position(s) ──")

    if not order_manager.positions:
        print("No open positions to check")
    else:
        for symbol in list(order_manager.positions.keys()):
            if symbol not in data or data[symbol].empty:
                print(f"No fresh data for {symbol} — cannot check exits")
                continue

            latest_row = data[symbol].iloc[-1]
            score_match = summary[summary["symbol"] == symbol]
            score = (int(score_match["signal_score"].values[0]) if not score_match.empty else None)

            order_manager.check_exits(symbol=symbol, latest_row=latest_row, signal_score=score)

        # Save immediately after exits - closed positions removed from disk
        save_positions(order_manager.positions)

    # 6) Enter new positions - strongest signals fill available slots
    print(f"\n── Step 5: Processing new signals ──")
    buys = summary[summary['signal_label'].isin(['STRONG BUY', 'BUY'])]
    sells = summary[summary['signal_label'].isin(['STRONG SELL', 'SELL'])]

    print(f"Buy  signals : {len(buys)}")
    print(f"Sell signals : {len(sells)}")
    print(f"Available slots : {order_manager.available_slots} / {MAX_POSITIONS}")

    if order_manager.available_slots == 0:
        print("All slots occupied — no new entries today")
    else:
        all_signals = pd.concat([buys, sells], ignore_index=True)
        all_signals = all_signals.sort_values('signal_score', ascending=False, key=abs).reset_index(drop=True)

        candidates = all_signals.head(order_manager.available_slots)
        skipped = all_signals.tail(len(all_signals) - len(candidates))

        print(f"\nEntering top {len(candidates)} signal(s) "
              f"(of {len(all_signals)} total):")

        for _, row in candidates.iterrows():
            order_manager.enter_trade(row)

        if not skipped.empty:
            print(f"\nSkipped {len(skipped)} signal(s) — no slots left:")
            for _, row in skipped.iterrows():
                print(f"{row['symbol']:12}  "
                      f"score {row['signal_score']:+d}  "
                      f"→ {row['signal_label']}")

        # Save after entries — new positions written to disk
        save_positions(order_manager.positions)

    # 7) Final status and summary
    order_manager.print_status()

    print(f"  Run complete   : {now_ist().strftime('%H:%M:%S')} IST")
    print(f"  Positions file : {POSITIONS_FILE.resolve()}")
    print(f"  Trade journal  : {LOGS_DIR / 'trade_journal.csv'}")
    print(f"  Bot log        : {LOGS_DIR / 'bot.log'}")
    print(f"{'=' * 70}\n")


if __name__ == '__main__':
    main()