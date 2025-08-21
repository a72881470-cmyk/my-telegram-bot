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

# Новый правильный эндпоинт Birdeye
API_URL = "https://public-api.birdeye.so/defi/tokenlist?sort=createdAt&sort_type=desc&chain=solana"
HEADERS = {"x-api-key": BIRDEYE_API_KEY}

# Запоминаем токены, чтобы не слать повторно
seen_tokens = {}


def get_new_tokens():
    """Получаем список новых токенов с Birdeye"""
    try:
        response = requests.get(API_URL, headers=HEADERS)

        # Если лимит исчерпан
        if response.status_code == 400 and "limit exceeded" in response.text.lower():
            print("⚠️ Превышен лимит запросов BirdEye. Ждём 60 секунд...")
            time.sleep(60)
            return []

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
        bot.send_message(CHAT_ID, text, parse_mode="HTML")
    except Exception as e:
        print("Ошибка при отправке в Telegram:", e)


def check_tokens():
    tokens = get_new_tokens()
    now = datetime.now(timezone.utc)

    for token in tokens:
        try:
            name = token.get("name")
            symbol = token.get("symbol")
            address = token.get("address")
            price = token.get("priceUsd", 0) or 0
            created_at = datetime.fromtimestamp(token.get("createdAt") / 1000, tz=timezone.utc)

            # Только токены младше 3 часов
            if (now - created_at) > timedelta(hours=3):
                continue

            if address not in seen_tokens:
                seen_tokens[address] = price

                msg = (
                    f"🆕 Новый токен на Solana!\n\n"
                    f"💎 <b>{name} ({symbol})</b>\n"
                    f"💰 Цена: ${price:.8f}\n"
                    f"📅 Создан: {created_at.strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
                    f"🔗 <a href='https://birdeye.so/token/{address}?chain=solana'>Мониторинг</a>\n"
                    f"👛 <a href='https://phantom.app/ul/browse/{address}'>Phantom</a>"
                )
                notify_telegram(msg)

                print(f"[NEW] {name} ({symbol}) - {address} - ${price:.8f}")

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

                        print(f"[GROWTH] {name} ({symbol}) +{growth:.2f}%")

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
