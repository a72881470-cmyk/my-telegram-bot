import os
import time
import requests
import logging
from dotenv import load_dotenv

# === Загружаем .env ===
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# === Фильтры ===
MIN_LIQ_USD = float(os.getenv("MIN_LIQ_USD", 300))
MIN_PCHANGE_5M = float(os.getenv("MIN_PCHANGE_5M", 25))
NEW_MAX_AGE_MIN = int(os.getenv("NEW_MAX_AGE_MIN", 10))
MIN_TRADES_5M = int(os.getenv("MIN_TRADES_5M", 10))
POLL_SECONDS = int(os.getenv("POLL_SECONDS", 30))

# === Логирование ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Хранилище отправленных токенов
sent_tokens = set()

# === Telegram ===
def send_telegram(msg: str):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        logging.error(f"Ошибка отправки в Telegram: {e}")

# === Pump.fun API ===
def get_new_pumpfun_tokens():
    url = "https://frontend-api.pump.fun/coins/"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        coins = resp.json()

        fresh = []
        for c in coins:
            created = c.get("created_timestamp", 0)
            age_min = (time.time() - created) / 60 if created else 9999

            if age_min <= NEW_MAX_AGE_MIN:  # только новые
                fresh.append({
                    "symbol": c.get("symbol", "???"),
                    "address": c.get("mint"),
                    "age_min": round(age_min, 1)
                })
        return fresh
    except Exception as e:
        logging.error(f"Pump.fun error: {e}")
        return []

# === Dexscreener API ===
def get_token_info(address: str):
    url = f"https://api.dexscreener.com/latest/dex/tokens/{address}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return None
        data = resp.json()
        pairs = data.get("pairs", [])
        if not pairs:
            return None
        return pairs[0]  # первую пару
    except Exception as e:
        logging.error(f"Dexscreener error: {e}")
        return None

# === Основной цикл ===
def main():
    logging.info("🚀 Бот запущен. Мониторинг мемкоинов Solana…")
    while True:
        try:
            tokens = get_new_pumpfun_tokens()
            logging.info(f"🔎 Найдено {len(tokens)} свежих токенов на Pump.fun")

            for t in tokens:
                # если сигнал по этому токену уже был → пропускаем
                if t["address"] in sent_tokens:
                    continue

                info = get_token_info(t["address"])
                if not info:
                    continue

                liq = info.get("liquidity", {}).get("usd", 0)
                trades_5m = info.get("txns", {}).get("m5", {}).get("buys", 0) + info.get("txns", {}).get("m5", {}).get("sells", 0)
                change_5m = info.get("priceChange", {}).get("m5", 0)

                if liq >= MIN_LIQ_USD and change_5m >= MIN_PCHANGE_5M and trades_5m >= MIN_TRADES_5M:
                    phantom_url = f"https://phantom.com/tokens/solana/{t['address']}"
                    msg = (
                        f"🚀 *Новый мемкоин Solana!*\n\n"
                        f"🪙 {t['symbol']}\n"
                        f"⏱ Возраст: {t['age_min']} мин\n"
                        f"💧 Ликвидность: ${liq:,.0f}\n"
                        f"📈 Рост (5м): {change_5m:.2f}%\n"
                        f"⚡ Сделок (5м): {trades_5m}\n\n"
                        f"[DexScreener]({info.get('url')}) | [Phantom]({phantom_url})"
                    )
                    send_telegram(msg)
                    sent_tokens.add(t["address"])  # сохраняем в антиспам
                    logging.info(f"✅ Сигнал отправлен: {t['symbol']} ({t['address']})")

        except Exception as e:
            logging.error(f"Ошибка цикла: {e}")

        time.sleep(POLL_SECONDS)

if __name__ == "__main__":
    main()
