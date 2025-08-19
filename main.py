import requests
import time
import logging
from datetime import datetime, timedelta, timezone

# ======================
# 🔧 Настройки
# ======================
TG_TOKEN = "ТОКЕН_ТЕЛЕГРАМ"
TG_CHAT_ID = "ID_ТЕЛЕГРАМ"

STATUS_INTERVAL = 3600       # каждые 1 час бот пишет "на связи"
BOOST_CHECK_MINUTES = 5      # проверка роста монеты
BOOST_PERCENT = 5            # 🚀 сигнал если рост >5% за 5 минут

# Фильтры из твоего файла
NEW_MAX_AGE_MIN = 180        # не старше 3 часов
MIN_LIQ_USD = 10000          # минимум $10k ликвидность
MAX_LIQ_USD = 5000000        # максимум $5m ликвидность
MAX_FDV_USD = 50000000       # FDV до $50m
MIN_TXNS_5M = 10             # минимум 10 сделок за 5 минут
MIN_BUYS_RATIO_5M = 0.45     # минимум 45% покупок
MIN_PCHANGE_5M_BUY = 1       # минимум рост 1% за 5 минут

# ======================
# 🗂 Хранилище данных
# ======================
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
        requests.post(url, data={
            "chat_id": TG_CHAT_ID,
            "text": msg,
            "parse_mode": "HTML"
        }, timeout=10)
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

            if r.status_code == 404:
                logging.warning(f"❌ Нет данных для {dex} (404)")
                continue
            if r.status_code != 200:
                logging.error(f"Ошибка запроса {dex}: {r.status_code}")
                continue

            data = r.json()
            for pair in data.get("pairs", []):
                try:
                    token = {
                        "symbol": pair.get("baseToken", {}).get("symbol", "N/A"),
                        "address": pair.get("baseToken", {}).get("address", "N/A"),
                        "price": float(pair.get("priceUsd", 0) or 0),
                        "dex": pair.get("dexId", dex),
                        "url": f"https://dexscreener.com/solana/{pair.get('pairAddress', '')}",
                        "phantom": f"https://phantom.app/ul/browse/{pair.get('pairAddress', '')}",
                        "liquidity": pair.get("liquidity", {}).get("usd", 0),
                        "fdv": pair.get("fdv", 0),
                        "txns5m": pair.get("txns", {}).get("m5", {}).get("buys", 0)
                                + pair.get("txns", {}).get("m5", {}).get("sells", 0),
                        "buys_ratio": (
                            pair.get("txns", {}).get("m5", {}).get("buys", 0) /
                            max(1, pair.get("txns", {}).get("m5", {}).get("buys", 0)
                                + pair.get("txns", {}).get("m5", {}).get("sells", 0))
                        ),
                        "age_min": (datetime.now(timezone.utc) -
                                    datetime.fromisoformat(pair.get("pairCreatedAt", datetime.now().isoformat())
                                                           .replace("Z", "+00:00"))).total_seconds() / 60
                    }

                    # фильтры
                    if not (MIN_LIQ_USD <= token["liquidity"] <= MAX_LIQ_USD):
                        continue
                    if token["fdv"] > MAX_FDV_USD:
                        continue
                    if token["txns5m"] < MIN_TXNS_5M:
                        continue
                    if token["buys_ratio"] < MIN_BUYS_RATIO_5M:
                        continue
                    if token["age_min"] > NEW_MAX_AGE_MIN:
                        continue

                    tokens.append(token)

                except Exception as e:
                    logging.warning(f"Ошибка обработки пары {dex}: {e}")

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
                    f"🚀 <b>СИГНАЛ: БУСТ МОНЕТЫ!</b>\n"
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
    send_tg("✅ Бот запущен и отслеживает монеты со всех DEX'ов")

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
