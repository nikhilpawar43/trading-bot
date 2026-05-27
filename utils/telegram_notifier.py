import os
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN   = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def notify(message):
    """
    Send a message to your Telegram bot.
    Call this from main.py and exit_checker.py for key events.
    Fails silently if Telegram is unavailable.
    """
    if not TOKEN or not CHAT_ID:
        return   # Telegram not configured — skip silently

    url  = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {
        "chat_id":    CHAT_ID,
        "text":       message,
        "parse_mode": "HTML",
    }
    try:
        requests.post(url, data=data, timeout=5)
    except Exception:
        pass   # never let Telegram failure crash the trading bot

