import os
import time
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv

# Загружаем настройки из .env
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# === Фильтры ===
NEW_MAX_AGE_MIN = int(os.getenv("NEW_MAX_AGE_MIN", 180))
MIN_LIQ_USD = int(os.getenv("MIN_LIQ_USD", 10000))
MAX_LIQ_USD = int(os.getenv("MAX_LIQ_USD", 5000000))
MAX_FDV_USD = int(os.getenv("MAX_FDV_USD", 50000000))
MIN_TXNS_5M = int(os.getenv("MIN_TXNS_5M", 10))
MIN_BUYS_RATIO_5M = float(os.getenv("MIN_BUYS_RATIO_5M", 0.45))
MIN_PCHANGE_5M_BUY = float(os.getenv("MIN_PCHANGE_5M_BUY", 1))
MIN_PCHANGE_5M_ALERT = float(os.getenv("MIN_PCHANGE_5M_ALERT", 5))

# === Сигналы ===
PUMP_ALERT_PCT = float(os.getenv("PUMP_ALERT_PCT", 100))
DROP_ALERT_PCT = float(os.getenv("DROP_ALERT_PCT", 100))
TRAIL_START_PCT = float(os.getenv("TRAIL_START_PCT", 20))
TRAIL_GAP_PCT = float(os.getenv("TRAIL_GAP_PCT", 15))
MAX_DRAWDOWN_PCT = float(os.getenv("MAX_DRAWDOWN_PCT", 30))
LIQ_DROP_RUG_PCT = float(os.getenv("LIQ_DROP_RUG_PCT", 50))

# === DexScreener API ===
DEX_API = "https://api.dexscreener.com/latest/dex/tokens/"

# Telegram API
def send_telegram(msg: str, buttons=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}
    if buttons:
        data["reply_markup"] = buttons
    try:
        r = requests.post(url, json=data, timeout=10)
        if r.status_code != 200:
            print(f"⚠ Ошибка Telegram: {r.text}")
    except Exception as e:
        print("⚠ Исключение Telegram:", e)


# Кнопка для покупки в Phantom
def phantom_button(token_address: str):
    return {
        "inline_keyboard": [
            [
                {
                    "text": "🔥 Купить в Phantom",
                    "url": f"https://phantom.app/ul/browse/{token_address}"
                }
            ]
        ]
    }


# Проверка токенов в сети Solana
def check_new_tokens():
    url = "https://api.dexscreener.com/latest/dex/search/?q=solana"
    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            print(f"⚠ Ошибка DexScreener: {r.status_code}")
            return

        data = r.json()
        if not data or "pairs" not in data:
            print("⚠ Пустой ответ DexScreener")
            return

        for pair in data["pairs"]:
            base = pair.get("baseToken", {})
            symbol = base.get("symbol", "?")
            address = base.get("address", "")
            price = float(pair.get("priceUsd") or 0)
            liq = float(pair.get("liquidity", {}).get("usd", 0))
            fdv = float(pair.get("fdv") or 0)
            created_at = pair.get("pairCreatedAt")
            url_dex = pair.get("url", "")

            # Возраст токена
            if isinstance(created_at, int):
                created_dt = datetime.fromtimestamp(created_at / 1000, tz=timezone.utc)
            else:
                created_dt = datetime.now(timezone.utc)
            age_min = (datetime.now(timezone.utc) - created_dt).total_seconds() / 60

            # Фильтры
            if age_min > NEW_MAX_AGE_MIN:
                continue
            if not (MIN_LIQ_USD <= liq <= MAX_LIQ_USD):
                continue
            if fdv > MAX_FDV_USD:
                continue

            # Сигнал
            msg = (
                f"🚀 Новый токен Solana!\n"
                f"🔹 *{symbol}*\n"
                f"💰 Цена: ${price:.6f}\n"
                f"💧 Ликвидность: ${liq:,.0f}\n"
                f"📊 FDV: ${fdv:,.0f}\n"
                f"⏱ Возраст: {age_min:.1f} мин\n"
                f"🌐 [DexScreener]({url_dex})"
            )
            print(msg)
            send_telegram(msg, buttons=phantom_button(address))

    except Exception as e:
        print("⚠ Ошибка при проверке токенов:", e)


# Основной цикл
def main():
    print("✅ Бот запущен")
    send_telegram("💸 Погнали фармить деньги!")

    last_ping = time.time()
    while True:
        check_new_tokens()

        # Каждые 2 часа сообщение "Я работаю"
        if time.time() - last_ping > 7200:
            send_telegram("⏱ Я работаю!")
            last_ping = time.time()

        time.sleep(60)


if __name__ == "__main__":
    main()
