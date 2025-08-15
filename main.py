import os
import time
import requests
import logging
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone

# --------------------------
# Загрузка .env и логирование
# --------------------------
load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# --------------------------
# Переменные окружения
# --------------------------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_IDS = [c.strip() for c in os.getenv("TELEGRAM_CHAT_ID", "").split(",") if c.strip()]

if not TELEGRAM_BOT_TOKEN:
    logging.error("Не задан TELEGRAM_BOT_TOKEN в .env — бот не сможет отправлять сообщения!")
if not TELEGRAM_CHAT_IDS:
    logging.error("Не задан TELEGRAM_CHAT_ID в .env — бот не сможет отправлять сообщения!")

# Фильтры/параметры
MIN_LIQ_USD        = float(os.getenv("MIN_LIQ_USD", 5000))
MIN_VOL_5M         = float(os.getenv("MIN_VOL_5M", 3000))
MIN_BUYS_5M        = int(os.getenv("MIN_BUYS_5M", 20))
MIN_PCHANGE_5M     = float(os.getenv("MIN_PCHANGE_5M", 5))
QUOTE_PREF         = [x.strip().upper() for x in os.getenv("QUOTE_PREF", "USDC,SOL").split(",")]
NEW_MAX_AGE_MIN    = int(os.getenv("NEW_MAX_AGE_MIN", 10))
POLL_SECONDS       = int(os.getenv("POLL_SECONDS", 60))
HEARTBEAT_HOURS    = float(os.getenv("HEARTBEAT_HOURS", 2))
SELL_DROP_PCT      = float(os.getenv("SELL_DROP_PCT", 7))
TRACK_TTL_
