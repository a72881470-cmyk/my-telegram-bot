import requests
import time
import logging

# 🔑 Твой API ключ
API_KEY = "9aad437cea2b440e8ebf437a60a3d02e"

# Логирование
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

# Проверка API-ключа перед запуском
def check_api_key():
    url = "https://public-api.birdeye.so/defi/tokenlist?offset=0&limit=1"
    headers = {
        "accept": "application/json",
        "x-chain": "solana",
        "X-API-KEY": API_KEY
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            logging.info("✅ API ключ рабочий! Бот запускается...")
            return True
        else:
            logging.error(f"❌ Ошибка API: {response.status_code}, ответ: {response.text}")
            return False
    except Exception as e:
        logging.error(f"❌ Ошибка подключения: {e}")
        return False


# Основная логика бота (ловим новые токены Solana)
def run_bot():
    logging.info("🚀 Бот запущен, ловлю новые токены Solana...")
    url = "https://public-api.birdeye.so/defi/tokenlist?offset=0&limit=5"
    headers = {
        "accept": "application/json",
        "x-chain": "solana",
        "X-API-KEY": API_KEY
    }

    while True:
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                tokens = data.get("data", {}).get("tokens", [])
                for token in tokens:
                    logging.info(f"🪙 Найден токен: {token.get('symbol')} ({token.get('address')})")
            else:
                logging.error(f"Ошибка API: {response.status_code}, ответ: {response.text}")
        except Exception as e:
            logging.error(f"Ошибка: {e}")

        time.sleep(10)  # Проверяем каждые 10 секунд


if __name__ == "__main__":
    if check_api_key():
        run_bot()
    else:
        logging.error("❌ API ключ недействителен, бот остановлен.")
