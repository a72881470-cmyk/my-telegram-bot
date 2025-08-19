import requests
import time
import logging
from datetime import datetime, timedelta, timezone

# ======================
# 🔧 Настройки
# ======================
TG_TOKEN = "ТОКЕН_ТЕЛЕГРАМ"
TG_CHAT_ID = "ID_ТЕЛЕГРАМ"
STATUS_INTERVAL = 3600  # каждые 1 час бот пишет "на связи"
BOOST_CHECK_MINUTES = 10  # проверка роста монеты
BOOST_PERCENT = 30        # % роста для сигнала буста

# Храним цены монет для проверки роста
price_history = {}
last_status_time = datetime.now(timezone.utc)

# DEX'ы для мониторинга
DEX_LIST = [
    "pumpswap", "raydium", "orca", "meteora",
    "pumpfun", "meteora-dbc", "fluxbeam"
]

# ======================
# 📩 Отправка сообщений
# ======================
def send_tg(msg: str):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": TG_CHAT_ID, "text": msg, "parse_mode": "HTML"})
    except Exception as e:
        logging.error(f"Ошибка отправки в Telegram: {e}")

# ======================
# 📊 Получение монет с DexScreener
# ======================
def fetch_from_dexscreener():
    tokens = []
    for dex in DEX_LIST:
        try:
            url = f"https://api.dexscreener.com/latest/dex/search/?q={dex}"
            r = requests.get(url, timeout=10)
            if r.status_code != 200:
                logging.error(f"Ошибка запроса {dex}: {r.status_code}")
                continue

            data = r.json()
            for pair in data.get("pairs", []):
                tokens.append({
                    "symbol": pair.get("baseToken", {}).get("symbol", "N/A"),
                    "address": pair.get("baseToken", {}).get("address", "N/A"),
                    "price": float(pair.get("priceUsd", 0) or 0),
                    "dex": pair.get("dexId", "N/A"),
                    "url": f"https://dexscreener.com/solana/{pair.get('pairAddress', '')}",
                    "phantom": f"https://phantom.app/ul/browse/{pair.get('pairAddress', '')}"
                })
        except Exception as e:
            logging.error(f"DexScreener fetch error {dex}: {e}")
    return tokens

# ======================
# 🚀 Проверка на буст монеты
# ======================
def check_boost(token):
    addr = token["address"]
    now = datetime.now(timezone.utc)
    price = token["price"]

    if not price or price <= 0:
        return None

    if addr in price_history:
        old_price, ts = price_history[addr]
        if now - ts >= timedelta(minutes=BOOST_CHECK_MINUTES):
            change = ((price - old_price) / old_price) * 100 if old_price > 0 else 0
            if change >= BOOST_PERCENT:
                return (
                    f"🚀 <b>ОБНАРУЖЕН БУСТ МОНЕТА!</b>\n"
                    f"<b>{token['symbol']}</b> ({token['address']})\n"
                    f"DEX: {token['dex']}\n"
                    f"Цена: ${price:.6f} (+{change:.2f}% за {BOOST_CHECK_MINUTES} мин)\n"
                    f"<a href='{token['url']}'>DexScreener</a>\n"
                    f"<a href='{token['phantom']}'>Phantom</a>"
                )
            else:
                price_history[addr] = (price, now)
    else:
        price_history[addr] = (price, now)

    return None

# ======================
# 🔄 Основной цикл
# ======================
def main():
    global last_status_time
    send_tg("✅ Бот запущен и отслеживает новые монеты со всех DEX'ов")

    while True:
        tokens = fetch_from_dexscreener()

        now = datetime.now(timezone.utc)
        if (now - last_status_time).total_seconds() >= STATUS_INTERVAL:
            send_tg("⏰ Бот на связи")
            last_status_time = now

        for token in tokens:
            boost_msg = check_boost(token)
            if boost_msg:
                send_tg(boost_msg)

        time.sleep(30)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logging.info("Starting Container")
    main()
