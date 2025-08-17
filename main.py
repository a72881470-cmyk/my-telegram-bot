import os
import time
import requests
import logging
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Фильтры
MIN_LIQ_USD = float(os.getenv("MIN_LIQ_USD", 100))
MIN_PCHANGE_5M = float(os.getenv("MIN_PCHANGE_5M", 5))
MIN_VOL_5M = float(os.getenv("MIN_VOL_5M", 100))
NEW_MAX_AGE_MIN = int(os.getenv("NEW_MAX_AGE_MIN", 10))
POLL_SECONDS = int(os.getenv("POLL_SECONDS", 60))

# Логирование
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# --- TELEGRAM ---
def send_telegram(msg: str):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        logging.error(f"Ошибка отправки в Telegram: {e}")

# --- Pump.fun API ---
def get_new_pumpfun_tokens():
    url = "https://frontend-api.pump.fun/coins/"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        coins = resp.json()
        
        fresh_tokens = []
        for c in coins:
            age_min = (time.time() - c.get("created_timestamp", 0)) / 60
            if age_min <= NEW_MAX_AGE_MIN:  # токены не старше N минут
                fresh_tokens.append({
                    "symbol": c.get("symbol"),
                    "address": c.get("mint"),
                    "age_min": round(age_min, 1)
                })
        return fresh_tokens
    except Exception as e:
        logging.error(f"Ошибка запроса Pump.fun: {e}")
        return []

# --- Dexscreener API ---
def get_token_info(address: str):
    url = f"https://api.dexscreener.com/latest/dex/tokens/{address}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return None
        data = resp.json()
        pairs = data.get("pairs", [])
        if not pairs:
            return None
        return pairs[0]  # берем первую пару
    except Exception as e:
        logging.error(f"Dexscreener error: {e}")
        return None

# --- Основной цикл ---
def main():
    logging.info("🚀 Бот запущен. Ищу новые мемкоины Solana...")
    while True:
        try:
            tokens = get_new_pumpfun_tokens()
            logging.info(f"🔎 Найдено {len(tokens)} новых токенов с Pump.fun")

            for t in tokens:
                info = get_token_info(t["address"])
                if not info:
                    continue

                liq = info.get("liquidity", {}).get("usd", 0)
                vol_5m = info.get("volume", {}).get("m5", 0)
                change_5m = info.get("priceChange", {}).get("m5", 0)

                if liq >= MIN_LIQ_USD and vol_5m >= MIN_VOL_5M and change_5m >= MIN_PCHANGE_5M:
                    msg = (
                        f"🚀 *Новый токен Solana!*\n\n"
                        f"🪙 {t['symbol']}\n"
                        f"⏱ Возраст: {t['age_min']} мин\n"
                        f"💧 Ликвидность: ${liq:,.0f}\n"
                        f"📊 Объём (5м): ${vol_5m:,.0f}\n"
                        f"📈 Рост (5м): {change_5m:.2f}%\n"
                        f"[DexScreener]({info.get('url')})"
                    )
                    send_telegram(msg)
                    logging.info(f"✅ Сигнал отправлен: {t['symbol']}")

        except Exception as e:
            logging.error(f"Ошибка цикла: {e}")

        time.sleep(POLL_SECONDS)

if __name__ == "__main__":
    main()
