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

# Фильтры
MIN_LIQ_USD = float(os.getenv("MIN_LIQ_USD", 5000))
MIN_VOL_5M = float(os.getenv("MIN_VOL_5M", 3000))
MIN_BUYS_5M = int(os.getenv("MIN_BUYS_5M", 20))
MIN_PCHANGE_5M = float(os.getenv("MIN_PCHANGE_5M", 5))
QUOTE_PREF = [x.strip().upper() for x in os.getenv("QUOTE_PREF", "USDC,SOL").split(",")]
NEW_MAX_AGE_MIN = int(os.getenv("NEW_MAX_AGE_MIN", 10))

# Параметры работы
POLL_SECONDS = int(os.getenv("POLL_SECONDS", 60))
HEARTBEAT_HOURS = float(os.getenv("HEARTBEAT_HOURS", 2))
SELL_DROP_PCT = float(os.getenv("SELL_DROP_PCT", 7))
TRACK_TTL_ = int(os.getenv("TRACK_TTL_HOURS", 24)) * 3600  # в секундах

# --------------------------
# Отправка в Telegram
# --------------------------
def send_telegram_message(text: str):
    for chat_id in TELEGRAM_CHAT_IDS:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        try:
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code != 200:
                logging.error(f"Ошибка Telegram API: {resp.text}")
        except Exception as e:
            logging.error(f"Ошибка отправки в {chat_id}: {e}")

# --------------------------
# Основная логика бота
# --------------------------
def main():
    logging.info("🚀 Бот запущен. Ожидание сигналов...")

    last_heartbeat = datetime.now(timezone.utc)

    while True:
        try:
            # Пример проверки — тут будет логика поиска монет
            now = datetime.now(timezone.utc)
            
            # Отправляем heartbeat каждые HEARTBEAT_HOURS
            if (now - last_heartbeat) > timedelta(hours=HEARTBEAT_HOURS):
                send_telegram_message("✅ Бот работает — пока всё тихо.")
                last_heartbeat = now

            # Здесь можно вставить проверку рынка и отправку сигналов
            # send_telegram_message("💎 Найден новый токен: ...")

        except Exception as e:
            logging.error(f"Ошибка в основном цикле: {e}")

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
