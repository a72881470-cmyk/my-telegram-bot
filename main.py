import os
import time
import requests
import threading
from dotenv import load_dotenv
from flask import Flask
from waitress import serve

# === Загружаем .env ===
load_dotenv()

# === Фильтры / параметры ===
NEW_MAX_AGE_MIN   = 180        # не старше 3 часов
MIN_LIQ_USD       = 15000      # минимум $15k ликвидность
MAX_LIQ_USD       = 300000     # максимум $300k ликвидность
MAX_FDV_USD       = 15000000   # FDV до $15M
MIN_TXNS_5M       = 20         # минимум 20 сделок за 5 минут
MIN_BUYS_RATIO_5M = 0.55       # минимум 55% покупок
MIN_PCHANGE_5M_BUY= 3          # минимум рост 3% за 5м
MIN_PCHANGE_5M_ALERT=10        # 🚀 сигнал если рост >10% за 5м

# === Слежение и выход ===
TRAIL_START_PCT   = 20
TRAIL_GAP_PCT     = 15
MAX_DRAWNDOWN_PCT = 30
LIQ_DROP_RUG_PCT  = 50

# === Системные ===
PORT          = int(os.getenv("PORT", 8080))
PING_INTERVAL = int(os.getenv("PING_INTERVAL", 30))
PING_TIMEOUT  = int(os.getenv("PING_TIMEOUT", 12))

# === Telegram ===
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN")
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
    pairs = []
    urls = {
        "default": "https://api.dexscreener.com/latest/dex/search?q=solana",
        "pumpswap": "https://api.dexscreener.com/latest/dex/pairs/solana/pumpswap"
    }
    for label, url in urls.items():
        try:
            r = requests.get(url, timeout=PING_TIMEOUT)
            data = r.json()
            if "pairs" in data:
                for p in data["pairs"]:
                    p["_source"] = label  # отмечаем источник
                    pairs.append(p)
        except Exception as e:
            print(f"[ERROR] DexScreener fetch error from {url}: {e}")
    return pairs

# === Flask healthcheck server ===
app = Flask(__name__)

@app.route("/")
def health():
    return "✅ Bot is running", 200

def run_server():
    serve(app, host="0.0.0.0", port=PORT)

# === MAIN ===
if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()
    send_telegram("🚀 Бот запущен и фильтрует Solana-мемы по условиям!")

    sent_tokens = set()
    last_status_time = time.time()

    while True:
        try:
            pairs = fetch_new_tokens()

            if pairs:
                for p in pairs:
                    try:
                        contract_address = p.get("baseToken", {}).get("address", "")
                        if not contract_address or contract_address in sent_tokens:
                            continue

                        symbol = p.get("baseToken", {}).get("symbol", "N/A")

                        # возраст
                        pair_created_at = p.get("pairCreatedAt")
                        age_min = int((time.time()*1000 - pair_created_at) / 1000 / 60) if pair_created_at else 999999  

                        # ликвидность / FDV
                        liquidity_usd = round(p.get("liquidity", {}).get("usd", 0), 2)
                        fdv = p.get("fdv", 0)

                        # активность
                        buys_5m  = p.get("txns", {}).get("m5", {}).get("buys", 0)
                        sells_5m = p.get("txns", {}).get("m5", {}).get("sells", 0)
                        txns5m   = buys_5m + sells_5m
                        buy_ratio= (buys_5m / txns5m) if txns5m > 0 else 0
                        price_change5m = p.get("priceChange", {}).get("m5", 0)

                        # фильтры
                        if (
                            age_min <= NEW_MAX_AGE_MIN and
                            MIN_LIQ_USD <= liquidity_usd <= MAX_LIQ_USD and
                            fdv <= MAX_FDV_USD and
                            txns5m >= MIN_TXNS_5M and
                            buy_ratio >= MIN_BUYS_RATIO_5M and
                            price_change5m >= MIN_PCHANGE_5M_BUY
                        ):
                            url_dex     = p.get("url", "")
                            url_phantom = f"https://phantom.com/tokens/solana/{contract_address}"

                            alert_emoji = "🚀" if price_change5m >= MIN_PCHANGE_5M_ALERT else "✅"
                            source_note = "🔥PUMPSWAP🔥" if p.get("_source") == "pumpswap" else ""

                            msg = (
                                f"{alert_emoji} <b>{symbol}</b> {source_note}\n"
                                f"⏱ Возраст: {age_min} мин\n"
                                f"💧 Ликвидность: ${liquidity_usd}\n"
                                f"📊 FDV: ${fdv}\n"
                                f"📈 Изм. цены (5м): {price_change5m}%\n"
                                f"🛒 Транзакции (5м): {txns5m} ({buy_ratio:.0%} покупок)\n"
                                f"🔗 <a href='{url_dex}'>DexScreener</a> | <a href='{url_phantom}'>Phantom</a>"
                            )
                            send_telegram(msg)
                            sent_tokens.add(contract_address)

            else:
                print("⏳ Пока чисто, жду дальше...")  

            # Раз в 15 мин — "я жив"
            if time.time() - last_status_time > 900:
                send_telegram("⏱ Я на связи, продолжаю сканировать рынок Solana...")
                last_status_time = time.time()

        except Exception as e:
            print(f"[MAIN LOOP ERROR] {e}")

        time.sleep(PING_INTERVAL)
