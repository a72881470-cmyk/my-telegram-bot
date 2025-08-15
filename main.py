import os
import time
import logging
import requests
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
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_IDS = [c.strip() for c in os.getenv("TELEGRAM_CHAT_ID", "").split(",") if c.strip()]

# Фильтры (могут быть переопределены из .env)
MIN_LIQ_USD        = float(os.getenv("MIN_LIQ_USD", 500))
MIN_VOL_5M         = float(os.getenv("MIN_VOL_5M", 100))
MIN_BUYS_5M        = int(os.getenv("MIN_BUYS_5M", 5))
MIN_PCHANGE_5M     = float(os.getenv("MIN_PCHANGE_5M", 1))
QUOTE_PREF         = [x.strip().upper() for x in os.getenv("QUOTE_PREF", "SOL").split(",") if x.strip()]

# Параметры работы
POLL_SECONDS         = int(os.getenv("POLL_SECONDS", 60))
HEARTBEAT_HOURS      = float(os.getenv("HEARTBEAT_HOURS", 2))
SELL_DROP_PCT        = float(os.getenv("SELL_DROP_PCT", 7))           # SELL при падении от пика
TRACK_TTL_HOURS      = float(os.getenv("TRACK_TTL_HOURS", 24))        # сколько держать монету в трекинге
REPEAT_ALERT_STEP_PCT= float(os.getenv("REPEAT_ALERT_STEP_PCT", 5))   # повторный алерт при росте ещё на X% от прошлой цены-алерта

TRACK_TTL_SEC        = int(TRACK_TTL_HOURS * 3600)

# Dexscreener
API_URL = "https://api.dexscreener.com/latest/dex/search?q=solana"

# --------------------------
# Внутренняя память
# --------------------------
# tracked[pair] = {
#   'symbol','name','address',
#   'first_seen': dt,
#   'first_alert_time': dt|None,
#   'last_alert_price': float|None,
#   'peak': float,
#   'last_price': float,
#   'sell_notified': bool
# }
tracked = {}
last_heartbeat = datetime.now(timezone.utc)

# --------------------------
# Утилиты
# --------------------------
def now_utc():
    return datetime.now(timezone.utc)

def fmt_usd(x: float) -> str:
    try:
        if x >= 1:
            return f"{x:,.2f}$"
        return f"{x:,.6f}$"
    except Exception:
        return f"{x}$"

