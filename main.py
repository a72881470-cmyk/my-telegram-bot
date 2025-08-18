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
PING_INTERVAL = int(os.getenv("PING_INTERVAL", 10))   # 👈 сделал 10 секунд
PING_TIMEOUT  = int(os.getenv("PING_TIMEOUT", 12))

# === Опционально: GPT-анализ ===
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL   = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# === Проверка DexScreener ===
DEXSCREENER_API = "https://api.dexscreener.com/latest/dex/tokens/solana"

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
    print("🚀 Bot запущен и слушает Solana мемки...")
    while True:
        pairs = fetch_new_tokens()
        memecoins = filter_memecoins(pairs)
        if memecoins:
            print("🎯 Найдены новые мемки:")
            for m in memecoins:
                print(m)
        else:
            print("⏳ Пока чисто, жду дальше...")
        time.sleep(PING_INTERVAL)
