import os
import logging
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv
from telegram import Bot
from flask import Flask, request

# Загружаем .env
load_dotenv()

# Логирование
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# Конфиг
NEW_MAX_AGE_MIN = 180
MIN_LIQ_USD = 10000
MAX_LIQ_USD = 5000000
MAX_FDV_USD = 50000000
MIN_TXNS_5M = 10
MIN_BUYS_RATIO_5M = 0.45
MIN_PCHANGE_5M_BUY = 1
MIN_PCHANGE_5M_ALERT = 5

# Telegram
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
bot = Bot(token=TELEGRAM_TOKEN)

# Flask (для Heroku/PaaS)
app = Flask(__name__)

DEXSCREENER_API = "https://api.dexscreener.com/latest/dex/pairs/solana"

def fetch_pairs():
    try:
        resp = requests.get(DEXSCREENER_API, timeout=10)
        if resp.status_code == 200:
            return resp.json().get("pairs", [])
    except Exception as e:
        logging.error(f"Ошибка API Dexscreener: {e}")
    return []

def process_pairs():
    pairs = fetch_pairs()
    if not pairs:
        return

    for pair in pairs:
        try:
            base_token = pair["baseToken"]["symbol"]
            liquidity_usd = float(pair.get("liquidity", {}).get("usd", 0))
            fdv = float(pair.get("fdv", 0))
            txns5m = int(pair.get("txns", {}).get("m5", {}).get("buys", 0)) + int(pair.get("txns", {}).get("m5", {}).get("sells", 0))
            buys = int(pair.get("txns", {}).get("m5", {}).get("buys", 0))
            ratio_buys = buys / txns5m if txns5m > 0 else 0
            price_change_5m = float(pair.get("priceChange", {}).get("m5", 0))

            # ---------------- ФИКС возраста ----------------
            created_at = pair.get("pairCreatedAt")
            if isinstance(created_at, int):  # timestamp (ms)
                created_dt = datetime.fromtimestamp(created_at / 1000, tz=timezone.utc)
            elif isinstance(created_at, str):  # ISO
                created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            else:
                created_dt = datetime.now(timezone.utc)
            age_min = (datetime.now(timezone.utc) - created_dt).total_seconds() / 60
            # ------------------------------------------------

            # Фильтрация
            if not (liquidity_usd >= MIN_LIQ_USD and liquidity_usd <= MAX_LIQ_USD):
                continue
            if fdv > MAX_FDV_USD:
                continue
            if txns5m < MIN_TXNS_5M:
                continue
            if ratio_buys < MIN_BUYS_RATIO_5M:
                continue
            if age_min > NEW_MAX_AGE_MIN:
                continue

            # Сигнал
            if price_change_5m >= MIN_PCHANGE_5M_ALERT:
                message = (
                    f"🚀 Новый сигнал!\n\n"
                    f"Монета: {base_token}\n"
                    f"Цена изм. 5м: {price_change_5m:.2f}%\n"
                    f"Ликвидность: ${liquidity_usd:,.0f}\n"
                    f"FDV: ${fdv:,.0f}\n"
                    f"Сделки (5м): {txns5m}\n"
                    f"Buy Ratio: {ratio_buys:.2%}\n"
                    f"Возраст: {age_min:.1f} мин\n"
                    f"🔗 {pair.get('url')}"
                )
                bot.send_message(chat_id=CHAT_ID, text=message)

        except Exception as e:
            logging.warning(f"Ошибка обработки пары {pair.get('baseToken', {}).get('symbol', '?')}: {e}")

@app.route("/ping", methods=["GET"])
def ping():
    return "pong", 200

if __name__ == "__main__":
    logging.info("🚀 Бот запущен и мониторит рынок Solana")
    process_pairs()  # запуск один раз при старте