def send_telegram(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_IDS:
        return
    for chat_id in TELEGRAM_CHAT_IDS:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": int(chat_id) if str(chat_id).lstrip("-").isdigit() else chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        try:
            r = requests.post(url, json=payload, timeout=10)
            if r.status_code != 200:
                logging.error("Telegram error %s: %s", chat_id, r.text)
        except Exception as e:
            logging.error("Telegram error %s: %s", chat_id, e)

def get_pairs():
    try:
        r = requests.get(API_URL, timeout=15)
        if r.status_code == 200:
            return r.json().get("pairs", []) or []
        logging.error("DexScreener API status: %s", r.status_code)
    except Exception as e:
        logging.error("DexScreener API error: %s", e)
    return []

def build_links(token: dict):
    pair_addr = token.get("pairAddress", "")
    base = token.get("baseToken", {}) or {}
    token_addr = base.get("address", "")
    dex_link = f"https://dexscreener.com/solana/{pair_addr}" if pair_addr else ""
    # Универсальная ссылка на токен в Phantom
    phantom_link = f"https://phantom.app/ul/browse/{token_addr}" if token_addr else ""
    return dex_link, phantom_link

def eligible_growth(token: dict) -> bool:
    """Фильтруем по росту и базовым метрикам. Возраст не ограничиваем — как ты просил."""
    try:
        liq = float(token.get("liquidity", {}).get("usd") or 0)
        vol5 = float(token.get("volume", {}).get("m5") or 0)
        buys5 = int(token.get("txns", {}).get("m5", {}).get("buys") or 0)
        pchg5 = float(token.get("priceChange", {}).get("m5") or 0)
        quote = (token.get("quoteToken", {}) or {}).get("symbol", "").upper()
        return (
            pchg5 >= MIN_PCHANGE_5M
            and liq >= MIN_LIQ_USD
            and vol5 >= MIN_VOL_5M
            and buys5 >= MIN_BUYS_5M
            and (quote in QUOTE_PREF if QUOTE_PREF else True)
        )
    except Exception:
        return False

# --------------------------
# Логика алертов
# --------------------------
def maybe_send_growth_alert(pid: str, t: dict) -> None:
    """Первичный и повторный алерт на рост."""
    base = t.get("baseToken", {}) or {}
    name = base.get("name", "") or ""
    symb = base.get("symbol", "") or ""

    price = float(t.get("priceUsd") or 0)
    if price <= 0:
        return

    pchg5 = float(t.get("priceChange", {}).get("m5") or 0)
    liq = float(t.get("liquidity", {}).get("usd") or 0)
    vol5 = float(t.get("volume", {}).get("m5") or 0)
    buys5 = int(t.get("txns", {}).get("m5", {}).get("buys") or 0)
    dex_link, phantom_link = build_links(t)

    info = tracked.setdefault(pid, {
        "symbol": symb,
        "name": name,
        "address": base.get("address", ""),
        "first_seen": now_utc(),
        "first_alert_time": None,
        "last_alert_price": None,
        "peak": 0.0,
        "last_price": 0.0,
        "sell_notified": False,
    })

    # обновляем пик/последнюю цену
    info["last_price"] = price
    if price > info["peak"]:
        info["peak"] = price
        # если пик обновился — снова разрешаем SELL-сигнал в будущем
        # (на случай, если ранее уже был sell_notified=True)
        # но лучше не трогать флаг, чтобы не спамить — оставим как есть

    # Первичный алерт?
    if info["first_alert_time"] is None:
        msg = (
            "🚀 <b>Рост на Solana</b>\n"
            f"🏷 <b>{name} ({symb})</b>\n"
            f"💰 Цена: <b>{fmt_usd(price)}</b>\n"
            f"📈 Рост (5м): <b>{pchg5:.2f}%</b>\n"
            f"💵 Ликвидность: <b>{liq:,.0f}$</b>\n"
            f"📊 Объём (5м): <b>{vol5:,.0f}$</b>\n"
            f"🛒 Покупок (5м): <b>{buys5}</b>\n"
            f"🔗 <a href='{dex_link}'>Dexscreener</a>\n"
            f"👛 <a href='{phantom_link}'>Открыть в Phantom</a>"
        )
        send_telegram(msg)
        logging.info("Growth alert (first): %s (%s) +%.2f%%", name, pid, pchg5)
        info["first_alert_time"] = now_utc()
        info["last_alert_price"] = price
        return

    # Повторный алерт? (цена выросла ещё на REPEAT_ALERT_STEP_PCT% от последней цены-алерта)
    last_alert_price = info.get("last_alert_price") or price
    step_threshold_price = last_alert_price * (1 + REPEAT_ALERT_STEP_PCT / 100.0)
    if price >= step_threshold_price:
        gain_from_last = (price / last_alert_price - 1) * 100.0
        msg = (
            "📈 <b>Повторный рост</b>\n"
            f"🏷 <b>{name} ({symb})</b>\n"
            f"⬆️ С момента прошлого алерта: <b>{gain_from_last:.2f}%</b>\n"
            f"💰 Цена: <b>{fmt_usd(price)}</b>\n"
            f"🔗 <a href='{dex_link}'>Dexscreener</a>\n"
            f"👛 <a href='{phantom_link}'>Открыть в Phantom</a>"
        )
        send_telegram(msg)
        logging.info("Growth alert (repeat): %s (%s) +%.2f%% from last", name, pid, gain_from_last)
        info["last_alert_price"] = price  # сдвигаем ступеньку

def maybe_send_sell_alert(pid: str) -> None:
    """SELL-сигнал при падении от пика >= SELL_DROP_PCT%."""
    info = tracked.get(pid)
    if not info or info["sell_notified"]:
        return
    peak = info.get("peak", 0.0) or 0.0
    last = info.get("last_price", 0.0) or 0.0
    if peak <= 0 or last <= 0:
        return
    drop_pct = (1 - last / peak) * 100.0
    if drop_pct >= SELL_DROP_PCT:
        # ссылки
        dex_link = f"https://dexscreener.com/solana/{pid}"
        phantom_link = f"https://phantom.app/ul/browse/{info.get('address','')}"
        msg = (
            "⚠️ <b>SELL-сигнал</b>\n"
            f"🏷 <b>{info['name']} ({info['symbol']})</b>\n"
            f"📉 Падение от пика: <b>{drop_pct:.2f}%</b>\n"
            f"💰 Текущая цена: <b>{fmt_usd(last)}</b>\n"
            f"🔗 <a href='{dex_link}'>Dexscreener</a>\n"
            f"👛 <a href='{phantom_link}'>Открыть в Phantom</a>"
        )
        send_telegram(msg)
        logging.info("SELL alert: %s (%s) drop=%.2f%%", info["name"], pid, drop_pct)
        info["sell_notified"] = True

# --------------------------
# Основной цикл
# --------------------------
def main():
    global last_heartbeat

    logging.info("🚀 Бот запущен. Ожидание сигналов...")

    while True:
        started = time.monotonic()
        try:
            # чистим старые треки по TTL
            cutoff = now_utc() - timedelta(seconds=TRACK_TTL_SEC)
            for pid, info in list(tracked.items()):
                if info["first_seen"] < cutoff:
                    tracked.pop(pid, None)

            pairs = get_pairs()
            if not pairs:
                logging.info("⏳ Нет данных от Dexscreener, жду...")
            found = 0

            # индекс по pairAddress для быстрого доступа в SELL
            by_pair = {p.get("pairAddress"): p for p in pairs if p.get("pairAddress")}

            # алерты на рост
            for t in pairs:
                if not eligible_growth(t):
                    continue
                pid = t.get("pairAddress")
                if not pid:
                    continue
                # обновляем трекинг и проверяем алерты
                maybe_send_growth_alert(pid, t)
                found += 1

            if found == 0:
                logging.info("⏳ Жду сигналы...")

            # SELL-проверка по всем, кого трекаем
            for pid, info in list(tracked.items()):
                cur = by_pair.get(pid)
                if cur:
                    price = float(cur.get("priceUsd") or 0)
                    if price > 0:
                        info["last_price"] = price
                        if price > info.get("peak", 0.0):
                            info["peak"] = price
                maybe_send_sell_alert(pid)

            # Heartbeat
            if now_utc() - last_heartbeat >= timedelta(hours=HEARTBEAT_HOURS):
                send_telegram("✅ Я работаю. Мониторю пары на рост/падение…")
                last_heartbeat = now_utc()

        except Exception as e:
            logging.error("❌ Ошибка цикла: %s", e, exc_info=True)
            time.sleep(5)

        # учитываем потраченное время
        elapsed = time.monotonic() - started
        sleep_for = max(1.0, POLL_SECONDS - elapsed)
        time.sleep(sleep_for)

if __name__ == "__main__":
    main()
