import requests
import time
import logging
import os
from datetime import datetime, timedelta

# === CONFIG ===
PING_TIMEOUT = 10
FETCH_INTERVAL = 60   # проверка токенов раз в 60 сек
HEARTBEAT_INTERVAL = 3600  # раз в час сообщение "бот на связи"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID")

# === Логгер ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

# === Telegram ===
def send_telegram_message(text: str):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "disable_web_page_preview": True}
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        logging.error(f"Telegram send error: {e}")

# === DexScreener ===
def fetch_from_dexscreener():
    url = "https://api.dexscreener.com/latest/dex/search?q=solana"
    pairs = []
    try:
        r = requests.get(url, timeout=PING_TIMEOUT)
        data = r.json()
        if "pairs" in data and data["pairs"]:
            for p in data["pairs"]:
                dex_id = (p.get("dexId") or "").lower()
                if dex_id in ["raydium", "orca", "meteora"]:
                    pairs.append({
                        "name": p.get("baseToken", {}).get("name"),
                        "symbol": p.get("baseToken", {}).get("symbol"),
                        "address": p.get("baseToken", {}).get("address"),
                        "dex": dex_id,
                        "liquidity": p.get("liquidity", {}).get("usd"),
                        "url": p.get("url")
                    })
    except Exception as e:
        logging.error(f"DexScreener fetch error: {e}")
    return pairs

# === PumpSwap ===
def fetch_from_pumpswap():
    url = "https://pumpportal.fun/api/trending"
    pairs = []
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=PING_TIMEOUT)
        data = r.json()
        if isinstance(data, list) and len(data) > 0:
            for p in data:
                pairs.append({
                    "name": p.get("name"),
                    "symbol": p.get("symbol"),
                    "address": p.get("mint"),
                    "dex": "pumpswap",
                    "liquidity": None,
                    "url": f"https://dexscreener.com/solana/{p.get('mint')}"
                })
    except Exception as e:
        logging.error(f"pumpswap fetch error: {e}")
    return pairs

# === Основной цикл ===
def main():
    logging.info("Starting token fetcher...")
    send_telegram_message("🚀 Бот запущен и слушает новые токены")

    last_heartbeat = datetime.now()
    seen_tokens = set()  # чтобы не спамить одинаковыми токенами

    while True:
        all_tokens = []
        all_tokens.extend(fetch_from_dexscreener())
        all_tokens.extend(fetch_from_pumpswap())

        if all_tokens:
            logging.info(f"Найдено {len(all_tokens)} токенов")
            for t in all_tokens[:5]:
                token_id = f"{t['dex']}:{t['address']}"
                if token_id not in seen_tokens:  # только новые токены
                    seen_tokens.add(token_id)
                    msg = f"[{t['dex']}] {t['symbol']} ({t['address']})\n{t['url']}"
                    logging.info(msg)
                    send_telegram_message(msg)
        else:
            logging.info("Новых токенов не найдено")

        # heartbeat раз в час
        if datetime.now() - last_heartbeat >= timedelta(seconds=HEARTBEAT_INTERVAL):
            send_telegram_message("✅ Бот на связи")
            last_heartbeat = datetime.now()

        time.sleep(FETCH_INTERVAL)

if __name__ == "__main__":
    main()
