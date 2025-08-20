import os
import time
import threading
import telebot
import requests
from dotenv import load_dotenv

# Загружаем .env
load_dotenv()

# Настройки из .env
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

bot = telebot.TeleBot(BOT_TOKEN)

# --- Анти-спам ---
last_alert_time = 0
ALERT_COOLDOWN = 30  # минимум 30 секунд между сообщениями

# --- Список уже отправленных токенов ---
sent_tokens = set()


def send_alert(text: str, token_name: str):
    """
    Отправляет сообщение в Telegram (если токен не дублируется и не чаще чем раз в минуту).
    """
    global last_alert_time

    if token_name in sent_tokens:
        print(f"⚠ {token_name} уже отправляли, пропуск...")
        return

    now = time.time()
    if now - last_alert_time >= ALERT_COOLDOWN:
        bot.send_message(CHAT_ID, text, disable_web_page_preview=False)
        last_alert_time = now
        sent_tokens.add(token_name)
        print(f"✅ Отправили токен: {token_name}")
    else:
        print("⏳ Сообщение пропущено (анти-спам)")


def worker_status():
    """
    Отправляет сообщение "Я работаю" каждые 2 часа
    """
    while True:
        bot.send_message(CHAT_ID, "✅ Я работаю, слежу за рынком! 💰")
        time.sleep(7200)  # 2 часа


def fetch_new_tokens():
    """
    Берем новые пары с DexScreener API (Solana)
    """
    url = "https://api.dexscreener.com/latest/dex/tokens/solana"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()

        if "pairs" not in data:
            return []

        return data["pairs"][:5]  # Берем только топ-5 последних
    except Exception as e:
        print("Ошибка API:", e)
        return []


def main():
    # При запуске
    bot.send_message(CHAT_ID, "🚀 Погнали фармить 💰")

    # Запуск отдельного потока для сообщений "Я работаю"
    threading.Thread(target=worker_status, daemon=True).start()

    # Основной цикл
    while True:
        pairs = fetch_new_tokens()

        for p in pairs:
            token_name = p.get("baseToken", {}).get("name", "Unknown")
            growth = p.get("priceChange", {}).get("h1", 0)  # рост за 1 час %
            price = p.get("priceUsd", "?")
            pair = f"{p.get('baseToken', {}).get('symbol', '')}/{p.get('quoteToken', {}).get('symbol', '')}"
            dex_link = p.get("url", "https://dexscreener.com/")
            phantom_link = f"https://phantom.app/ul/browse/{dex_link}"

            send_alert(
                f"🟢 Новый токен найден!\n\n"
                f"🔹 Название: {token_name}\n"
                f"📈 Рост (1ч): {growth}%\n"
                f"💲 Цена: {price}\n"
                f"🔄 Пара: {pair}\n"
                f"🌐 DexScreener: {dex_link}\n"
                f"👛 Phantom: {phantom_link}",
                token_name
            )

        time.sleep(60)  # проверка раз в минуту


if __name__ == "__main__":
    main()
