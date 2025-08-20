import os
import time
import threading
import telebot
from dotenv import load_dotenv

# Загружаем .env
load_dotenv()

# Настройки из .env
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

bot = telebot.TeleBot(BOT_TOKEN)

# --- Анти-спам ---
last_alert_time = 0
ALERT_COOLDOWN = 60  # минимум 60 секунд между сообщениями


def send_alert(text: str):
    """
    Отправляет сообщение в Telegram, но не чаще чем раз в минуту.
    """
    global last_alert_time
    now = time.time()
    if now - last_alert_time >= ALERT_COOLDOWN:
        bot.send_message(CHAT_ID, text)
        last_alert_time = now
        time.sleep(1)  # задержка для анти-спама Telegram
    else:
        print("⏳ Сообщение пропущено (анти-спам)")


def worker_status():
    """
    Отправляет сообщение "Я работаю" каждые 2 часа
    """
    while True:
        bot.send_message(CHAT_ID, "✅ Я работаю, слежу за рынком! 💰")
        time.sleep(7200)  # 2 часа


def main():
    # При запуске
    bot.send_message(CHAT_ID, "🚀 Погнали фармить деньги 💸")

    # Запуск отдельного потока для сообщений "Я работаю"
    threading.Thread(target=worker_status, daemon=True).start()

    # --- Тут твоя логика ловли токенов ---
    while True:
        # пример события: нашли новый токен
        token_name = "TEST"
        growth = 120  # %
        price = "0.000123"
        pair = "TEST/USDC"
        dex_link = "https://dexscreener.com/solana/xxx"
        phantom_link = "https://phantom.app/xxx"

        send_alert(
            f"🟢 Новый токен найден!\n\n"
            f"🔹 Название: {token_name}\n"
            f"📈 Рост: {growth}%\n"
            f"💲 Цена: {price}\n"
            f"🔄 Пара: {pair}\n"
            f"🌐 DexScreener: {dex_link}\n"
            f"👛 Phantom: {phantom_link}"
        )

        time.sleep(10)  # эмуляция работы


if __name__ == "__main__":
    main()
