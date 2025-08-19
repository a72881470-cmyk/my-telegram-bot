import requests
import time
import logging
import os
from datetime import datetime, timedelta

# === CONFIG ===
PING_TIMEOUT = 10
FETCH_INTERVAL = 60    # проверка раз в 60 сек
HEARTBEAT_INTERVAL = 3600  # каждые 3600 сек (1 час)

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
    """Получаем токены Solana с DexScreener"""
    url = "https://api.dexscreener.com/latest/dex/search?q=solana"
    pairs = []
    try:
        r = requests.get(url, timeout=PING_TIMEOUT)
        data = r.json()
        if "pairs" in data and data["pairs"]:
            for p in data["pairs"]:
                dex_id = (p.get("dexId") or "").lower()
                if dex_id in ["raydium", "orca", "meteora"]:
                    change15m = p.get("priceChange", {}).get("h15")
                    pairs.append({
                        "name": p.get("baseToken", {}).get("name"),
                        "symbol": p.get("baseToken", {}).get("symbol"),
                        "address": p.get("baseToken", {}).get("address"),
                        "dex": dex_id,
                        "liquidity": p.get("liquidity", {}).get("usd"),
                        "price": p.get("priceUsd"),
                        "change15m": change15m,
                        "url": p.get("url"),
                        "phantom": f"https://phantom.app/ul/browse/{p.get('baseToken', {}).get('address')}"
                    })
        else:
            logging.warning("DexScreener: пустой ответ")
    except Exception as e:
        logging.error(f"DexScreener fetch error: {e}")
    return pairs

# === PumpSwap ===
def fetch_from_pumpswap():
    """Получаем токены с PumpSwap"""
    url = "https://pumpportal.fun/api/trending"
    pairs = []
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=PING_TIMEOUT)
        data = r.json()
        if isinstance(data, list) and len(data) > 0:
            for p in data:
                addr = p.get("mint")
                pairs.append({
                    "name": p.get("name"),
                    "symbol": p.get("symbol"),
                    "address": addr,
                    "dex": "pumpswap",
                    "liquidity": None,
                    "price": None,
                    "change15m": None,
                    "url": f"https://dexscreener.com/solana/{addr}",
                    "phantom": f"https://phantom.app/ul/browse/{addr}"
                })
        else:
            logging.warning("pumpswap: API вернул пустой ответ или неверный формат")
    except Exception as e:
        logging.error(f"pumpswap fetch error: {e}")
    return pairs

# === Основной цикл ===
def main():
    logging.info("Starting token fetcher...")
    send_telegram_message("🚀 Бот запущен и слушает новые токены")

    last_heartbeat = datetime.now()
    seen_tokens = set()

    while True:
        all_tokens = []
        all_tokens.extend(fetch_from_dexscreener())
        all_tokens.extend(fetch_from_pumpswap())

        if all_tokens:
            logging.info(f"Найдено {len(all_tokens)} токенов")
            for t in all_tokens[:5]:  # первые 5
                token_id = f"{t['dex']}:{t['address']}"
                if token_id not in seen_tokens:
                    seen_tokens.add(token_id)

                    msg = f"🔹 [{t['dex'].upper()}] {t['symbol']} ({t['address']})\n"

                    # Цена
                    if t["price"]:
                        try:
                            price = float(t["price"])
                            msg += f"💵 Цена: ${price:.6f}\n"
                        except:
                            msg += f"💵 Цена: {t['price']}\n"

                    # Ликвидность
                    if t["liquidity"]:
                        try:
                            liquidity = float(t["liquidity"])
                            msg += f"💧 Ликвидность: ${liquidity:,.0f}\n"
                        except:
                            msg += f"💧 Ликвидность: {t['liquidity']}\n"

                    # Рост за 15 мин
                    if t["change15m"] is not None:
                        try:
                            change = float(t["change15m"])
                            if change > 0:
                                msg += f"📊 Рост за 15 мин: 🔺 {change:.2f}%\n"
                            elif change < 0:
                                msg += f"📊 Рост за 15 мин: 🔻 {change:.2f}%\n"
                            else:
                                msg += f"📊 Рост за 15 мин: ➖ 0.00%\n"
                        except:
                            msg += f"📊 Рост за 15 мин: {t['change15m']}\n"

                    msg += f"🔗 Dex: {t['url']}\n"
                    msg += f"👛 Phantom: {t['phantom']}"

                    logging.info(msg.replace("\n", " | "))
                    send_telegram_message(msg)
        else:
            logging.info("Новых токенов не найдено")

        # Heartbeat раз в час
        if datetime.now() - last_heartbeat >= timedelta(seconds=HEARTBEAT_INTERVAL):
            send_telegram_message("✅ Бот на связи")
            last_heartbeat = datetime.now()

        time.sleep(FETCH_INTERVAL)

if __name__ == "__main__":
    main()
