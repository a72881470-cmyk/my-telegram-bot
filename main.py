import os
import time
import requests
import telebot
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Конфиги
API_KEY = os.getenv("API_KEY")  # твой API для Solana
BOT_TOKEN = os.getenv("BOT_TOKEN")  # токен Telegram бота
CHAT_ID = os.getenv("CHAT_ID")  # твой chat_id в Telegram

bot = telebot.TeleBot(BOT_TOKEN)

# Хранилище токенов
tracked_tokens = {}

# Отправка сообщений
def send_message(text: str):
    try:
        bot.send_message(CHAT_ID, text, parse_mode="HTML", disable_web_page_preview=True)
    except Exception as e:
        print(f"Ошибка отправки в Telegram: {e}")

# Получение новых токенов
def get_new_tokens():
    url = "https://api.dexscreener.com/latest/dex/tokens"
    headers = {"Authorization": API_KEY}
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print(f"Ошибка API: {response.status_code}, {response.text}")
        return []

    tokens = response.json().get("pairs", [])
    fresh_tokens = []
    now = datetime.utcnow()

    for token in tokens:
        created_at = datetime.utcfromtimestamp(token["pairCreatedAt"] / 1000)
        if now - created_at < timedelta(hours=3):  # не старше 3 часов
            fresh_tokens.append(token)
    return fresh_tokens

# Проверка роста токена
def check_growth(token):
    address = token["baseToken"]["address"]
    price_change = token.get("priceChange", {}).get("h1", 0)

    if address not in tracked_tokens:
        tracked_tokens[address] = {
            "symbol": token["baseToken"]["symbol"],
            "price": token["priceUsd"],
            "price_change": price_change
        }
        return

    if price_change >= 30:
        msg = (
            f"🚀 <b>Рост токена!</b>\n\n"
            f"💎 Токен: <b>{token['baseToken']['symbol']}</b>\n"
            f"💰 Цена: ${token['priceUsd']}\n"
            f"📈 Рост: {price_change}%\n\n"
            f"🔗 DexScreener: https://dexscreener.com/solana/{address}\n"
            f"👛 Phantom: https://phantom.app/asset/{address}"
        )
        send_message(msg)

# Основной цикл
def run_bot():
    last_alive = time.time()

    send_message("✅ Бот запущен, ловлю новые токены Solana...")

    while True:
        try:
            tokens = get_new_tokens()
            for token in tokens:
                address = token["baseToken"]["address"]
                if address not in tracked_tokens:
                    msg = (
                        f"🪙 <b>Найден новый токен!</b>\n\n"
                        f"💎 Токен: <b>{token['baseToken']['symbol']}</b>\n"
                        f"💰 Цена: ${token['priceUsd']}\n"
                        f"⏰ Создан: {datetime.utcfromtimestamp(token['pairCreatedAt']/1000)}\n\n"
                        f"🔗 DexScreener: https://dexscreener.com/solana/{address}\n"
                        f"👛 Phantom: https://phantom.app/asset/{address}"
                    )
                    send_message(msg)

                # Проверяем рост
                check_growth(token)

            # Сообщение "жив" каждые 2 часа
            if time.time() - last_alive > 7200:
                send_message("🤖 Бот жив и работает!")
                last_alive = time.time()

            time.sleep(60)  # проверяем раз в минуту

        except Exception as e:
            print(f"Ошибка: {e}")
            time.sleep(10)


if __name__ == "__main__":
    run_bot()
