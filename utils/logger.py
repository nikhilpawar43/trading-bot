# =============================================================================
# Centralised logging for the trading bot.
# Writes three CSV files to the logs/ directory:
#
#   trade_journal.csv  — every entry and exit with P&L
#   signal_log.csv     — every signal scored by the signal engine each day
#   daily_summary.csv  — one end-of-day snapshot per trading session
#
# All files are append-only. Headers are written only on first creation.
# =============================================================================

import csv
import datetime as dt
from pathlib import Path

# All logs go into the logs/ folder at the project root
LOGS_DIR      = Path(__file__).resolve().parent.parent / "logs"
TRADE_JOURNAL = LOGS_DIR / "trade_journal.csv"
SIGNAL_LOG    = LOGS_DIR / "signal_log.csv"
DAILY_SUMMARY = LOGS_DIR / "daily_summary.csv"

def _ensure_logs_dir():
    """Create the logs/ directory if it does not exist."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

def _append_row(filepath, headers, row):
    """
    Append one row to a CSV file.
    Writes the header line automatically if the file is new.
    """
    _ensure_logs_dir()
    file_exists = filepath.exists()

    with open(filepath, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(headers)
        writer.writerow(row)

TRADE_HEADERS = ["datetime", "action", "symbol", "side", "qty", "price", "stop", "pnl", "reason", "hold_days"]

def log_trade(action, symbol, side, qty, price, stop=None, pnl=None, reason=None, hold_days=None):
    _append_row(TRADE_JOURNAL, TRADE_HEADERS, [
        dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        action,
        symbol,
        side,
        qty,
        round(float(price), 2),
        round(float(stop), 2) if stop is not None else "",
        round(float(pnl), 2) if pnl is not None else "",
        reason or "",
        hold_days or "",
    ])

SIGNAL_HEADERS = ["date", "symbol", "close", "ema_9", "ema_21", "rsi", "macd", "macd_signal", "atr", "signal_score", "signal_label", "entered"]
def log_signals(summary_df, data_dict, entered_symbols):
    """
    Log today's signal scores for every stock that was evaluated.

    Parameters
    ----------
    summary_df      : DataFrame from run_signal_engine() — one row per stock
    data_dict       : {symbol: DataFrame} from run_signal_engine()
    entered_symbols : list of symbols where enter_trade() was actually called
    """
    today = dt.date.today().isoformat()

    for _, row in summary_df.iterrows():
        symbol = row["symbol"]
        df     = data_dict.get(symbol)

        # Pull indicator values from the last candle if available
        if df is not None and not df.empty:
            last = df.iloc[-1]
            ema9  = round(last.get("ema_9",         float("nan")), 2)
            ema21 = round(last.get("ema_21",        float("nan")), 2)
            rsi   = round(last.get("rsi",           float("nan")), 1)
            macd  = round(last.get("macd",          float("nan")), 3)
            msig  = round(last.get("macd_signal",   float("nan")), 3)
            atr   = round(last.get("atr",           float("nan")), 2)
        else:
            ema9 = ema21 = rsi = macd = msig = atr = ""

        # Determine if this signal was acted on
        if symbol in entered_symbols:
            entered = "Yes"
        elif row["signal_label"] in ("STRONG BUY", "BUY",
                                     "STRONG SELL", "SELL"):
            entered = "No slot"    # signal fired but no slot available
        else:
            entered = "No"        # neutral — not entered by design

        _append_row(SIGNAL_LOG, SIGNAL_HEADERS, [
            today,
            symbol,
            round(float(row["close"]), 2),
            ema9, ema21, rsi, macd, msig, atr,
            row["signal_score"],
            row["signal_label"],
            entered,
        ])

SUMMARY_HEADERS = ["date", "open_positions", "positions_list", "session_pnl", "capital", "allocated", "free", "slots_used", "slots_free", "slots_total"]
def log_daily_summary(manager):
    """
    Log an end-of-day portfolio snapshot to daily_summary.csv.

    Parameters
    ----------
    manager : OrderManager instance (reads positions, pnl, capital etc.)
    """
    pos_list  = "|".join(manager.positions.keys()) if manager.positions else ""
    allocated = manager.allocated_capital
    free      = manager.capital - allocated

    _append_row(DAILY_SUMMARY, SUMMARY_HEADERS, [
        dt.date.today().isoformat(),
        len(manager.positions),
        pos_list,
        round(manager.daily_pnl, 2),
        manager.capital,
        round(allocated, 2),
        round(free, 2),
        len(manager.positions),
        manager.available_slots,
        manager.max_positions,
    ])

def print_trade_summary():
    """
    Print a performance summary from trade_journal.csv.
    Run this manually: python3 -c "from utils.logger import print_trade_summary; print_trade_summary()"
    """
    import csv

    if not TRADE_JOURNAL.exists():
        print("No trade journal found — no trades logged yet.")
        return

    exits = []
    with open(TRADE_JOURNAL, "r") as f:
        for row in csv.DictReader(f):
            if row["action"] == "EXIT" and row["pnl"]:
                exits.append(float(row["pnl"]))

    if not exits:
        print("No closed trades yet.")
        return

    wins   = [p for p in exits if p > 0]
    losses = [p for p in exits if p < 0]
    total  = sum(exits)

    print(f"\n{'='*50}")
    print(f"  TRADE PERFORMANCE SUMMARY")
    print(f"{'='*50}")
    print(f"  Total trades     : {len(exits)}")
    print(f"  Wins             : {len(wins)}")
    print(f"  Losses           : {len(losses)}")
    print(f"  Win rate         : {len(wins)/len(exits)*100:.1f}%")
    print(f"  Total P&L        : ₹{total:+,.2f}")
    print(f"  Avg win          : ₹{sum(wins)/len(wins):+,.2f}" if wins   else "  Avg win         : —")
    print(f"  Avg loss         : ₹{sum(losses)/len(losses):+,.2f}" if losses else "  Avg loss        : —")
    if wins and losses:
        print(f"  Reward/risk      : {abs(sum(wins)/len(wins)) / abs(sum(losses)/len(losses)):.2f}×")

    # Exit reason breakdown
    reasons = {}
    with open(TRADE_JOURNAL, "r") as f:
        for row in csv.DictReader(f):
            if row["action"] == "EXIT":
                r = row["reason"].split("_")[0] + ("_" + row["reason"].split("_")[1] if "_" in row["reason"] else "")
                reasons[r] = reasons.get(r, 0) + 1

    print(f"\n  Exit reason breakdown:")
    for reason, count in sorted(reasons.items(), key=lambda x: -x[1]):
        print(f"    {reason:<25} {count:>3} trades")
    print(f"{'='*50}\n")


def print_signal_accuracy():
    """
    Show how often each signal label (STRONG BUY, BUY etc.) was actually entered.
    Helps tune signal thresholds.
    Run: python3 -c "from utils.logger import print_signal_accuracy; print_signal_accuracy()"
    """
    if not SIGNAL_LOG.exists():
        print("No signal log found.")
        return

    from collections import defaultdict
    counts = defaultdict(lambda: {"total": 0, "entered": 0, "no_slot": 0})

    with open(SIGNAL_LOG, "r") as f:
        for row in csv.DictReader(f):
            label = row["signal_label"]
            counts[label]["total"] += 1
            if row["entered"] == "Yes":
                counts[label]["entered"] += 1
            if row["entered"] == "No slot":
                counts[label]["no_slot"] += 1

    print(f"\n{'='*60}")
    print(f"  SIGNAL FREQUENCY & ENTRY RATE")
    print(f"{'='*60}")
    print(f"  {'Label':<14} {'Total':>7} {'Entered':>9} {'No slot':>9} {'Entry%':>8}")
    print(f"  {'-'*57}")
    order = ["STRONG BUY","BUY","NEUTRAL","SELL","STRONG SELL"]
    for label in order:
        if label in counts:
            d = counts[label]
            pct = d["entered"] / d["total"] * 100 if d["total"] else 0
            print(f"  {label:<14} {d['total']:>7} {d['entered']:>9} "
                  f"{d['no_slot']:>9} {pct:>7.1f}%")
    print(f"{'='*60}\n")