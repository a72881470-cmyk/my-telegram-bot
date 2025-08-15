import os
import time
import requests
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv

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

MIN_LIQ_USD = float(os.getenv("MIN_LIQ_USD", 500))
NEW_MAX_AGE_MIN = int(os.getenv("NEW_MAX_AGE_MIN", 60))
POLL_SECONDS = int(os.getenv("POLL_SECONDS", 60))

# Фильтр по росту
MIN_PCHANGE_5M = 25.0

# DexScreener API (Solana)
DEX_URL = "https://api.dexscreener.com/latest/dex/tokens/solana"

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_IDS:
    logging.error("❌ Проверь TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID в .env!")
    exit(1)

def send_telegram_message(text):
    """Отправка сообщения во все чаты"""
    for chat_id in TELEGRAM_CHAT_IDS:
        try:
            resp = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
            )
            if resp.status_code != 200:
                logging.warning(f"Ошибка Telegram: {resp.text}")
        except Exception as e:
            logging.error(f"Ошибка отправки в Telegram: {e}")

def get_solana_memecoins():
    """Получаем список токенов Solana с DexScreener"""
    try:
        r = requests.get("https://api.dexscreener.com/latest/dex/search?q=solana")
        data = r.json()
        tokens = data.get("pairs", [])
        result = []
        now_ts = time.time()

        for t in tokens:
            price_change_5m = t.get("priceChange", {}).get("m5", 0)
            liquidity_usd = t.get("liquidity", {}).get("usd", 0)
            tags = [tag.lower() for tag in t.get("tags", [])]
            created_at = t.get("info", {}).get("createdAt")

            # Фильтрация по времени создания токена
            age_min = None
            if created_at:
                try:
                    age_min = (now_ts - (created_at / 1000)) / 60
                except:
                    age_min = None

            if (
                "solana" in (t.get("chainId") or "").lower()
                and ("memecoin" in tags or "shitcoin" in tags)
                and price_change_5m is not None and price_change_5m >= MIN_PCHANGE_5M
                and liquidity_usd is not None and liquidity_usd >= MIN_LIQ_USD
                and age_min is not None and age_min <= NEW_MAX_AGE_MIN
            ):
                result.append(t)

        return result

    except Exception as e:
        logging.error(f"Ошибка запроса DexScreener: {e}")
        return []

def main():
    logging.info("🚀 Бот запущен. Мониторинг мемкоинов в сети Solana…")
    while True:
        coins = get_solana_memecoins()
        for c in coins:
            name = c.get("baseToken", {}).get("name", "Unknown")
            symbol = c.get("baseToken", {}).get("symbol", "")
            price_usd = c.get("priceUsd", "0")
            price_change_5m = c.get("priceChange", {}).get("m5", 0)
            pair_address = c.get("pairAddress")
            token_address = c.get("baseToken", {}).get("address", "")

            dex_link = f"https://dexscreener.com/solana/{pair_address}"
            phantom_link = f"https://phantom.app/ul/browse/{token_address}"

            msg = (
                f"🪙 <b>{name} ({symbol})</b>\n"
                f"📈 Рост за 5м: <b>+{price_change_5m:.2f}%</b>\n"
                f"💲 Цена: ${price_usd}\n"
                f"🔗 <a href='{dex_link}'>DexScreener</a>\n"
                f"🔑 <a href='{phantom_link}'>Phantom Wallet</a>"
            )
            send_telegram_message(msg)

        time.sleep(POLL_SECONDS)

if __name__ == "__main__":
    main()
