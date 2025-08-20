import requests
import telebot
import time
import json
from datetime import datetime, timedelta

# 🔑 Настройки
TELEGRAM_TOKEN = "ТОКЕН_ТВОЕГО_БОТА"
CHAT_ID = "ТВОЙ_CHAT_ID"
API_KEY = "sadasd234234234234"   # Birdeye API ключ

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# 📂 Храним отправленные токены и цены
SENT_FILE = "sent_tokens.json"
PRICES_FILE = "prices.json"

try:
    with open(SENT_FILE, "r") as f:
        sent_tokens = set(json.load(f))
except:
    sent_tokens = set()

try:
    with open(PRICES_FILE, "r") as f:
        token_prices = json.load(f)
except:
    token_prices = {}  # {address: {"price": float, "time": timestamp}}


# 📡 Получаем новые токены Solana
def fetch_new_tokens():
    url = "https://public-api.birdeye.so/defi/new_pairs?limit=50&offset=0"
    headers = {
        "accept": "application/json",
        "x-chain": "solana",
        "x-api-key": API_KEY
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            print(f"❌ Ошибка API: статус {resp.status_code}")
            return []

        data = resp.json()
        tokens = data.get("data", [])

        new_tokens = []
        now = datetime.utcnow()
        max_age = timedelta(days=2)

        for token in tokens:
            created_at = token.get("createdTime")
            if not created_at:
                continue

            try:
                created_at = datetime.utcfromtimestamp(int(created_at))
            except Exception:
                continue

            if now - created_at <= max_age:
                vol = float(token.get("volume24hUSD", 0) or 0)
                liq = float(token.get("liquidity", 0) or 0)

                if vol > 1000 and liq > 2000:
                    new_tokens.append(token)

        print(f"✅ Найдено {len(new_tokens)} новых токенов")
        return new_tokens[:5]

    except Exception as e:
        print("Ошибка API:", e)
        return []


# 📡 Получаем актуальную цену токена
def fetch_token_price(address):
    url = f"https://public-api.birdeye.so/defi/price?address={address}"
    headers = {
        "accept": "application/json",
        "x-chain": "solana",
        "x-api-key": API_KEY
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        data = resp.json()
        return float(data.get("data", {}).get("value", 0))
    except:
        return 0


# 📩 Отправляем токен в Telegram
def send_token_alert(token, alert_type="new"):
    try:
        name = token.get("baseToken", {}).get("name", "N/A")
        symbol = token.get("baseToken", {}).get("symbol", "N/A")
        address = token.get("baseToken", {}).get("address", "N/A")

        price = fetch_token_price(address)
        volume = round(float(token.get("volume24hUSD", 0) or 0), 2)
        liquidity = round(float(token.get("liquidity", 0) or 0), 2)

        if alert_type == "new":
            message = (
                f"🟢 Новый токен!\n\n"
                f"📛 Название: {name}\n"
                f"🔹 Символ: {symbol}\n"
                f"💲 Цена: {price}\n"
                f"📊 Объём 24ч: {volume}$\n"
                f"💧 Ликвидность: {liquidity}$\n"
                f"🌐 DexScreener: https://dexscreener.com/solana/{address}\n"
                f"👛 Phantom: https://phantom.app/ul/browse/{address}"
            )
        else:
            message = (
                f"🚀 РОСТ ТОКЕНА!\n\n"
                f"📛 {name} ({symbol})\n"
                f"📈 Цена выросла на {alert_type}% за 5 минут!\n"
                f"💲 Текущая цена: {price}\n"
                f"🌐 DexScreener: https://dexscreener.com/solana/{address}"
            )

        bot.send_message(CHAT_ID, message)
        print(f"✅ Отправлено сообщение про {name} ({symbol})")

    except Exception as e:
        print("Ошибка отправки в Telegram:", e)


# 🚀 Основной цикл
def main():
    global sent_tokens, token_prices

    print("🚀 Бот запущен, ловлю новые токены Solana...")

    while True:
        tokens = fetch_new_tokens()
        now = time.time()

        for token in tokens:
            address = token.get("baseToken", {}).get("address")
            if not address:
                continue

            # 📌 Новый токен
            if address not in sent_tokens:
                send_token_alert(token, "new")
                sent_tokens.add(address)
                price = fetch_token_price(address)
                token_prices[address] = {"price": price, "time": now}

                with open(SENT_FILE, "w") as f:
                    json.dump(list(sent_tokens), f)
                with open(PRICES_FILE, "w") as f:
                    json.dump(token_prices, f)

            else:
                # 📈 Проверяем рост цены
                old_data = token_prices.get(address)
                if old_data and now - old_data["time"] >= 300:  # 5 минут
                    old_price = old_data["price"]
                    new_price = fetch_token_price(address)

                    if old_price > 0:
                        change = ((new_price - old_price) / old_price) * 100
                        if change >= 20:
                            send_token_alert(token, round(change, 2))

                    token_prices[address] = {"price": new_price, "time": now}
                    with open(PRICES_FILE, "w") as f:
                        json.dump(token_prices, f)

        time.sleep(60)


if __name__ == "__main__":
    main()
