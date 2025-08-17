import os
import threading
import http.server
import socketserver
import logging
import websocket
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# === Telegram ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def send_telegram(msg: str):
    if not BOT_TOKEN or not CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": msg}
        )
    except Exception as e:
        logging.error(f"Ошибка отправки в Telegram: {e}")

# === HTTP сервер для Railway ===
PORT = int(os.getenv("PORT", 8080))

def run_http_server():
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("0.0.0.0", PORT), handler) as httpd:
        logging.info(f"✅ HTTP сервер слушает порт {PORT}")
        send_telegram(f"✅ HTTP сервер слушает порт {PORT}")
        httpd.serve_forever()

# === WebSocket PumpPortal ===
def on_message(ws, message):
    logging.info(f"📩 Пришло сообщение: {message}")
    send_telegram(f"📩 {message}")

def on_open(ws):
    logging.info("🔗 WebSocket подключен")
    send_telegram("🔗 WebSocket подключен к PumpPortal")

def start_websocket():
    ws = websocket.WebSocketApp(
        "wss://pumpportal.fun/api/data",
        on_message=on_message,
        on_open=on_open
    )
    ws.run_forever()

if __name__ == "__main__":
    logging.info("🚀 Бот запущен. Ловим мемкоины Solana…")

    # Запускаем HTTP сервер в отдельном потоке
    threading.Thread(target=run_http_server, daemon=True).start()

    # Запускаем WebSocket
    start_websocket()
