import datetime as dt
import time

from data.instruments import get_token
from utils.logger import log_trade


class OrderManager:

    def __init__(self, session, capital, risk_per_trade, daily_loss_limit, reward_ratio, max_hold_days, max_positions, paper):
        self.session = session
        self.capital = capital
        self.risk_per_trade = risk_per_trade
        self.daily_loss_limit = daily_loss_limit
        self.reward_ratio = reward_ratio
        self.max_hold_days = max_hold_days
        self.max_positions = max_positions
        self.paper = paper
        self.positions = {}
        self.daily_pnl = 0.0

        mode = "PAPER TRADING" if paper else "LIVE TRADING — REAL MONEY"
        print(f"\n{'=' * 65}")
        print(f"OrderManager  —  {mode}")
        print(f"Capital       : ₹{capital:>12,.0f}")
        print(f"Max positions : {max_positions} slots  "
              f"→ ₹{capital / max_positions:,.0f} per slot")
        print(f"Risk / trade  : {risk_per_trade * 100:.1f}%  "
              f"→ ₹{capital * risk_per_trade:,.0f} max loss per trade")
        print(f"Reward ratio  : {reward_ratio}×  "
              f"→ target = {reward_ratio}× the risk taken")
        print(f"Max hold      : {max_hold_days} calendar days")
        print(f"Daily limit   : {daily_loss_limit * 100:.1f}%  "
              f"→ ₹{capital * daily_loss_limit:,.0f} stops trading today")
        print(f"{'=' * 65}\n")

    @property
    def available_slots(self):
        return self.max_positions - len(self.positions)

    def exit_trade(self, symbol, exit_price, reason="MANUAL"):
        if symbol not in self.positions:
            print(f"{symbol} not in open positions")
            return

        position = self.positions[symbol]
        exit_side = 'SELL' if position['side'] == 'BUY' else 'BUY'
        qty = position['qty']

        try:
            token, trading_symbol = get_token(symbol)
        except Exception as ex:
            print(f"{symbol} — token lookup failed: {ex}")
            return

        self._place_order(symbol, trading_symbol, token, qty, exit_side)

        # Calculate P&L
        if position['side'] == 'BUY':
            pnl = (exit_price - position['entry_price']) * qty
        else:
            pnl = (position['entry_price'] - exit_price) * qty

        self.daily_pnl += pnl
        del self.positions[symbol]

        result = "PROFIT" if pnl >= 0 else "LOSS"
        print(f"Exit   ₹{exit_price:>9.2f}  "
              f"P&L ₹{pnl:>+10,.0f}  "
              f"[{reason}]  [{result}]")
        print(f"Session P&L: ₹{self.daily_pnl:>+,.0f}  "
              f"Slots now free: {self.available_slots}/{self.max_positions}")
        log_trade("EXIT", symbol, exit_side, qty, exit_price, None, pnl, reason)

    def check_exits(self, symbol, latest_row, signal_score=None):
        if symbol not in self.positions:
            return

        position = self.positions[symbol]
        side = position['side']
        stop = position['stop_price']
        target = position['target_price']
        high = latest_row['high']
        low = latest_row['low']
        close = latest_row['close']

        # Priority 1: Check stop loss
        if side == "BUY" and low < stop:
            print(f"\nStop-loss: {symbol}  "
                  f"Low {low:.2f} < Stop {stop:.2f}")
            self.exit_trade(symbol, stop, reason="STOP_LOSS")
            return

        if side == "SELL" and high > stop:
            print(f"\nStop-loss: {symbol}  "
                  f"High {high:.2f} > Stop {stop:.2f}")
            self.exit_trade(symbol, stop, reason="STOP_LOSS")
            return

        # Priority 2: Take profit
        if side == "BUY" and high >= target:
            print(f"\nTake-profit: {symbol}  "
                  f"High {high:.2f} ≥ Target {target:.2f}")
            self.exit_trade(symbol, target, reason="TAKE_PROFIT")
            return

        if side == "SELL" and low <= target:
            print(f"\nTake-profit: {symbol}  "
                  f"Low {low:.2f} ≤ Target {target:.2f}")
            self.exit_trade(symbol, target, reason="TAKE_PROFIT")
            return

        # Priority 3: Signal reversal
        # Exit a long when the signal engine turns bearish (score ≤ −2)
        # Exit a short when the signal engine turns bullish (score ≥ +2)
        if signal_score is not None:
            if side == "BUY" and signal_score <= -2:
                print(f"\nSignal reversal: {symbol}  "
                      f"score {signal_score:+d}  (long → bearish signal)")
                self.exit_trade(symbol, close, reason="SIGNAL_REVERSAL")
                return

            if side == "SELL" and signal_score >= -2:
                print(f"\nSignal reversal: {symbol}  "
                      f"score {signal_score:+d}  (short → bullish signal)")
                self.exit_trade(symbol, close, reason="SIGNAL_REVERSAL")
                return

        # Priority 4: Time limit
        entry_date = dt.date.fromisoformat(str(position["entry_date"])[:10])
        days_held = (dt.date.today() - entry_date).days

        if days_held >= self.max_hold_days:
            print(f"\nTime limit: {symbol}  "
                  f"held {days_held} days ≥ max {self.max_hold_days}")
            self.exit_trade(symbol, close,
                            reason=f"TIME_LIMIT_{days_held}D")

    @property
    def daily_loss_breached(self):
        return self.daily_pnl <= -(self.capital * self.daily_loss_limit)

    def _can_trade(self):
        if self.daily_loss_breached:
            print(f"Daily loss limit reached  "
                  f"(₹{self.daily_pnl:,.0f})  —  no new trades today")
            return False

        if self.available_slots <= 0:
            print(f"All {self.max_positions} slots occupied  "
                  f"—  no new entries until a position closes")
            return False

        return True

    @property
    def slot_capital(self):
        return self.capital / self.max_positions

    @property
    def allocated_capital(self):
        return sum(pos['qty'] * pos['entry_price'] for pos in self.positions.values())

    def calculate_quantity(self, entry_price, stop_price):
        risk_budget = self.capital * self.risk_per_trade
        risk_per_share = abs(entry_price - stop_price)

        if risk_per_share == 0:
            return 1

        qty = int(risk_budget / risk_per_share)

        max_qty_slot = int(self.slot_capital / entry_price)

        free_capital = self.capital - self.allocated_capital
        max_qty_available = int(free_capital / entry_price)

        qty = min(qty, max_qty_slot, max_qty_available)
        return max(1, qty)

    def _place_order(self, symbol, trading_symbol, token, qty, transaction_type):
        tag = "[PAPER]" if self.paper else "[LIVE]"
        print(f"  {tag}  {transaction_type:4}  "
              f"{qty:>5} × {symbol} ({trading_symbol})  @ MARKET")

        if self.paper:
            return {
                "status": True,
                "orderId": f"PAPER_{symbol}_{dt.datetime.now():%H-%M-%S}",
            }

        param = {
            "variety": "NORMAL",
            "tradingsymbol": trading_symbol,
            "symboltoken": token,
            "transactiontype": transaction_type,
            "exchange": "NSE",
            "ordertype": "MARKET",
            "producttype": "DELIVERY",
            "duration": "DAY",
            "price": "0",
            "squareoff": "0",
            "stoploss": "0",
            "quantity": str(qty),
        }

        try:
            result = self.session.placeOrder(param)
            time.sleep(0.5)
            return result
        except Exception as ex:
            print(f"Order failed for {symbol}: {ex}")
            return None

    def enter_trade(self, signal_row):
        symbol = signal_row['symbol']
        signal_label = signal_row['signal_label']

        if not self._can_trade():
            return

        if symbol in self.positions:
            print(f"{symbol} already open, skipping")
            return

        is_buy = signal_label in ['STRONG BUY', 'BUY']
        is_sell = signal_label in ['STRONG SELL', 'SELL']

        if not is_buy and not is_sell:
            return

        side = 'BUY' if is_buy else 'SELL'
        entry = float(signal_row['close'])
        stop = float(signal_row['stop_long']) if is_buy else float(signal_row['stop_short'])

        if stop is None or (isinstance(stop, float) and stop != stop):
            print(f"{symbol} — stop price unavailable, skipping")
            return

        risk = abs(entry - stop)
        target = round(entry + risk * self.reward_ratio if is_buy else entry - risk * self.reward_ratio, 2)
        qty = self.calculate_quantity(entry, stop)

        try:
            token, trading_symbol = get_token(symbol)
        except Exception as ex:
            print(f"  ✗ {symbol} — token lookup failed: {ex}")
            return

        result = self._place_order(symbol, trading_symbol, token, qty, side)

        if result and result.get("status", True):
            self.positions[symbol] = {
                "qty": qty,
                "entry_price": entry,
                "stop_price": stop,
                "target_price": target,
                "side": side,
                "order_id": result.get("orderId", ""),
                "entry_date": dt.date.today().isoformat(),
            }
            print(f"Entry  ₹{entry:>9.2f}  "
                  f"Stop  ₹{stop:>9.2f}  "
                  f"Target ₹{target:>9.2f}  "
                  f"Qty {qty:>4}  "
                  f"Risk ₹{qty * risk:,.0f}")
            print(f"Slots used: {len(self.positions)}/{self.max_positions}  "
                  f"Allocated: ₹{self.allocated_capital:,.0f}")
            log_trade("ENTRY", symbol, side, qty, entry, stop)


    def print_status(self):
        print(f"\n{'=' * 70}")
        print(f"  PORTFOLIO STATUS  —  {dt.datetime.now():%Y-%m-%d %H:%M:%S}")
        print(f"{'=' * 70}")

        if not self.positions:
            print("No open positions")
        else:
            print(f"{'Symbol':<12}  {'Side':<4}  {'Qty':>5}  "
                  f"{'Entry':>9}  {'Stop':>9}  {'Target':>9}  "
                  f"{'Allocated':>12}  {'Day':>6}")
            print(f"  {'-' * 67}")
            for symbol, position in self.positions.items():
                entry_date = dt.date.fromisoformat(str(position["entry_date"])[:10])
                days = (dt.date.today() - entry_date).days
                allocated = position["qty"] * position["entry_price"]

                print(f"{symbol:<12}  {position['side']:<4}  "
                      f"{position['qty']:>5}  "
                      f"₹{position['entry_price']:>8.2f}  "
                      f"₹{position['stop_price']:>8.2f}  "
                      f"₹{position['target_price']:>8.2f}  "
                      f"₹{allocated:>11,.0f}  "
                      f"{days:>3}/{self.max_hold_days}d")

                print(f"\nSlots          : {len(self.positions)} used  /  "
                      f"{self.available_slots} free  /  {self.max_positions} total")
                print(f"Allocated      : ₹{self.allocated_capital:>12,.0f}")
                print(f"Free capital   : ₹{self.capital - self.allocated_capital:>12,.0f}")
                label = "PROFIT ✓" if self.daily_pnl >= 0 else "LOSS ✗"
                print(f"Session P&L    : ₹{self.daily_pnl:>+12,.0f}  [{label}]")
                print(f"{'=' * 70}\n")