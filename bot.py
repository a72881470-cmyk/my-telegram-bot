import os
import json
import time
import logging
import requests
import asyncio
from telegram import Bot

# ---------- Загрузка конфигурации ----------
with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

DEPOSIT_USD = config["deposit_usd"]
MAX_TRADES = config["max_trades"]
MIN_LIQ_USD = config["min_liquidity_usd"]
MIN_VOL_1H = config["min_volume_usd_1h"]
MIN_PC_5M = config["min_price_change_5m"]
MIN_PC_1H = config["min_price_change_1h"]
POLL_INTERVAL = config["poll_interval_seconds"]
PHANTOM_LINK = config["phantom_link"]
NETWORK = config["network"]
CHAT_ID = config["chat_id"]

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")  # токен храним в переменных окружения

# ---------- Логирование ----------
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("dexbot")

# ---------- Dexscreener API ----------
API_URL = f"https://api.dexscreener.com/latest/dex/search?q={NETWORK}"
sent_cache = {}

def phantom_url(mint: str) -> str:
    return f"https://phantom.app/asset/{NETWORK}/{mint}"

def fetch_pairs():
    try:
        r = requests.get(API_URL, timeout=15)
        r.raise_for_status()
        data = r.json()
        return data.get("pairs", [])
    except Exception as e:
        log.error(f"Ошибка запроса Dexscreener: {e}")
        return []

def filter_pairs(pairs):
    results = []
    for p in pairs:
        try:
            liq = ((p.get("liquidity") or {}).get("usd")) or 0
            vol1h = (p.get("volume") or {}).get("h1") or 0
            pc5 = (p.get("priceChange") or {}).get("m5") or 0
            pc1 = (p.get("priceChange") or {}).get("h1") or 0

            if liq < MIN_LIQ_USD:
                continue
            if vol1h < MIN_VOL_1H:
                continue
            if pc5 < MIN_PC_5M and pc1 < MIN_PC_1H:
                continue

            results.append(p)
        except Exception:
            continue
    return results

def format_message(p):
    base = p.get("baseToken", {})
    sym = base.get("symbol", "?")
    price = p.get("priceUsd", "?")
    liq = (p.get("liquidity") or {}).get("usd", "?")
    vol = p.get("volume") or {}
    pc = p.get("priceChange") or {}
    mint = base.get("address", "")
    dex_url = p.get("url", "https://dexscreener.com/")
    phantom = phantom_url(mint) if PHANTOM_LINK and mint else ""

    text = (
        f"🚀 <b>{sym}</b> ({NETWORK})\n"
        f"💰 Депозит: ${DEPOSIT_USD}\n"
        f"💵 Ликвидность: ${int(liq):,}\n"
        f"📈 Объём 1ч: ${int(vol.get('h1',0)):,}\n"
        f"📊 Рост: 5м {pc.get('m5','?')}% | 1ч {pc.get('h1','?')}%\n"
        f"🔗 <a href='{dex_url}'>Dexscreener</a>\n"
    )
    if phantom:
        text += f"👜 <a href='{phantom}'>Phantom</a>\n"
    if mint:
        text += f"🧾 Mint: <code>{mint}</code>\n"
    return text

# ---------- Основной цикл ----------
async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    while True:
        pairs = fetch_pairs()
        filtered = filter_pairs(pairs)

        # сортировка по росту за 5 мин
        filtered.sort(key=lambda x: (x.get("priceChange") or {}).get("m5", 0), reverse=True)

        count = 0
        for p in filtered:
            mint = (p.get("baseToken") or {}).get("address", "")
            now = time.time()
            last_sent = sent_cache.get(mint, 0)

            if now - last_sent < 3600:  # не слать повтор в течение часа
                continue

            msg = format_message(p)
            try:
                await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="HTML", disable_web_page_preview=True)
                sent_cache[mint] = now
                count += 1
            except Exception as e:
                log.error(f"Ошибка отправки сообщения: {e}")

            if count >= MAX_TRADES:
                break

        await asyncio.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    asyncio.run(main())
