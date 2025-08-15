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

# Фильтры/параметры
MIN_LIQ_USD        = float(os.getenv("MIN_LIQ_USD", 5000))
MIN_VOL_5M         = float(os.getenv("MIN_VOL_5M", 3000))
MIN_BUYS_5M        = int(os.getenv("MIN_BUYS_5M", 20))
MIN_PCHANGE_5M     = float(os.getenv("MIN_PCHANGE_5M", 5))
QUOTE_PREF         = [x.strip().upper() for x in os.getenv("QUOTE_PREF", "USDC,SOL").split(",")]
NEW_MAX_AGE_MIN    = int(os.getenv("NEW_MAX_AGE_MIN", 10))
POLL_SECONDS       = int(os.getenv("POLL_SECONDS", 60))
HEARTBEAT_HOURS    = float(os.getenv("HEARTBEAT_HOURS", 2))
SELL_DROP_PCT      = float(os.getenv("SELL_DROP_PCT", 7))
TRACK_TTL_         = int(os.getenv("TRACK_TTL", 60))  # TTL для трекинга в секундах (по умолчанию 60)

# --------------------------
# Функция отправки в Telegram
# --------------------------
def send_telegram_message(text: str):
    for chat_id in TELEGRAM_CHAT_IDS:
        try:
            resp = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
            )
            if resp.status_code != 200:
                logging.error(f"Ошибка отправки в {chat_id}: {resp.text}")
        except Exception as e:
            logging.error(f"Ошибка при отправке в Telegram: {e}")

# --------------------------
# Основной цикл
# --------------------------
if __name__ == "__main__":
    logging.info("🚀 Бот запущен. Ожидание сигналов...")

    tracked_tokens = {}  # токены, которые отслеживаются с TTL

    while True:
        now = datetime.now(timezone.utc)

        # Чистим старые записи
        tracked_tokens = {
            token: ts for token, ts in tracked_tokens.items()
            if (now - ts).total_seconds() < TRACK_TTL_
        }

        # Тут твоя логика получения новых токенов
        # Пример: просто тестовое сообщение каждые POLL_SECONDS
        send_telegram_message(f"⏱ Тестовое сообщение. Время: {now.strftime('%H:%M:%S')}")

        time.sleep(POLL_SECONDS)
