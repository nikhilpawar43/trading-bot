# config/market_calendar.py
# =============================================================================
# NSE trading holiday calendar.
# Update NSE_HOLIDAYS every January when NSE publishes the new year's list.
# Official source: https://www.nseindia.com/resources/exchange-communication-holidays
# =============================================================================

import datetime as dt

# ── NSE trading holidays 2026 ─────────────────────────────────────────────────
# All weekday dates when NSE remains closed for equity trading.
# Holidays falling on Saturday/Sunday are excluded (market already closed).
# Source: NSE official circular + stockfeed.in/market-holidays-2026

NSE_HOLIDAYS_2026 = {
    "2026-01-15",   # Municipal Corporation Election — Maharashtra
    "2026-01-26",   # Republic Day
    "2026-03-03",   # Holi
    "2026-03-26",   # Shri Ram Navami
    "2026-03-31",   # Shri Mahavir Jayanti
    "2026-04-03",   # Good Friday
    "2026-04-14",   # Dr. Baba Saheb Ambedkar Jayanti
    "2026-05-01",   # Maharashtra Day
    "2026-05-28",   # Bakri Id
    "2026-06-26",   # Muharram
    "2026-09-14",   # Ganesh Chaturthi
    "2026-10-02",   # Mahatma Gandhi Jayanti
    "2026-10-20",   # Dussehra
    "2026-11-10",   # Diwali — Balipratipada
    "2026-11-24",   # Prakash Gurpurb Sri Guru Nanak Dev Ji
    "2026-12-25",   # Christmas
}

# ── Combine all years ─────────────────────────────────────────────────────────
# When you add NSE_HOLIDAYS_2027 next January, just add it to this set.
ALL_HOLIDAYS = NSE_HOLIDAYS_2026


def is_trading_day(date=None):
    """
    Returns True only if the given date (default today) is an NSE trading day.
    Checks three conditions:
      1. Not a Saturday or Sunday
      2. Not an NSE declared holiday
      3. Date is within a known holiday calendar year
    """
    if date is None:
        date = dt.date.today()

    # Weekends
    if date.weekday() >= 5:
        return False

    # NSE holiday
    if date.isoformat() in ALL_HOLIDAYS:
        return False

    return True


def is_market_open():
    """
    Returns True only if the market is currently open right now.
    Checks trading day AND current IST time is within 09:15–15:30.
    """
    IST     = dt.timezone(dt.timedelta(hours=5, minutes=30))
    now     = dt.datetime.now(tz=IST)
    today   = now.date()

    if not is_trading_day(today):
        return False

    market_open  = dt.time(9, 15)
    market_close = dt.time(15, 30)
    return market_open <= now.time() <= market_close


def next_trading_day(from_date=None):
    """Return the next trading day after from_date (useful for logging)."""
    if from_date is None:
        from_date = dt.date.today()

    candidate = from_date + dt.timedelta(days=1)
    while not is_trading_day(candidate):
        candidate += dt.timedelta(days=1)
    return candidate