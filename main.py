import requests
import time
import logging

# === CONFIG ===
PING_TIMEOUT = 10
FETCH_INTERVAL = 60  # каждые 60 сек

# === Логгер ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

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
                dex_id = p.get("dexId", "").lower()
                if dex_id in ["raydium", "orca", "meteora"]:
                    pairs.append({
                        "name": p.get("baseToken", {}).get("name"),
                        "symbol": p.get("baseToken", {}).get("symbol"),
                        "address": p.get("baseToken", {}).get("address"),
                        "dex": dex_id,
                        "liquidity": p.get("liquidity", {}).get("usd"),
                        "url": p.get("url")
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
        r = requests.get(url, timeout=PING_TIMEOUT)
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
        else:
            logging.warning("pumpswap: API вернул пустой ответ или неверный формат")
    except Exception as e:
        logging.error(f"pumpswap fetch error: {e}")
    return pairs

# === Основной цикл ===
def main():
    logging.info("Starting token fetcher...")
    while True:
        all_tokens = []
        all_tokens.extend(fetch_from_dexscreener())
        all_tokens.extend(fetch_from_pumpswap())

        if all_tokens:
            logging.info(f"Найдено {len(all_tokens)} токенов")
            for t in all_tokens[:5]:  # показываем первые 5
                logging.info(f"[{t['dex']}] {t['symbol']} ({t['address']}) {t['url']}")
        else:
            logging.info("Новых токенов не найдено")

        time.sleep(FETCH_INTERVAL)

if __name__ == "__main__":
    main()
