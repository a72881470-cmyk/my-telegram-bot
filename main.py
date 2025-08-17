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
    """Отправка сообщений в Telegram"""
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
    """HTTP сервер, чтобы Railway не гасил контейнер"""
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("0.0.0.0", PORT), handler) as httpd:
        logging.info(f"🌐 Server started on port {PORT}")
        send_telegram(f"🌐 Server started on port {PORT}")
        httpd.serve_forever()

# === WebSocket PumpPortal ===
def on_message(ws, message):
    logging.info(f"📩 Пришло сообщение: {message}")
    send_telegram(f"📩 {message}")

def on_open(ws):
    logging.info("🔗 WebSocket подключен")
    send_telegram("🔗 WebSocket подключен к PumpPortal")

def on_error(ws, error):
    logging.error(f"❌ WebSocket ошибка: {error}")
    send_telegram(f"❌ WebSocket ошибка: {error}")

def on_close(ws, close_status_code, close_msg):
    logging.warning(f"⚠️ WebSocket закрыт: {close_status_code}, {close_msg}")
    send_telegram(f"⚠️ WebSocket закрыт. Переподключение...")

def start_websocket():
    """Подключение к WebSocket с автопереподключением"""
    while True:
        try:
            ws = websocket.WebSocketApp(
                "wss://pumpportal.fun/api/data",
                on_message=on_message,
                on_open=on_open,
                on_error=on_error,
                on_close=on_close
            )
            ws.run_forever()
        except Exception as e:
            logging.error(f"💥 Критическая ошибка WebSocket: {e}")
            send_telegram(f"💥 Критическая ошибка WebSocket: {e}")
        logging.info("♻️ Переподключение к WebSocket через 5 секунд...")
        time.sleep(5)

if __name__ == "__main__":
    logging.info("🚀 Бот запущен. Ловим мемкоины Solana…")
    send_telegram("🚀 Бот запущен на Railway")

    # Запускаем HTTP сервер в отдельном потоке
    threading.Thread(target=run_http_server, daemon=True).start()

    # Запускаем WebSocket с автопереподключением
    start_websocket()
