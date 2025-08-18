import os
import time
import requests
from dotenv import load_dotenv

# === Загружаем .env ===
load_dotenv()

# === Фильтры мемок (Solana) ===
NEW_MAX_AGE_MIN   = int(os.getenv("NEW_MAX_AGE_MIN", 8))
MAX_LIQ_USD       = float(os.getenv("MAX_LIQ_USD", 25000))
MAX_FDV_USD       = float(os.getenv("MAX_FDV_USD", 3000000))
MIN_TXNS_5M       = int(os.getenv("MIN_TXNS_5M", 15))
MIN_BUYS_RATIO_5M = float(os.getenv("MIN_BUYS_RATIO_5M", 0.55))
MIN_PCHANGE_5M_BUY   = float(os.getenv("MIN_PCHANGE_5M_BUY", 4))
MIN_PCHANGE_5M_ALERT = float(os.getenv("MIN_PCHANGE_5M_ALERT", 12))

# === Слежение и выход ===
TRAIL_START_PCT   = float(os.getenv("TRAIL_START_PCT", 20))
TRAIL_GAP_PCT     = float(os.getenv("TRAIL_GAP_PCT", 15))
MAX_DRAWNDOWN_PCT = float(os.getenv("MAX_DRAWNDOWN_PCT", 30))
LIQ_DROP_RUG_PCT  = float(os.getenv("LIQ_DROP_RUG_PCT", 50))

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

def filter_memecoins(pairs):
    result = []
    for p in pairs:
        try:
            age_min = p.get("ageMinutes", 9999)
            liquidity_usd = p.get("liquidity", {}).get("usd", 0)
            fdv = p.get("fdv", 0)
            txns5m = p.get("txns", {}).get("m5", {}).get("buys", 0) + p.get("txns", {}).get("m5", {}).get("sells", 0)
            buys_ratio = p.get("txns", {}).get("m5", {}).get("buys", 0) / max(1, txns5m)
            price_change5m = p.get("priceChange", {}).get("m5", 0)

            if (age_min <= NEW_MAX_AGE_MIN and
                liquidity_usd <= MAX_LIQ_USD and
                fdv <= MAX_FDV_USD and
                txns5m >= MIN_TXNS_5M and
                buys_ratio >= MIN_BUYS_RATIO_5M and
                price_change5m >= MIN_PCHANGE_5M_BUY):

                result.append({
                    "symbol": p.get("baseToken", {}).get("symbol"),
                    "age_min": age_min,
                    "liq": liquidity_usd,
                    "fdv": fdv,
                    "txns5m": txns5m,
                    "buys_ratio": round(buys_ratio, 2),
                    "price_change5m": price_change5m,
                    "url": p.get("url")
                })
        except Exception:
            continue
    return result

if __name__ == "__main__":
    send_telegram("🚀 Бот запущен и готов ловить мемкоины Solana!")
    last_status_time = time.time()

    while True:
        pairs = fetch_new_tokens()
        memecoins = filter_memecoins(pairs)

        if memecoins:
            for m in memecoins:
                msg = (
                    f"🎯 <b>{m['symbol']}</b>\n"
                    f"⏱ Возраст: {m['age_min']} мин\n"
                    f"💧 Ликвидность: ${m['liq']}\n"
                    f"📊 FDV: ${m['fdv']}\n"
                    f"📈 Изм. цены (5м): {m['price_change5m']}%\n"
                    f"🛒 Транзакции (5м): {m['txns5m']} (buys ratio {m['buys_ratio']})\n"
                    f"🔗 {m['url']}"
                )
                send_telegram(msg)
        else:
            print("⏳ Пока чисто, жду дальше...")  # 👈 теперь только в консоль

        # раз в 15 минут бот шлет "я жив"
        if time.time() - last_status_time > 900:
            send_telegram("⏱ Я на связи, продолжаю сканировать рынок Solana...")
            last_status_time = time.time()

        time.sleep(PING_INTERVAL)
