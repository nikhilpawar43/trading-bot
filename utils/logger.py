import csv
import os
import datetime as dt

JOURNAL_FILE = 'trade_journal.csv'
HEADERS = ["datetime", "action", "symbol", "side", "qty", "price", "stop", "pnl", "reason"]

def log_trade(action, symbol, side, qty, price, stop=None, pnl=None, reason=None):
    file_exists = os.path.exists(JOURNAL_FILE)

    with open(JOURNAL_FILE, 'a', newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(HEADERS)
        writer.writerow([
            dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            action, symbol, side, qty,
            round(float(price), 2),
            round(float(stop), 2) if stop is not None else "",
            round(float(pnl), 2) if pnl is not None else "",
            reason or ""
        ])

def print_journal():
    if not os.path.exists(JOURNAL_FILE):
        print("No trades logged yet.")
        return

    with open(JOURNAL_FILE, 'r') as f:
        print(f.read())