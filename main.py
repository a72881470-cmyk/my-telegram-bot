import requests
import telebot
import time
from datetime import datetime, timedelta

# 🔑 Токен и чат
TELEGRAM_TOKEN = "ТОКЕН_ТВОЕГО_БОТА"
CHAT_ID = "ТВОЙ_CHAT_ID"
API_KEY = "9aad437cea2b440e8ebf437a60a3d02e"  # ✅ твой ключ с Birdeye

bot = telebot.TeleBot(TELEGRAM_TOKEN)
sent_tokens = set()

# 📡 Получаем новые токены Solana
def fetch_new_tokens():
    url = "https://public-api.birdeye.so/defi/tokenlist?sort_by=created_at&sort_type=desc&offset=0&limit=50"
    headers = {
        "accept": "application/json",
        "x-chain": "solana",
        "X-API-KEY": API_KEY
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            print(f"❌ Ошибка API: статус {resp.status_code}, ответ: {resp.text}")
            return []

        data = resp.json()
        tokens = data.get("data", {}).get("tokens", [])

        new_tokens = []
        now = datetime.utcnow()
        max_age = timedelta(days=2)

        for token in tokens:
            created_at = token.get("created_at")
            if not created_at:
                continue

            try:
                created_at = datetime.utcfromtimestamp(int(created_at))
            except Exception:
                continue

            if now - created_at <= max_age:
                # 🔹 Объём
                vol = token.get("volume_usd", 0)
                try:
                    vol = float(vol)
                except Exception:
                    vol = 0

                # 🔹 Ликвидность
                liq = token.get("liquidity_usd", 0)
                try:
                    liq = float(liq)
                except Exception:
                    liq = 0

                # 📌 Фильтр: объём > 5000$ и ликвидность > 10k$
                if vol > 5000 and liq > 10000:
                    new_tokens.append(token)

        print(f"✅ Найдено {len(new_tokens)} новых токенов (2 дня, vol>5k$, liq>10k$)")
        return new_tokens[:5]

    except Exception as e:
        print("Ошибка API:", e)
        return []

# 📩 Отправляем токен в Telegram
def send_token_alert(token):
    try:
        name = token.get("name", "N/A")
        symbol = token.get("symbol", "N/A")
        address = token.get("address", "N/A")

        price = token.get("price", "N/A")
        try:
            price = round(float(price), 6)
        except Exception:
            price = "N/A"

        volume = token.get("volume_usd", "N/A")
        try:
            volume = round(float(volume), 2)
        except Exception:
            volume = "N/A"

        liquidity = token.get("liquidity_usd", "N/A")
        try:
            liquidity = round(float(liquidity), 2)
        except Exception:
            liquidity = "N/A"

        message = (
            f"🟢 Новый токен найден!\n\n"
            f"📛 Название: {name}\n"
            f"🔹 Символ: {symbol}\n"
            f"💲 Цена: {price}\n"
            f"📊 Объём 24ч: {volume}$\n"
            f"💧 Ликвидность: {liquidity}$\n"
            f"🌐 DexScreener: https://dexscreener.com/solana/{address}\n"
            f"👛 Phantom: https://phantom.app/ul/browse/{address}"
        )

        bot.send_message(CHAT_ID, message)
        print(f"✅ Отправлено: {name} ({symbol})")

    except Exception as e:
        print("Ошибка отправки в Telegram:", e)

# 🚀 Основной цикл
def main():
    print("🚀 Бот запущен, ловлю новые токены Solana...")
    while True:
        tokens = fetch_new_tokens()
        for token in tokens:
            address = token.get("address")
            if not address:
                continue
            if address in sent_tokens:
                print(f"⚠ {token.get('symbol', '???')} уже отправляли, пропуск...")
                continue
            send_token_alert(token)
            sent_tokens.add(address)
        time.sleep(60)

if __name__ == "__main__":
    main()
