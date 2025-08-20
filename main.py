import requests
import telebot
import time
from datetime import datetime, timedelta

TELEGRAM_TOKEN = "ТОКЕН_ТВОЕГО_БОТА"
CHAT_ID = "ТВОЙ_CHAT_ID"

bot = telebot.TeleBot(TELEGRAM_TOKEN)

sent_tokens = set()

def fetch_new_tokens():
    url = "https://public-api.birdeye.so/public/tokenlist?sort_by=created_at&sort_type=desc&offset=0&limit=50&chain=solana"
    headers = {"accept": "application/json", "x-chain": "solana"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            print(f"❌ Ошибка API: статус {resp.status_code}")
            return []

        data = resp.json()
        tokens = data.get("data", {}).get("tokens", [])

        new_tokens = []
        now = datetime.utcnow()
        max_age = timedelta(days=2)

        for token in tokens:
            created_at = token.get("created_at")
            if created_at:
                created_at = datetime.utcfromtimestamp(int(created_at))
                if now - created_at <= max_age:
                    vol = token.get("volume_usd", 0)
                    if vol and vol > 5000:  # фильтр по объёму
                        new_tokens.append(token)

        print(f"✅ Найдено {len(new_tokens)} новых токенов (за 2 дня, volume > 5k$)")
        return new_tokens[:5]

    except Exception as e:
        print("Ошибка API:", e)
        return []

def send_token_alert(token):
    try:
        name = token.get("name", "N/A")
        symbol = token.get("symbol", "N/A")
        address = token.get("address", "N/A")
        price = token.get("price", "N/A")
        volume = token.get("volume_usd", "N/A")

        message = (
            f"🟢 Новый токен найден!\n\n"
            f"📛 Название: {name}\n"
            f"🔹 Символ: {symbol}\n"
            f"💲 Цена: {price}\n"
            f"📊 Объём 24ч: {volume}$\n"
            f"🌐 DexScreener: https://dexscreener.com/solana/{address}\n"
            f"👛 Phantom: https://phantom.app/ul/browse/{address}"
        )

        bot.send_message(CHAT_ID, message)
        print(f"✅ Отправлено: {name} ({symbol})")
    except Exception as e:
        print("Ошибка отправки в Telegram:", e)

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
