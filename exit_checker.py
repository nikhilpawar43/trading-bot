import time
from pathlib import Path

from config.connect import get_session
from main import now_ist, load_positions, save_positions
from orders.order_manager import OrderManager
from config.market_calendar import is_market_open

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

def get_order_status(session, order_id):
    """
        Check the status of a specific order in AngelOne's order book.

        Returns:
            "complete"   — order was executed (stop was triggered)
            "open"       — order is still active
            "cancelled"  — order was cancelled or expired
            "paper"      — paper mode, skip check
            "unknown"    — could not retrieve status
        """
    if not order_id:
        return "unknown"

    if order_id.startswith("PAPER_"):
        return "paper"  # paper mode — no real orders to check

    try:
        order_book = session.orderBook()
        if not order_book.get("status") or not order_book.get("data"):
            return "unknown"

        for order in order_book["data"]:
            if order.get("orderid") == order_id:
                return order.get("status", "unknown").lower()

    except Exception as ex:
        print(f"Could not fetch order book: {ex}")

    return "unknown"

def main():
    LOGS_DIR.mkdir(exist_ok=True)

    if not is_market_open():
        return

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

    # ── Check if any stop orders were triggered ───────────────────────────────
    changed = False

    for symbol in list(order_manager.positions.keys()):
        position = order_manager.positions[symbol]
        stop_order_id = position.get('stop_order_id', "")

        order_status = get_order_status(session, stop_order_id)
        print(f"{symbol:12} stop order status: {order_status}")

        if order_status == "complete":
            # Stop was triggered — AngelOne already exited the position
            # Update our records to reflect this
            print(f"{symbol} — stop order was triggered, "
                  f"position closed by AngelOne")
            order_manager.exit_trade(symbol=symbol, exit_price=position['stop_price'], reason="STOP_LOSS_BROKER", place_order=False)
            changed = True

        elif order_status in ("cancelled", "rejected"):
            # Stop order expired or was rejected — fall back to price monitoring
            print(f"{symbol} — stop order {order_status}, "
                  f"monitoring price manually as fallback ...")

            # Fetch latest price and check manually
            today = dt.date.today()
            from_date = today.strftime("%Y-%m-%d 09:15")
            to_date = now.strftime("%Y-%m-%d %H:%M")

            try:
                df = get_candles(session=session, symbol=symbol, interval="FIFTEEN_MINUTE", from_date=from_date, to_date=to_date)
                if df.empty:
                    continue

                latest_row = df.iloc[-1]
                order_manager.check_exits(symbol=symbol, latest_row=latest_row, signal_score=None)
                changed = True
            except Exception as ex:
                print(f"Manual check failed for {symbol}: {ex}")

        time.sleep(1)  # rate limit between order book calls

        if changed:
            save_positions(order_manager.positions)

        if order_manager.daily_pnl != 0:
            print(f"Session P&L from exits this check: ₹{order_manager.daily_pnl:+,.0f}")

        print(f"Done — {len(order_manager.positions)} position(s) still open")

if __name__ == "__main__":
    main()