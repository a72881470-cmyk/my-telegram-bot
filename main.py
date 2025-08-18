import os
import time
import requests
import threading
from dotenv import load_dotenv
from flask import Flask

# === Загружаем .env ===
load_dotenv()

# === Системные ===
PORT          = int(os.getenv("PORT", 8080))
PING_INTERVAL = int(os.getenv("PING_INTERVAL", 10))   # каждые 10 сек проверка
PING_TIMEOUT  = int(os.getenv("PING_TIMEOUT", 12))

# === Telegram ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram(text: str):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"[ERROR] Telegram error: {e}")

# === DexScreener API ===
def fetch_new_tokens():
    try:
        url = "https://api.dexscreener.com/latest/dex/search?q=solana"
        r = requests.get(url, timeout=PING_TIMEOUT)
        data = r.json()
        if "pairs" not in data:
            return []
        return data["pairs"]
    except Exception as e:
        print(f"[ERROR] DexScreener fetch error: {e}")
        return []

# === Flask healthcheck server ===
app = Flask(__name__)

@app.route("/")
def health():
    return "✅ Bot is running", 200

def run_server():
    app.run(host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    # Запускаем веб-сервер в отдельном потоке
    threading.Thread(target=run_server, daemon=True).start()

    send_telegram("🚀 Бот запущен и теперь ловит ВСЕ монеты Solana!")
    last_status_time = time.time()

    while True:
        pairs = fetch_new_tokens()

        if pairs:
            for p in pairs:
                try:
                    symbol = p.get("baseToken", {}).get("symbol", "N/A")
                    age_min = p.get("ageMinutes", "?")
                    liquidity_usd = p.get("liquidity", {}).get("usd", 0)
                    fdv = p.get("fdv", 0)
                    price_change5m = p.get("priceChange", {}).get("m5", 0)
                    txns5m = p.get("txns", {}).get("m5", {}).get("buys", 0) + p.get("txns", {}).get("m5", {}).get("sells", 0)

                    url_dex = p.get("url", "")
                    contract_address = p.get("baseToken", {}).get("address", "")
                    url_phantom = f"https://phantom.com/tokens/solana/{contract_address}"

                    msg = (
                        f"🎯 <b>{symbol}</b>\n"
                        f"⏱ Возраст: {age_min} мин\n"
                        f"💧 Ликвидность: ${liquidity_usd}\n"
                        f"📊 FDV: ${fdv}\n"
                        f"📈 Изм. цены (5м): {price_change5m}%\n"
                        f"🛒 Транзакции (5м): {txns5m}\n"
                        f"🔗 <a href='{url_dex}'>DexScreener</a> | <a href='{url_phantom}'>Phantom</a>"
                    )

                    send_telegram(msg)
                except Exception as e:
                    print(f"[ERROR] Format send error: {e}")

        else:
            print("⏳ Пока чисто, жду дальше...")  

        # раз в 15 минут бот шлет "я жив"
        if time.time() - last_status_time > 900:
            send_telegram("⏱ Я на связи, продолжаю сканировать рынок Solana...")
            last_status_time = time.time()

        time.sleep(PING_INTERVAL)
