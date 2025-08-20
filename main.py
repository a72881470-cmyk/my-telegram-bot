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
    url = "https://api.dexscreener.com/latest/dex/chains/solana"
    try:
        resp = requests.get(url, timeout=10)

        if resp.status_code != 200:
            print(f"❌ Ошибка API: статус {resp.status_code}")
            return []

        data = resp.json()

        if not data or "pairs" not in data:
            print("⚠ API вернуло пустой ответ или нет поля 'pairs'")
            return []

        pairs = data["pairs"]
        print(f"🔍 Всего пар на Solana: {len(pairs)}")

        # Логируем первые 3 токена для проверки
        for p in pairs[:3]:
            print("👉", p.get("baseToken", {}).get("symbol"), "-", p.get("baseToken", {}).get("name"))

        # --- Фильтр по возрасту и объему ---
        new_pairs = []
        now = datetime.utcnow()
        max_age = timedelta(days=2)

        for pair in pairs:
            created_ts = pair.get("pairCreatedAt")
            if created_ts:
                created_at = datetime.utcfromtimestamp(created_ts / 1000)
                if now - created_at <= max_age:
                    volume = pair.get("volume", {}).get("h24", 0)
                    if volume and volume > 5000:  # фильтр по объему
                        new_pairs.append(pair)

        print(f"✅ Найдено {len(new_pairs)} новых токенов (младше 2 дней и volume > 5k$)")
        return new_pairs[:5]

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
        volume = token.get("volume", {}).get("h24", "N/A")

        message = (
            f"🟢 Новый токен найден!\n\n"
            f"📛 Название: {name}\n"
            f"🔹 Символ: {symbol}\n"
            f"💲 Цена: {price}\n"
            f"📊 Объем 24ч: {volume}$\n"
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
