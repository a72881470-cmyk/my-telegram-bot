import requests
import telebot
import time
import json
from datetime import datetime, timedelta

# 🔑 Твой токен телеграм-бота
TELEGRAM_TOKEN = "ТОКЕН_ТВОЕГО_БОТА"
CHAT_ID = "ТВОЙ_CHAT_ID"

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Храним уже отправленные токены
sent_tokens = set()

# Функция получения новых токенов с DexScreener
def fetch_new_tokens():
    url = "https://api.dexscreener.com/latest/dex/pairs/solana"
    try:
        resp = requests.get(url, timeout=10)

        if resp.status_code != 200:
            print(f"❌ Ошибка API: статус {resp.status_code}")
            return []

        data = resp.json()

        # Сохраняем ответ для анализа
        with open("api_debug.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        if not data or "pairs" not in data or not data["pairs"]:
            print("⚠ API вернуло пустой ответ или нет поля 'pairs'")
            return []

        new_pairs = []
        now = datetime.utcnow()
        max_age = timedelta(days=2)  # только токены младше 2 дней

        for pair in data["pairs"]:
            created_ts = pair.get("pairCreatedAt")
            if created_ts:
                created_at = datetime.utcfromtimestamp(created_ts / 1000)
                age = now - created_at
                if age <= max_age:
                    new_pairs.append(pair)

        print(f"✅ Найдено {len(new_pairs)} новых токенов (младше 2 дней)")
        return new_pairs[:5]  # берём только первые 5
    except Exception as e:
        print("Ошибка API:", e)
        return []

# Отправка токена в телеграм
def send_token_alert(token):
    try:
        name = token.get("baseToken", {}).get("name", "N/A")
        symbol = token.get("baseToken", {}).get("symbol", "N/A")
        price = token.get("priceUsd", "N/A")
        url = token.get("url", "https://dexscreener.com/")
        created_ts = token.get("pairCreatedAt")

        created_at_str = "N/A"
        if created_ts:
            created_at = datetime.utcfromtimestamp(created_ts / 1000)
            created_at_str = created_at.strftime("%Y-%m-%d %H:%M:%S")

        message = (
            f"🟢 Новый токен найден!\n\n"
            f"📛 Название: {name}\n"
            f"🔹 Символ: {symbol}\n"
            f"💲 Цена: {price}\n"
            f"🕒 Дата создания: {created_at_str} UTC\n"
            f"🌐 DexScreener: {url}\n"
            f"👛 Phantom: https://phantom.app/"
        )

        bot.send_message(CHAT_ID, message)
        print(f"✅ Отправлено: {name} ({symbol})")
    except Exception as e:
        print("Ошибка отправки в Telegram:", e)

# Основной цикл
def main():
    print("🚀 Бот запущен, слежу за Solana...")
    while True:
        tokens = fetch_new_tokens()
        for token in tokens:
            address = token.get("pairAddress")
            if not address:
                continue

            if address in sent_tokens:
                print(f"⚠ {token.get('baseToken', {}).get('symbol', '???')} уже отправляли, пропуск...")
                continue

            send_token_alert(token)
            sent_tokens.add(address)

        time.sleep(60)  # проверка раз в минуту

if __name__ == "__main__":
    main()
