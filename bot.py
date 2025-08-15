import json
import asyncio
import requests
from datetime import datetime, timedelta
from telegram import Bot
from telegram.constants import ParseMode

# Загружаем конфиг
with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

BOT_TOKEN = config["bot_token"]
CHAT_ID = config["chat_id"]
POLL_INTERVAL = config["poll_interval_seconds"]

bot = Bot(token=BOT_TOKEN)

API_URL = "https://api.dexscreener.com/latest/dex/search?q=solana"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Bot/1.0; +https://github.com/yourusername)"
}

def get_solana_data():
    """Запрос к DexScreener API"""
    try:
        response = requests.get(API_URL, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Ошибка API {response.status_code}: {response.text}")
            return None
    except Exception as e:
        print(f"Ошибка подключения: {e}")
        return None

def format_message(data):
    """Форматируем сообщение для Telegram"""
    if not data or "pairs" not in data:
        return "Данные о Solana недоступны сейчас."

    msg = "<b>Топ пары по Solana:</b>\n"
    for pair in data["pairs"][:5]:
        name = pair.get("baseToken", {}).get("name", "Неизвестно")
        price = pair.get("priceUsd", "—")
        liquidity = pair.get("liquidity", {}).get("usd", "—")
        msg += f"\n{name}: ${price} | Ликвидность: ${liquidity}"
    return msg

async def send_message_periodically():
    """Основной цикл работы"""
    last_active_msg_time = datetime.now()

    while True:
        # Получаем данные
        data = get_solana_data()
        message = format_message(data)

        # Отправляем сообщение с парами
        await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode=ParseMode.HTML)

        # Если прошло больше часа — отправляем "бот активен"
        if datetime.now() - last_active_msg_time >= timedelta(hours=1):
            await bot.send_message(chat_id=CHAT_ID, text="✅ Бот активен", parse_mode=ParseMode.HTML)
            last_active_msg_time = datetime.now()

        await asyncio.sleep(POLL_INTERVAL)

async def main():
    await send_message_periodically()

if __name__ == "__main__":
    asyncio.run(main())
