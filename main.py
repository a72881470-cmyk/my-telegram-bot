import os
import time
import requests
import telebot
from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta

# Загружаем .env
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
BIRDEYE_API_KEY = os.getenv("BIRDEYE_API_KEY")

bot = telebot.TeleBot(TELEGRAM_TOKEN)

API_URL = "https://public-api.birdeye.so/public/tokenlist?sort=createdAt&chain=solana"
HEADERS = {
    "x-api-key": BIRDEYE_API_KEY,
    "accept": "application/json"
}

# Запоминаем токены, чтобы не слать повторно
seen_tokens = {}

def get_new_tokens():
    """Получаем список новых токенов с Birdeye"""
    try:
        response = requests.get(API_URL, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            return response.json().get("data", {}).get("items", [])
        else:
            print("Ошибка API:", response.status_code, response.text)
            return []
    except Exception as e:
        print("Ошибка при запросе:", e)
        return []

def notify_telegram(text):
    """Отправка уведомления в Telegram"""
    try:
        bot.send_message(CHAT_ID, text, parse_mode="HTML", disable_web_page_preview=True)
    except Exception as e:
        print("Ошибка при отправке в Telegram:", e)

def check_tokens():
    tokens = get_new_tokens()
    now = datetime.now(timezone.utc)

    for token in tokens:
        try:
            name = token.get("name", "Unknown")
            symbol = token.get("symbol", "?")
            address = token.get("address")
            price = float(token.get("priceUsd") or 0.0)

            created_at_raw = token.get("createdAt")
            if not created_at_raw:
                continue  # если нет даты создания → пропускаем

            created_at = datetime.fromtimestamp(created_at_raw / 1000, tz=timezone.utc)

            # Только токены младше 3 часов
            if (now - created_at) > timedelta(hours=3):
                continue

            if address not in seen_tokens:
                seen_tokens[address] = price

                msg = (
                    f"🆕 Новый токен на Solana!\n\n"
                    f"💎 <b>{name} ({symbol})</b>\n"
                    f"💰 Цена: ${price:.8f}\n"
                    f"📈 Рост: 0% (новый)\n"
                    f"🔗 <a href='https://birdeye.so/token/{address}?chain=solana'>Мониторинг</a>\n"
                    f"👛 <a href='https://phantom.app/ul/browse/{address}'>Phantom</a>"
                )
                notify_telegram(msg)

            else:
                old_price = seen_tokens[address]
                if old_price > 0:
                    growth = ((price - old_price) / old_price) * 100
                    if growth >= 30:
                        msg = (
                            f"🚀 Токен <b>{name} ({symbol})</b> вырос на {growth:.2f}%!\n"
                            f"💰 Цена: ${price:.8f}\n"
                            f"🔗 <a href='https://birdeye.so/token/{address}?chain=solana'>Мониторинг</a>"
                        )
                        notify_telegram(msg)

                # Обновляем цену
                seen_tokens[address] = price
        except Exception as e:
            print("Ошибка при обработке токена:", e)

def heartbeat():
    notify_telegram("✅ Бот жив 👋")

if __name__ == "__main__":
    last_heartbeat = time.time()

    while True:
        check_tokens()

        # Каждые 2 часа напоминаем, что бот жив
        if time.time() - last_heartbeat > 7200:
            heartbeat()
            last_heartbeat = time.time()

        time.sleep(60)  # проверяем раз в минуту
