import pyotp
from SmartApi import SmartConnect
from config.settings import API_KEY, CLIENT_ID, MPIN, TOTP_SECRET


def get_session():
    """Create and return an authenticated SmartAPI session."""
    obj  = SmartConnect(api_key=API_KEY)
    totp = pyotp.TOTP(TOTP_SECRET).now()
    data = obj.generateSession(CLIENT_ID, MPIN, totp)

    if not data["status"]:
        raise Exception(f"Login failed: {data['message']}")

    print(f"✓ Connected as: {data['data']['name']}")
    return obj