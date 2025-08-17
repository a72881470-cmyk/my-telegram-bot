import os
import threading
import http.server
import socketserver
import logging
import websocket
import requests
import time

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

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")  # healthcheck
        else:
            super().do_GET()

def run_http_server():
    with socketserver.TCPServer(("0.0.0.0", PORT), Handler) as httpd:
        logging.info(f"🌍 HTTP сервер слушает порт {PORT}")
        send_telegram(f"🌍 HTTP сервер слушает порт {PORT}")
        httpd.serve_forever()

# === WebSocket PumpPortal ===
def on_message(ws, message):
    logging.info(f"📩 Пришло сообщение: {message}")
    send_telegram(f"📩 {message}")

def on_open(ws):
    logging.info("🔗 WebSocket подключен")
    send_telegram("🔗 WebSocket подключен к PumpPortal")

def start_websocket():
    while True:
        try:
            ws = websocket.WebSocketApp(
                "wss://pumpportal.fun/api/data",
                on_message=on_message,
                on_open=on_open
            )
            ws.run_forever(ping_interval=30, ping_timeout=10)
        except Exception as e:
            logging.error(f"❌ Ошибка WebSocket: {e}")
            send_telegram(f"❌ Ошибка WebSocket: {e}")
        logging.info("♻️ Переподключение через 5 секунд…")
        time.sleep(5)

if __name__ == "__main__":
    logging.info("🚀 Бот запущен. Ловим мемкоины Solana…")
    send_telegram("🚀 Бот запущен на Railway")

    # Запускаем WebSocket в отдельном потоке (НЕ daemon!)
    threading.Thread(target=start_websocket).start()

    # Главный процесс — HTTP сервер (держит Railway живым)
    run_http_server()
