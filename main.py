import os
import json
import requests
import websocket
import logging
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# 🔥 Фильтры для "ростущих" токенов
MIN_LIQ_USD = float(os.getenv("MIN_LIQ_USD", 5000))
MIN_VOL_5M = float(os.getenv("MIN_VOL_5M", 3000))

DEXSCREENER_URL = "https://api.dexscreener.com/latest/dex/tokens/"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text})
    except Exception as e:
        logging.error(f"Ошибка отправки в Telegram: {e}")

def check_with_dexscreener(token_address):
    try:
        url = f"{DEXSCREENER_URL}{token_address}"
        r = requests.get(url, timeout=10)
        data = r.json()

        if "pairs" not in data:
            return False, None

        for pair in data["pairs"]:
            liquidity_usd = pair.get("liquidity", {}).get("usd", 0)
            vol_5m = pair.get("volume", {}).get("m5", 0)

            if liquidity_usd >= MIN_LIQ_USD and vol_5m >= MIN_VOL_5M:
                return True, pair

        return False, None
    except Exception as e:
        logging.error(f"DexScreener error: {e}")
        return False, None

def on_message(ws, message):
    try:
        data = json.loads(message)
        token_address = data.get("mint")
        name = data.get("name")
        symbol = data.get("symbol")

        # 1. Отправляем все мемки
        send_telegram(f"🚀 Новый мемкоин на Solana!\n{name} ({symbol})\nCA: {token_address}")

        # 2. Проверяем на «ростущий»
        is_potential, pair = check_with_dexscreener(token_address)
        if is_potential:
            price = pair.get("priceUsd")
            liquidity = pair.get("liquidity", {}).get("usd", 0)
            vol_5m = pair.get("volume", {}).get("m5", 0)

            send_telegram(
                f"⚡ Внимание! Потенциально ростущий токен\n"
                f"{name} ({symbol})\n"
                f"Цена: ${price}\n"
                f"Ликвидность: ${liquidity}\n"
                f"Объём (5m): ${vol_5m}\n"
                f"CA: {token_address}"
            )

    except Exception as e:
        logging.error(f"Ошибка обработки сообщения: {e}")

def on_error(ws, error):
    logging.error(f"WebSocket error: {error}")

def on_close(ws, close_status_code, close_msg):
    logging.info("WebSocket closed")

def on_open(ws):
    logging.info("✅ Подключено к PumpPortal WebSocket")

if __name__ == "__main__":
    logging.info("🚀 Бот запущен. Ловим мемкоины Solana…")
    ws = websocket.WebSocketApp(
        "wss://pumpportal.fun/api/data",
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws.on_open = on_open
    ws.run_forever()
