import requests
import time
from datetime import datetime, timezone
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

API_URL = "https://api.dexscreener.com/latest/dex/search?q=solana"
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", 30))

NEW_MAX_AGE_MIN = int(os.getenv("NEW_MAX_AGE_MIN", 180))
MIN_LIQ_USD = int(os.getenv("MIN_LIQ_USD", 10000))
MAX_LIQ_USD = int(os.getenv("MAX_LIQ_USD", 5000000))

MIN_PCHANGE_5M_ALERT = int(os.getenv("MIN_PCHANGE_5M_ALERT", 10))
BIG_PUMP_ALERT = int(os.getenv("BIG_PUMP_ALERT", 100))
BIG_DUMP_ALERT = int(os.getenv("BIG_DUMP_ALERT", 50))

PHANTOM_DEPOSIT_USD = int(os.getenv("PHANTOM_DEPOSIT_USD", 20))

tracked_tokens = {}

def send_telegram(msg: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(url, data={"chat_id": CHAT_ID, "text": msg}, timeout=10)
        if r.status_code != 200:
            print(f"⚠ Ошибка TG: {r.text}")
    except Exception as e:
        print("⚠ Ошибка отправки в TG:", e)

def check_new_tokens():
    try:
        r = requests.get(API_URL, timeout=10)
        if r.status_code != 200:
            print(f"⚠ Ошибка API: {r.status_code}")
            return

        data = r.json()
        if "pairs" not in data:
            print("⚠ Dexscreener вернул пусто")
            return

        for pair in data["pairs"]:
            created_at = pair.get("pairCreatedAt")
            if not created_at:
                continue

            age_min = (datetime.now(timezone.utc) - datetime.fromtimestamp(created_at/1000, tz=timezone.utc)).total_seconds() / 60
            if age_min > NEW_MAX_AGE_MIN:
                continue

            liq_usd = float(pair.get("liquidity", {}).get("usd", 0))
            if liq_usd < MIN_LIQ_USD or liq_usd > MAX_LIQ_USD:
                continue

            price = float(pair.get("priceUsd") or 0)
            pchange_5m = float(pair.get("priceChange", {}).get("m5", 0))
            symbol = pair.get("baseToken", {}).get("symbol", "?")
            address = pair.get("baseToken", {}).get("address", "?")
            url_dex = pair.get("url", "")

            # 🚀 сигнал на новый токен
            if abs(pchange_5m) >= MIN_PCHANGE_5M_ALERT and address not in tracked_tokens:
                msg = (
                    f"🚀 Новый токен на Solana\n\n"
                    f"🪙 {symbol} ({address})\n"
                    f"💰 Цена: {price:.6f} USD\n"
                    f"📈 Рост (5м): {pchange_5m}%\n"
                    f"🌐 Dex: {url_dex}\n"
                    f"👛 Phantom: https://phantom.app/ul/buy/solana/{address}?amount={PHANTOM_DEPOSIT_USD}"
                )
                send_telegram(msg)
                tracked_tokens[address] = {"peak": price, "symbol": symbol, "url": url_dex}

            # отслеживание роста/падения
            if address in tracked_tokens:
                peak = tracked_tokens[address]["peak"]
                if price > peak:
                    tracked_tokens[address]["peak"] = price
                    if ((price - peak) / peak) * 100 > BIG_PUMP_ALERT:
                        send_telegram(f"🚀 {symbol} ВЗОРВАЛСЯ +100%!\nЦена: {price:.6f} USD\n🔗 {url_dex}")

                drawdown = 100 * (1 - price / tracked_tokens[address]["peak"])
                if drawdown > BIG_DUMP_ALERT:
                    send_telegram(f"⚠ {symbol} Обвалился {drawdown:.1f}%\nЦена: {price:.6f} USD\n🔗 {url_dex}")
                    del tracked_tokens[address]

    except Exception as e:
        print("⚠ Ошибка:", e)


def main():
    print("✅ Бот Solana запущен")
    while True:
        check_new_tokens()
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
