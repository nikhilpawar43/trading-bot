import os
from dotenv import load_dotenv

load_dotenv()

# SmartAPI credentials — loaded from .env file
API_KEY     = os.getenv("API_KEY")
CLIENT_ID   = os.getenv("CLIENT_ID")
MPIN        = os.getenv("MPIN")
TOTP_SECRET = os.getenv("TOTP_SECRET")

# Trading defaults
EXCHANGE    = "NSE"