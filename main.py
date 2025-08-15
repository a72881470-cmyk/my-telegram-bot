import os
import time
import requests
import logging
from dotenv import load_dotenv

# Загружаем .env
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

DEX_API = "https://api.dexscreener.com/latest/dex/tokens/solana"

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        logging.error(f"Ошибка отправки сообщения в Telegram: {e}")

def check_solana_tokens():
    try:
        resp = requests.get("https://api.dexscreener.com/latest/dex/search?q=solana", timeout=10)
        data = resp.json()
        if "pairs" not in data:
            return

        for pair in data["pairs"]:
            try:
                token_name = pair.get("baseToken", {}).get("name", "Unknown")
                token_symbol = pair.get("baseToken", {}).get("symbol", "")
                token_addr = pair.get("baseToken", {}).get("address", "")
                price_change = float(pair.get("priceChange", {}).get("m5", 0))
                dex_url = pair.get("url", "")
                phantom_url = f"https://phantom.app/ul/browse/{token_addr}"

                if price_change > 0:  # фильтр: только положительный рост
                    msg = (
                        f"🚀 *Новый рост токена!*\n"
                        f"💎 Token: *{token_name}* ({token_symbol})\n"
                        f"📈 Рост: *+{price_change:.2f}%* за 5м\n"
                        f"[🔗 DexScreener]({dex_url}) | [👛 Phantom]({phantom_url})"
                    )
                    send_telegram_message(msg)
            except Exception as e:
                logging.error(f"Ошибка обработки пары: {e}")

    except Exception as e:
        logging.error(f"Ошибка при запросе DexScreener: {e}")

if __name__ == "__main__":
    logging.info("🚀 Бот запущен. Мониторинг токенов Solana...")
    while True:
        check_solana_tokens()
        time.sleep(60)
