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
seen_tokens = set()  # список уже отправленных токенов


def send_alert(token_name, growth, price, pair, dex_link, phantom_link):
    """
    Отправляет сообщение в Telegram (с антиспамом и без повторов).
    """
    global last_alert_time

    # Фильтр по росту
    if growth < 50:
        print(f"⏳ {token_name} пропущен, рост {growth}% < 50%")
        return

    # Проверка на дубликаты
    if token_name in seen_tokens:
        print(f"⚠ {token_name} уже отправляли, пропуск...")
        return

    now = time.time()
    if now - last_alert_time >= ALERT_COOLDOWN:
        bot.send_message(
            CHAT_ID,
            f"🟢 Новый токен найден!\n\n"
            f"🔹 Название: {token_name}\n"
            f"📈 Рост: {growth}%\n"
            f"💲 Цена: {price}\n"
            f"🔄 Пара: {pair}\n"
            f"🌐 DexScreener: {dex_link}\n"
            f"👛 Phantom: {phantom_link}"
        )
        seen_tokens.add(token_name)  # помечаем как отправленный
        last_alert_time = now
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
        # Пример события: нашли новый токен
        token_name = "TEST"
        growth = 120  # %
        price = "0.000123"
        pair = "TEST/USDC"
        dex_link = "https://dexscreener.com/solana/xxx"
        phantom_link = "https://phantom.app/xxx"

        send_alert(token_name, growth, price, pair, dex_link, phantom_link)

        time.sleep(30)  # проверка каждые 30 секунд (можешь увеличить)


if __name__ == "__main__":
    main()
