import os
import time
import requests
import logging
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone

# --------------------------
# Загрузка .env и логирование
# --------------------------
load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# --------------------------
# Переменные окружения
# --------------------------
try:
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
except Exception as e:
    print(TELEGRAM_BOT_TOKEN)
    print('e')
TELEGRAM_CHAT_IDS = [c.strip() for c in os.getenv("TELEGRAM_CHAT_ID", "").split(",") if c.strip()]

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("Не задан TELEGRAM_BOT_TOKEN в .env")
if not TELEGRAM_CHAT_IDS:
    raise ValueError("Не задан TELEGRAM_CHAT_ID в .env (можно несколько, через запятую)")

# Фильтры/параметры
MIN_LIQ_USD        = float(os.getenv("MIN_LIQ_USD", 5000))         # мин. ликвидность $
MIN_VOL_5M         = float(os.getenv("MIN_VOL_5M", 3000))          # мин. объём за 5м $
MIN_BUYS_5M        = int(os.getenv("MIN_BUYS_5M", 20))             # мин. покупок за 5м
MIN_PCHANGE_5M     = float(os.getenv("MIN_PCHANGE_5M", 5))         # мин. рост за 5м %
QUOTE_PREF         = [x.strip().upper() for x in os.getenv("QUOTE_PREF", "USDC,SOL").split(",")]
NEW_MAX_AGE_MIN    = int(os.getenv("NEW_MAX_AGE_MIN", 10))         # макс. возраст «новой монеты», мин
POLL_SECONDS       = int(os.getenv("POLL_SECONDS", 60))            # период опроса, сек
HEARTBEAT_HOURS    = float(os.getenv("HEARTBEAT_HOURS", 2))        # раз в сколько часов слать «я работаю»
SELL_DROP_PCT      = float(os.getenv("SELL_DROP_PCT", 7))          # падение от пика для SELL сигнала, %
TRACK_TTL_HOURS    = float(os.getenv("TRACK_TTL_HOURS", 24))       # сколько часов держать монету в трекинге

# DexScreener API (Solana)
API_URL = "https://api.dexscreener.com/latest/dex/search?q=solana"

# Память
seen_tokens = set()        # чтобы не дублировать BUY
tracked = {}               # pairAddress -> { 'symbol','name','address','buy_price','peak','last','first_seen','sell_notified' }
last_status_time = datetime.now(timezone.utc)

# --------------------------
# Утилиты
# --------------------------
def fmt_usd(x: float) -> str:
    try:
        if x >= 1:
            return f"{x:,.2f}$"
        return f"{x:,.6f}$"
    except Exception:
        return f"{x}$"

def send_telegram(message: str):
    """Отправить сообщение во все чаты."""
    for chat_id in TELEGRAM_CHAT_IDS:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML", "disable_web_page_preview": True}
        try:
            r = requests.post(url, json=payload, timeout=10)
            if r.status_code != 200:
                logging.error("TG error %s: %s", chat_id, r.text)
        except Exception as e:
            logging.error("TG error %s: %s", chat_id, e)

def get_pairs():
    """Загрузить пары Solana из DexScreener."""
    try:
        r = requests.get(API_URL, timeout=15)
        if r.status_code == 200:
            return r.json().get("pairs", []) or []
        logging.error("DexScreener API status: %s", r.status_code)
    except Exception as e:
        logging.error("DexScreener API error: %s", e)
    return []

def eligible(token: dict) -> bool:
    """Фильтруем новые монеты по условиям."""
    try:
        liq = float(token.get("liquidity", {}).get("usd") or 0)
        vol5 = float(token.get("volume", {}).get("m5") or 0)
        buys5 = int(token.get("txns", {}).get("m5", {}).get("buys") or 0)
        age_min = int(token.get("age") or 0)
        pchg5 = float(token.get("priceChange", {}).get("m5") or 0)
        quote = (token.get("quoteToken", {}) or {}).get("symbol", "").upper()

        return (
            age_min <= NEW_MAX_AGE_MIN
            and liq >= MIN_LIQ_USD
            and vol5 >= MIN_VOL_5M
            and buys5 >= MIN_BUYS_5M
            and pchg5 >= MIN_PCHANGE_5M
            and (quote in QUOTE_PREF)
        )
    except Exception:
        return False

def build_links(token: dict):
    """Ссылки DexScreener + Phantom."""
    pair_addr = token.get("pairAddress", "")
    base = token.get("baseToken", {}) or {}
    token_addr = base.get("address", "")

    dex_link = f"https://dexscreener.com/solana/{pair_addr}" if pair_addr else ""
    phantom_link = f"https://phantom.app/ul/browse/{token_addr}" if token_addr else ""
    return dex_link, phantom_link

