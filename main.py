import os
import json
import requests
import websocket
import logging
import time
import signal
import sys
import threading
import http.server
import socketserver
from dotenv import load_dotenv

# Загружаем .env
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

MIN_LIQ_USD = float(os.getenv("MIN_LIQ_USD", 5000))
MIN_VOL_5M = float(os.getenv("MIN_VOL_5M", 3000))

DEXSCREENER_URL = "https://api.dexscreener.com/latest/dex/tokens/"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ================= TELEGRAM =================
def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text})
    except Exception as e:
        logging.error(f"Ошибка отправки в Telegram: {e}")

# ================= DEXSCREENER =================
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

# ================= WEBSOCKET CALLBACKS =================
def on_message(ws, message):
    try:
        data = json.loads(message)
        token_address = data.get("mint")
        name = data.get("name")
        symbol = data.get("symbol")

        send_telegram(f"🚀 Новый мемкоин на Solana!\n{name} ({symbol})\nCA: {token_address}")

        is_potential, pair = check_with_dexscreener(token_address)
        if is_potential:
            price = pair.get("priceUsd")
            liquidity = pair.get("liquidity", {}).get("usd", 0)
            vol_5m = pair.get("volume", {}).get("m5", 0)

            send_telegram(
                f"⚡ Внимание! Потенциально растущий токен\n"
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
    logging.warning("⚠️ WebSocket closed")

def on_open(ws):
    logging.info("✅ Подключено к PumpPortal WebSocket")
    send_telegram("✅ Подключено к PumpPortal WebSocket")

# ================= WEBSOCKET RUNNER =================
def run_ws():
    while True:
        try:
            ws = websocket.WebSocketApp(
                "wss://pumpportal.fun/api/data",
                on_message=on_message,
                on_error=on_error,
                on_close=on_close
            )
            ws.on_open = on_open
            ws.run_forever(ping_interval=30, ping_timeout=10)
        except Exception as e:
            logging.error(f"Ошибка WebSocket: {e}")

        logging.info("♻️ Переподключение через 5 секунд...")
        send_telegram("♻️ Переподключение к PumpPortal WebSocket...")
        time.sleep(5)

# ================= HTTP SERVER (для Railway) =================
PORT = int(os.getenv("PORT", 8080))

def run_http_server():
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", PORT), handler) as httpd:
        logging.info(f"🌍 HTTP сервер запущен на порту {PORT}")
        httpd.serve_forever()

# ================= SHUTDOWN HANDLER =================
def shutdown_handler(sig, frame):
    logging.info("🛑 Бот остановлен")
    send_telegram("🛑 Бот остановлен")
    sys.exit(0)

signal.signal(signal.SIGINT, shutdown_handler)
signal.signal(signal.SIGTERM, shutdown_handler)

# ================= MAIN =================
if __name__ == "__main__":
    logging.info("🚀 Бот запущен. Ловим мемкоины Solana…")
    send_telegram("🤖 Бот запущен и готов ловить мемкоины Solana!")

    # Запускаем HTTP сервер в отдельном потоке (для Railway)
    threading.Thread(target=run_http_server, daemon=True).start()

    # Запускаем WebSocket
    run_ws()
