import requests
import time
import logging
from datetime import datetime, timedelta

# === CONFIG ===
BOT_TOKEN = "ТОКЕН_ТЕЛЕГРАМ_БОТА"
CHAT_ID = "ID_ТВОЕГО_ЧАТА"

FETCH_INTERVAL = 60  # проверка каждую минуту
BOOST_CHECK_MINUTES = 10
BOOST_PERCENT = 20  # рост на 20% за 10 минут
STATUS_INTERVAL = 3600  # 1 час

# === Логгер ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

# === Хранилище цен (для буста) ===
price_history = {}
last_status_time = datetime.utcnow()

# === Telegram ===
def send_tg(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"})
    except Exception as e:
        logging.error(f"Ошибка отправки в Telegram: {e}")

# === DexScreener ===
def fetch_from_dexscreener():
    url = "https://api.dexscreener.com/latest/dex/search?q=solana"
    pairs = []
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        if "pairs" in data and data["pairs"]:
            for p in data["pairs"]:
                dex_id = (p.get("dexId") or "").lower()
                price = safe_float(p.get("priceUsd"))
                change15m = safe_float(p.get("priceChange", {}).get("m15"))

                token = {
                    "name": p.get("baseToken", {}).get("name"),
                    "symbol": p.get("baseToken", {}).get("symbol"),
                    "address": p.get("baseToken", {}).get("address"),
                    "dex": dex_id,
                    "price": price,
                    "change15m": change15m,
                    "url": p.get("url"),
                    "phantom": f"https://phantom.app/ul/browse/{p.get('baseToken', {}).get('address')}"
                }
                pairs.append(token)
    except Exception as e:
        logging.error(f"DexScreener fetch error: {e}")
    return pairs

def safe_float(val):
    try:
        return float(val)
    except:
        return None

# === Проверка буста ===
def check_boost(token):
    addr = token["address"]
    now = datetime.utcnow()
    price = token["price"]

    if not price:
        return None

    if addr in price_history:
        old_price, ts = price_history[addr]
        if now - ts >= timedelta(minutes=BOOST_CHECK_MINUTES):
            change = ((price - old_price) / old_price) * 100 if old_price > 0 else 0
            if change >= BOOST_PERCENT:
                return f"🚀 <b>ОБНАРУЖЕН БУСТ МОНЕТА!</b>\n" \
                       f"<b>{token['symbol']}</b> ({token['address']})\n" \
                       f"DEX: {token['dex']}\n" \
                       f"Цена: ${price:.6f} (+{change:.2f}% за {BOOST_CHECK_MINUTES} мин)\n" \
                       f"<a href='{token['url']}'>DexScreener</a>\n" \
                       f"<a href='{token['phantom']}'>Phantom</a>"
            else:
                price_history[addr] = (price, now)
    else:
        price_history[addr] = (price, now)

    return None

# === Основной цикл ===
def main():
    global last_status_time
    send_tg("✅ Бот запущен и отслеживает новые монеты")

    while True:
        tokens = fetch_from_dexscreener()

        # раз в час - сигнал "бот на связи"
        now = datetime.utcnow()
        if (now - last_status_time).total_seconds() >= STATUS_INTERVAL:
            send_tg("⏰ Бот на связи")
            last_status_time = now

        if tokens:
            for t in tokens[:5]:
                msg = f"🆕 <b>Новая монета</b>\n" \
                      f"<b>{t['symbol']}</b> ({t['address']})\n" \
                      f"DEX: {t['dex']}\n" \
                      f"Цена: ${t['price']:.6f}\n" \
                      f"Δ15m: {t['change15m']}%\n" \
                      f"<a href='{t['url']}'>DexScreener</a>\n" \
                      f"<a href='{t['phantom']}'>Phantom</a>"
                send_tg(msg)

                # проверка на буст
                boost_msg = check_boost(t)
                if boost_msg:
                    send_tg(boost_msg)

        time.sleep(FETCH_INTERVAL)


if __name__ == "__main__":
    main()
