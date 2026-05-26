import time
from pathlib import Path

from config.connect import get_session
from main import now_ist, is_market_open, load_positions, save_positions
from orders.order_manager import OrderManager

import datetime as dt

from strategy.signal_engine import get_candles

CAPITAL = 100_000
RISK_PER_TRADE = 0.02
DAILY_LOSS_LIMIT = 0.05
REWARD_RATIO = 2.0
MAX_HOLD_DAYS = 15
MAX_POSITIONS = 5
PAPER = True

LOGS_DIR         = Path(__file__).parent / "logs"

def main():
    LOGS_DIR.mkdir(exist_ok=True)

    # if not is_market_open():
        # return

    positions = load_positions()
    if not positions:
        return

    now = now_ist()
    print(f"\n[{now.strftime('%H:%M:%S')} IST]  Exit checker — "
          f"{len(positions)} open position(s): {list(positions.keys())}")

    try:
        session = get_session()
        time.sleep(2)   # let the session settle before first data call
    except Exception as ex:
        print(f"\n✗ Authentication failed: {ex}")
        print(f"Check API key, MPIN and TOTP secret in your .env file.\n")
        return

    order_manager = OrderManager(session=session,
                                 capital=CAPITAL,
                                 risk_per_trade=RISK_PER_TRADE,
                                 daily_loss_limit=DAILY_LOSS_LIMIT,
                                 reward_ratio=REWARD_RATIO,
                                 max_hold_days=MAX_HOLD_DAYS,
                                 max_positions=MAX_POSITIONS,
                                 paper=PAPER)

    order_manager.positions = positions

    today = dt.date.today()
    from_date = today.strftime("%Y-%m-%d 09:15")
    to_date = now.strftime("%Y-%m-%d %H:%M")

    for symbol in list(order_manager.positions.keys()):
        try:
            df = get_candles(session=session, symbol=symbol, interval="FIFTEEN_MINUTE", from_date=from_date, to_date=to_date)
            if df.empty:
                continue

            latest_row = df.iloc[-1]
            order_manager.check_exits(symbol=symbol, latest_row=latest_row, signal_score=None)

        except Exception as ex:
            print(f"Exit checker failed for {symbol}: {ex}")

        save_positions(order_manager.positions)

        if order_manager.daily_pnl != 0:
            print(f"Session P&L from exits this check: ₹{order_manager.daily_pnl:+,.0f}")

        print(f"Done — {len(order_manager.positions)} position(s) still open")

if __name__ == "__main__":
    main()