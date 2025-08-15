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
TRACK_TTL_HOURS    = float(os.getenv("TRACK_TTL_HOURS", 24))

API_URL = "https://api.dexscreener.com/latest/dex/search?q=solana"

seen_tokens = set()
tracked = {}
last_status_time = datetime.now(timezone.utc)

# --------------------------
# Утилиты
# --------------------------
def fmt_usd(x: float) -> str:
    try:
        if x >= 1:
            return f"{x:,.2f}$"
        return f"{x:,.6f}$"
    except Exception:
        return f"{x}$"

def send_telegram(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_IDS:
        return
    for chat_id in TELEGRAM_CHAT_IDS:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": int(chat_id) if chat_id.lstrip("-").isdigit() else chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        try:
            r = requests.post(url, json=payload, timeout=10)
            if r.status_code != 200:
                logging.error("TG error %s: %s", chat_id, r.text)
        except Exception as e:
            logging.error("TG error %s: %s", chat_id, e)

def get_pairs():
    try:
        r = requests.get(API_URL, timeout=15)
        if r.status_code == 200:
            return r.json().get("pairs", []) or []
        logging.error("DexScreener API status: %s", r.status_code)
    except Exception as e:
        logging.error("DexScreener API error: %s", e)
    return []

def eligible(token: dict) -> bool:
    try:
        liq = float(token.get("liquidity", {}).get("usd") or 0)
        vol5 = float(token.get("volume", {}).get("m5") or 0)
        buys5 = int(token.get("txns", {}).get("m5", {}).get("buys") or 0)
        age_min = int(token.get("age") or 0)
        pchg5 = float(token.get("priceChange", {}).get("m5") or 0)
        quote = (token.get("quoteToken", {}) or {}).get("symbol", "").upper()

        return (
            age_min <= NEW_MAX_AGE_MIN
            and liq >= MIN_LIQ_USD
            and vol5 >= MIN_VOL_5M
            and buys5 >= MIN_BUYS_5M
            and pchg5 >= MIN_PCHANGE_5M
            and (quote in QUOTE_PREF)
        )
    except Exception:
        return False

def build_links(token: dict):
    pair_addr = token.get("pairAddress", "")
    base = token.get("baseToken", {}) or {}
    token_addr = base.get("address", "")

    dex_link = f"https://dexscreener.com/solana/{pair_addr}" if pair_addr else ""
    phantom_link = f"https://phantom.app/ul/browse/{token_addr}" if token_addr else ""
    return dex_link, phantom_link

def now_utc():
    return datetime.now(timezone.utc)

# --------------------------
# Основная логика
# --------------------------
def main():
    global last_status_time

    logging.info("🚀 Бот запущен. Ожидание сигналов...")
    send_telegram("🤖 Бот запущен! Жду новые монеты по Solana…")

    while True:
        try:
            start_ts = time.monotonic()
            pairs = get_pairs()

            for t in pairs:
                if not eligible(t):
                    continue

                pair_id = t.get("pairAddress")
                if not pair_id or pair_id in seen_tokens:
                    continue
