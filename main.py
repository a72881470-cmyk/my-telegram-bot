import os
import requests
from telegram import Bot
from telegram.ext import Updater, CommandHandler

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

bot = Bot(token=BOT_TOKEN)

DEX_API = "https://api.dexscreener.com/latest/dex/tokens/solana"

def start(update, context):
    update.message.reply_text("✅ Бот Solana запущен и мониторит новые токены!")

def check_new_tokens(context):
    try:
        response = requests.get(DEX_API)
        data = response.json()

        if "pairs" not in data:
            return

        for token in data["pairs"][:3]:  # первые 3 токена
            name = token.get("baseToken", {}).get("name", "Unknown")
            symbol = token.get("baseToken", {}).get("symbol", "?")
            price = token.get("priceUsd", "0")
            url = f"https://dexscreener.com/solana/{token.get('pairAddress')}"

            msg = (
                f"🚀 Новый токен на Solana\n"
                f"💎 {name} ({symbol})\n"
                f"💲 Цена: {price} USD\n"
                f"📊 Пара: {token.get('baseToken', {}).get('symbol')} / {token.get('quoteToken', {}).get('symbol')}\n"
                f"🔗 [DexScreener]({url})\n\n"
                f"💸 Погнали фармить деньги!"
            )

            bot.send_message(chat_id=CHANNEL_ID, text=msg, parse_mode="Markdown")

    except Exception as e:
        print("Ошибка при получении данных:", e)

def keep_alive(context):
    """Сообщение каждые 2 часа"""
    bot.send_message(chat_id=CHANNEL_ID, text="🤖 Я работаю, мониторю рынок...")

def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))

    job_queue = updater.job_queue

    # проверка новых токенов каждую минуту
    job_queue.run_repeating(check_new_tokens, interval=60, first=5)

    # сообщение "Я работаю" каждые 2 часа (7200 секунд)
    job_queue.run_repeating(keep_alive, interval=7200, first=10)

    print("✅ Бот Solana запущен и работает бесконечно")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
