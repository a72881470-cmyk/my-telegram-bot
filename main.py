import os
import time
import requests
import logging
from datetime import datetime, timezone

# === Логирование ===
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# === Telegram ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def send_telegram(msg: str):
    if not BOT_TOKEN or not CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}
        )
    except Exception as e:
        logging.error(f"Ошибка отправки в Telegram: {e}")

# === Фильтры мемок (Solana) ===
NEW_MAX_AGE_MIN   = 5
MAX_LIQ_USD       = 15000
MAX_FDV_USD       = 3000000
MIN_TXNS_5M       = 20
MIN_BUYS_RATIO_5M = 0.6
MIN_PCHANGE_5M_BUY   = 8
MIN_PCHANGE_5M_ALERT = 12

# === Слежение и выход ===
TRAIL_START_PCT   = 20
TRAIL_GAP_PCT     = 15
MAX_DRAWNDOWN_PCT = 30
LIQ_DROP_RUG_PCT  = 50

# === DexScreener API ===
API_URL = "https://api.dexscreener.com/latest/dex/pairs/solana"

tracked_tokens = {}  # {addr: {"entry": price, "peak": price, "liq_peak": liquidity}}

def fetch_tokens():
    try:
        resp = requests.get(API_URL)
        data = resp.json()
        return data.get("pairs", [])
    except Exception as e:
        logging.error(f"Ошибка DexScreener: {e}")
        return []

def analyze_new_token(token):
    try:
        addr = token.get("baseToken", {}).get("address")
        name = token.get("baseToken", {}).get("name")
        symbol = token.get("baseToken", {}).get("symbol")
        url = token.get("url", "")
        liquidity = token.get("liquidity", {}).get("usd", 0)
        fdv = token.get("fdv", 0)
        price_usd = float(token.get("priceUsd", 0) or 0)
        txns = token.get("txns", {}).get("m5", {})
        buys = txns.get("buys", 0)
        sells = txns.get("sells", 0)
        pchange_5m = token.get("priceChange", {}).get("m5", 0)
        age = int((datetime.now(timezone.utc) - datetime.fromtimestamp(token["pairCreatedAt"]/1000, tz=timezone.utc)).total_seconds() / 60)

        if age > NEW_MAX_AGE_MIN: return None
        if liquidity > MAX_LIQ_USD: return None
        if fdv and fdv > MAX_FDV_USD: return None
        if buys + sells < MIN_TXNS_5M: return None
        if sells and (buys/(buys+sells)) < MIN_BUYS_RATIO_5M: return None

        signal = None
        if pchange_5m >= MIN_PCHANGE_5M_ALERT:
            signal = "📈 Растёт"
        elif pchange_5m >= MIN_PCHANGE_5M_BUY:
            signal = "🟢 Купить"

        if signal:
            msg = (
                f"{signal}\n\n"
                f"<b>{name} ({symbol})</b>\n"
                f"⏱ Возраст: {age} мин\n"
                f"💧 Ликвидность: ${liquidity:,.0f}\n"
                f"📊 FDV: ${fdv:,.0f}\n"
                f"📈 Рост 5м: {pchange_5m}%\n"
                f"🛒 Сделки 5м: {buys} / {sells}\n"
                f"💵 Цена: ${price_usd:.8f}\n"
                f"🔗 {url}"
            )
            send_telegram(msg)

            if signal == "🟢 Купить":
                tracked_tokens[addr] = {
                    "entry": price_usd,
                    "peak": price_usd,
                    "liq_peak": liquidity,
                    "url": url,
                    "symbol": symbol
                }
    except Exception as e:
        logging.error(f"Ошибка анализа токена: {e}")

def track_positions():
    to_remove = []
    for addr, t in tracked_tokens.items():
        try:
            resp = requests.get(f"{API_URL}/{addr}")
            data = resp.json()
            pairs = data.get("pairs", [])
            if not pairs: continue
            token = pairs[0]

            price = float(token.get("priceUsd", 0) or 0)
            liquidity = token.get("liquidity", {}).get("usd", 0)
            entry = t["entry"]
            peak = t["peak"]
            liq_peak = t["liq_peak"]

            change_from_entry = (price-entry)/entry*100 if entry else 0
            change_from_peak  = (price-peak)/peak*100 if peak else 0
            liq_drop = (liq_peak-liquidity)/liq_peak*100 if liq_peak else 0

            # обновляем пик
            if price > peak:
                tracked_tokens[addr]["peak"] = price
            if liquidity > liq_peak:
                tracked_tokens[addr]["liq_peak"] = liquidity

            # трейлинг
            if change_from_entry >= TRAIL_START_PCT:
                if change_from_peak <= -TRAIL_GAP_PCT:
                    send_telegram(f"⚠️ Продать {t['symbol']} — трейлинг-стоп\nЦена ${price:.8f}\n{t['url']}")
                    to_remove.append(addr)

            # стоп-лосс
            if change_from_entry <= -MAX_DRAWNDOWN_PCT:
                send_telegram(f"❌ Продать {t['symbol']} — стоп-лосс ({change_from_entry:.1f}%)\nЦена ${price:.8f}\n{t['url']}")
                to_remove.append(addr)

            # rug pull
            if liq_drop >= LIQ_DROP_RUG_PCT:
                send_telegram(f"💀 {t['symbol']} — ликвидность упала на {liq_drop:.1f}%\nЦена ${price:.8f}\n{t['url']}")
                to_remove.append(addr)

        except Exception as e:
            logging.error(f"Ошибка трекинга {addr}: {e}")

    for addr in to_remove:
        tracked_tokens.pop(addr, None)

def run_bot():
    send_telegram("🚀 Бот запущен. Ловим мемки Solana каждые 10 сек…")
    while True:
        tokens = fetch_tokens()
        for t in tokens:
            analyze_new_token(t)
        track_positions()
        time.sleep(10)

if __name__ == "__main__":
    run_bot()