def now_utc():
    return datetime.now(timezone.utc)

# --------------------------
# Основная логика
# --------------------------
def main():
    global last_status_time

    logging.info("🚀 Бот запущен. Ожидание сигналов...")
    send_telegram("🤖 Бот запущен! Жду новые монеты по Solana…")

    while True:
        start_ts = time.monotonic()
        pairs = get_pairs()

        # BUY-сигналы для новых монет
        for t in pairs:
            if not eligible(t):
                continue

            pair_id = t.get("pairAddress")
            if not pair_id or pair_id in seen_tokens:
                continue

            seen_tokens.add(pair_id)

            base = t.get("baseToken", {}) or {}
            name = base.get("name", "") or ""
            symb = base.get("symbol", "") or ""
            token_addr = base.get("address", "") or ""

            price = float(t.get("priceUsd") or 0)
            pchg5 = float(t.get("priceChange", {}).get("m5") or 0)
            liq = float(t.get("liquidity", {}).get("usd") or 0)
            vol5 = float(t.get("volume", {}).get("m5") or 0)
            buys5 = int(t.get("txns", {}).get("m5", {}).get("buys") or 0)

            dex_link, phantom_link = build_links(t)

            msg = (
                "🚀 <b>Новая монета (BUY-сигнал)</b>\n"
                f"🏷 <b>{name} ({symb})</b>\n"
                f"💰 Цена: <b>{fmt_usd(price)}</b>\n"
                f"📈 Рост (5м): <b>{pchg5:.2f}%</b>\n"
                f"💵 Ликвидность: <b>{liq:,.0f}$</b>\n"
                f"📊 Объём (5м): <b>{vol5:,.0f}$</b>\n"
                f"🛒 Покупок (5м): <b>{buys5}</b>\n"
                f"🔗 <a href='{dex_link}'>DexScreener</a>\n"
                f"👛 <a href='{phantom_link}'>Открыть в Phantom</a>"
            )
            send_telegram(msg)
            logging.info("BUY signal: %s (%s)", name, pair_id)

            # добавляем в трекинг для последующего SELL
            tracked[pair_id] = {
                "symbol": symb,
                "name": name,
                "address": token_addr,
                "buy_price": price,
                "peak": price if price > 0 else 0,
                "last": price,
                "first_seen": now_utc(),
                "sell_notified": False,
            }

        # Обновление трекинга и SELL-сигналы
        # создаём индекс текущих цен по парам, чтобы не искать по всему списку
        by_pair = {p.get("pairAddress"): p for p in pairs if p.get("pairAddress")}

        to_delete = []
        for pid, info in tracked.items():
            # TTL очистка
            if now_utc() - info["first_seen"] > timedelta(hours=TRACK_TTL_HOURS):
                to_delete.append(pid)
                continue

            cur = by_pair.get(pid)
            if not cur:
                # пары нет в выдаче — просто ждём, может появится снова
                continue

            price = float(cur.get("priceUsd") or 0)
            if price <= 0:
                continue

            # обновляем пик
            if price > info["peak"]:
                info["peak"] = price

            info["last"] = price

            # условие SELL: падение от пика на SELL_DROP_PCT%
            if not info["sell_notified"] and info["peak"] > 0:
                drop_pct = (1 - price / info["peak"]) * 100
                if drop_pct >= SELL_DROP_PCT:
                    dex_link, phantom_link = build_links(cur)
                    msg = (
                        "⚠️ <b>SELL-сигнал</b>\n"
                        f"🏷 <b>{info['name']} ({info['symbol']})</b>\n"
                        f"📉 Текущее падение от пика: <b>{drop_pct:.2f}%</b>\n"
                        f"💰 Текущая цена: <b>{fmt_usd(price)}</b>\n"
                        f"🔗 <a href='{dex_link}'>DexScreener</a>\n"
                        f"👛 <a href='{phantom_link}'>Открыть в Phantom</a>"
                    )
                    send_telegram(msg)
                    info["sell_notified"] = True
                    logging.info("SELL signal: %s (%s) drop=%.2f%%", info["name"], pid, drop_pct)

        # очистка старых
        for pid in to_delete:
            tracked.pop(pid, None)

        # heartbeat раз в HEARTBEAT_HOURS
        if now_utc() - last_status_time >= timedelta(hours=HEARTBEAT_HOURS):
            send_telegram("✅ Я работаю. Мониторю новые монеты и цены…")
            last_status_time = now_utc()

        # спим оставшееся время
        elapsed = time.monotonic() - start_ts
        sleep_for = max(1.0, POLL_SECONDS - elapsed)
        time.sleep(sleep_for)


if __name__ == "__main__":
    main()

