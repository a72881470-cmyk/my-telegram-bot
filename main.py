import requests
import time
import logging
import json
from datetime import datetime, timedelta
import telegram

# 🔑 Настройки
API_KEY = "9aad437cea2b440e8ebf437a60a3d02e"
BOT_TOKEN = "ТВОЙ_TELEGRAM_BOT_TOKEN"
CHAT_ID = "ТВОЙ_CHAT_ID"

# Telegram бот
bot = telegram.Bot(token=BOT_TOKEN)

# Логирование
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

# Хранилище обработанных токенов
SEEN_TOKENS_FILE = "seen_tokens.json"
try:
    with open(SEEN_TOKENS_FILE, "r") as f:
        seen_tokens = set(json.load(f))
except:
    seen_tokens = set()

def save_seen_tokens():
    with open(SEEN_TOKENS_FILE, "w") as f:
        json.dump(list(seen_tokens), f)

# Проверка API ключа
def check_api_key():
    url = "https://public-api.birdeye.so/defi/tokenlist?offset=0&limit=1"
    headers = {"accept": "application/json", "x-chain": "solana", "X-API-KEY": API_KEY}
    r = requests.get(url, headers=headers)
    return r.status_code == 200

# Получить список токенов
def fetch_tokens():
    url = "https://public-api.birdeye.so/defi/tokenlist?offset=0&limit=20"
    headers = {"accept": "application/json", "x-chain": "solana", "X-API-KEY": API_KEY}
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        return r.json().get("data", {}).get("tokens", [])
    return []

# Получить инфо о токене
def fetch_token_info(address):
    url = f"https://public-api.birdeye.so/defi/price?address={address}"
    headers = {"accept": "application/json", "x-chain": "solana", "X-API-KEY": API_KEY}
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        return r.json().get("data", {})
    return {}

# Основная логика
def run_bot():
    logging.info("🚀 Бот запущен, ловлю новые токены Solana...")
    last_alive = time.time()

    while True:
        try:
            tokens = fetch_tokens()
            now = datetime.utcnow()

            for token in tokens:
                address = token.get("address")
                created_at = datetime.utcfromtimestamp(token.get("created_at", now.timestamp()) / 1000)

                # Проверка: токен не старше 3 часов
                if now - created_at > timedelta(hours=3):
                    continue

                # Новый токен
                if address not in seen_tokens:
                    seen_tokens.add(address)
                    save_seen_tokens()

                    info = fetch_token_info(address)
                    price = info.get("value", "N/A")
                    change_24h = info.get("priceChange24hPercent", 0)

                    msg = (
                        f"🆕 Новый токен Solana!\n\n"
                        f"🪙 {token.get('symbol')} ({address})\n"
                        f"💵 Цена: {price}\n"
                        f"📈 Рост 24ч: {change_24h:.2f}%\n\n"
                        f"🔍 [Мониторинг](https://birdeye.so/token/{address}?chain=solana)\n"
                        f"👛 [Phantom Wallet](https://phantom.app/ul/browse/{address})"
                    )
                    bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")

                # Если рост > 30%
                info = fetch_token_info(address)
                change_24h = info.get("priceChange24hPercent", 0)
                if change_24h > 30:
                    msg = (
                        f"🚨 Рост токена!\n\n"
                        f"🪙 {token.get('symbol')} ({address})\n"
                        f"📈 Рост: {change_24h:.2f}%\n\n"
                        f"🔍 [Мониторинг](https://birdeye.so/token/{address}?chain=solana)\n"
                        f"👛 [Phantom Wallet](https://phantom.app/ul/browse/{address})"
                    )
                    bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")

            # Каждые 2 часа сообщение что бот жив
            if time.time() - last_alive >= 7200:
                bot.send_message(chat_id=CHAT_ID, text="🤖 Бот работает и мониторит новые токены!")
                last_alive = time.time()

        except Exception as e:
            logging.error(f"Ошибка: {e}")

        time.sleep(60)  # Проверка раз в минуту


if __name__ == "__main__":
    if check_api_key():
        run_bot()
    else:
        logging.error("❌ API ключ недействителен, бот остановлен.")
