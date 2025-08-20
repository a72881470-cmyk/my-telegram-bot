import os
import time
import threading
import json
import requests
import telebot
from datetime import datetime, timedelta
from dotenv import load_dotenv

# ─── env ──────────────────────────────────────────────────────────────────────
load_dotenv()
TELEGRAM_TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")
CHAT_ID        = os.getenv("TELEGRAM_CHAT_ID") or os.getenv("CHAT_ID")

CHECK_INTERVAL_SEC = int(os.getenv("CHECK_INTERVAL_SEC", "60"))
MAX_AGE_MIN        = int(os.getenv("MAX_AGE_MIN", "2880"))       # 2 дня = 2880
MIN_VOLUME_USD     = float(os.getenv("MIN_VOLUME_USD", "5000"))  # фильтр по объёму
MIN_LIQ_USD        = float(os.getenv("MIN_LIQ_USD", "0"))        # 0 = не фильтруем
PUMP_ALERT_PCT     = float(os.getenv("PUMP_ALERT_PCT", "100"))   # рост от старт. цены
DROP_ALERT_PCT     = float(os.getenv("DROP_ALERT_PCT", "100"))   # падение от ATH

if not TELEGRAM_TOKEN or not CHAT_ID:
    raise SystemExit("❌ Заполни BOT_TOKEN и TELEGRAM_CHAT_ID в .env")

bot = telebot.TeleBot(TELEGRAM_TOKEN, parse_mode=None)

# ─── State ────────────────────────────────────────────────────────────────────
sent_new_signal = set()  # какие пары уже присылали как «новые»
track = {}               # pairAddress -> dict(base_price, ath, pump_sent, drop_sent)

# ─── helpers ──────────────────────────────────────────────────────────────────
SEARCH_URL = "https://api.dexscreener.com/latest/dex/search?q=solana"
PAIRS_URL  = "https://api.dexscreener.com/latest/dex/pairs/solana"

def dex_fetch_pairs():
    """Получить пары Solana. Сначала search, при 404/ошибке — запасной эндпоинт."""
    for url in (SEARCH_URL, PAIRS_URL):
        try:
            r = requests.get(url, timeout=12)
            if r.status_code == 200:
                data = r.json()
                if data and isinstance(data, dict) and data.get("pairs"):
                    return data["pairs"]
            else:
                print(f"❌ Dex API {url} -> {r.status_code}")
        except Exception as e:
            print(f"❌ Dex API {url} -> {e}")
    return []

def as_float(x, default=None):
    try:
        if x is None: return default
        return float(x)
    except Exception:
        return default

def phantom_buy_link(base_mint: str) -> str:
    # Откроет Jupiter в Phantom (мобайл/десктоп): USDC -> ваш токен
    jup = f"https://jup.ag/swap/USDC-{base_mint}"
    # Phantom deeplink (работает и как обычная ссылка)
    return f"https://phantom.app/ul/browse/{jup}"

def nice_pct(x):
    try:
        return f"{float(x):.2f}%"
    except Exception:
        return "N/A"

# ─── Telegram ─────────────────────────────────────────────────────────────────
def send(msg: str):
    try:
        bot.send_message(CHAT_ID, msg)
    except Exception as e:
        print("⚠️ Ошибка отправки в Telegram:", e)

def worker_status():
    while True:
        send("✅ Я работаю, слежу за рынком! 💰")
        time.sleep(7200)  # каждые 2 часа

# ─── Core ─────────────────────────────────────────────────────────────────────
def filter_new_pairs(pairs):
    """Фильтруем: только Solana, моложе MAX_AGE_MIN, объём >= MIN_VOLUME, ликвидность >= MIN_LIQ."""
    now = datetime.utcnow()
    max_age = timedelta(minutes=MAX_AGE_MIN)
    out = []

    for p in pairs:
        if p.get("chainId") and p["chainId"] != "solana":
            continue

        created_ts = p.get("pairCreatedAt")
        if not created_ts:
            continue
        created_at = datetime.utcfromtimestamp(created_ts / 1000)
        if now - created_at > max_age:
            continue

        vol24 = as_float(p.get("volume", {}).get("h24"), 0.0)
        if vol24 < MIN_VOLUME_USD:
            continue

        liq = as_float(p.get("liquidity", {}).get("usd"), 0.0)
        if liq is not None and liq < MIN_LIQ_USD:
            continue

        out.append(p)
    return out

def announce_new_pair(p):
    base = p.get("baseToken", {}) or {}
    quote = p.get("quoteToken", {}) or {}
    symbol = base.get("symbol", "N/A")
    name   = base.get("name", "N/A")
    price  = p.get("priceUsd", "N/A")
    url    = p.get("url", "https://dexscreener.com/")
    pc5m   = p.get("priceChange", {}).get("m5")
    pc1h   = p.get("priceChange", {}).get("h1")
    pair_name = f"{symbol}/{quote.get('symbol','?')}"
    base_mint = base.get("address") or ""
    phantom   = phantom_buy_link(base_mint) if base_mint else "https://phantom.app/"

    msg = (
        "🟢 Новый токен (Solana)!\n\n"
        f"📛 Название: {name}\n"
        f"🔹 Пара: {pair_name}\n"
        f"💲 Цена: {price}\n"
        f"📈 Рост 5м: {nice_pct(pc5m)} | 1ч: {nice_pct(pc1h)}\n"
        f"🌐 DexScreener: {url}\n"
        f"👛 Купить в Phantom (Jupiter): {phantom}"
    )
    send(msg)

def check_pump_drop(p):
    """Следить за ростом от старта и падением от ATH для уже анонсированных пар."""
    pair_addr = p.get("pairAddress")
    if not pair_addr:
        return
    price = as_float(p.get("priceUsd"))
    if price is None:
        return

    st = track.setdefault(pair_addr, {"base": price, "ath": price, "pump": False, "drop": False})
    # обновим ATH
    if price > st["ath"]:
        st["ath"] = price

    # сигнал на рост от стартовой цены
    if not st["pump"]:
        base_price = st["base"]
        if base_price and price >= base_price * (1 + PUMP_ALERT_PCT / 100):
            base = p.get("baseToken", {}) or {}
            quote = p.get("quoteToken", {}) or {}
            pair_name = f"{base.get('symbol','?')}/{quote.get('symbol','?')}"
            url = p.get("url", "https://dexscreener.com/")
            send(
                "🚀 РОСТ! Токен перевалил порог\n\n"
                f"🔹 Пара: {pair_name}\n"
                f"📈 Рост от старта: {PUMP_ALERT_PCT:.0f}%+\n"
                f"💲 Текущая цена: {price}\n"
                f"🌐 DexScreener: {url}"
            )
            st["pump"] = True

    # сигнал на падение от ATH
    if not st["drop"] and st["ath"] > 0:
        if price <= st["ath"] * (1 - DROP_ALERT_PCT / 100):
            base = p.get("baseToken", {}) or {}
            quote = p.get("quoteToken", {}) or {}
            pair_name = f"{base.get('symbol','?')}/{quote.get('symbol','?')}"
            url = p.get("url", "https://dexscreener.com/")
            send(
                "🔻 ПАДЕНИЕ! Токен просел от ATH\n\n"
                f"🔹 Пара: {pair_name}\n"
                f"📉 Просадка от ATH: {DROP_ALERT_PCT:.0f}%+\n"
                f"💲 Текущая цена: {price}\n"
                f"🌐 DexScreener: {url}"
            )
            st["drop"] = True

def main_loop():
    send("🚀 Погнали фармить деньги! 🤑")
    threading.Thread(target=worker_status, daemon=True).start()

    while True:
        pairs_raw = dex_fetch_pairs()
        if not pairs_raw:
            time.sleep(CHECK_INTERVAL_SEC)
            continue

        # для дебага можно сохранять ответ
        try:
            with open("api_debug.json", "w", encoding="utf-8") as f:
                json.dump({"pairs": pairs_raw[:50]}, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

        filtered = filter_new_pairs(pairs_raw)
        print(f"✅ Найдено {len(filtered)} новых токенов (возраст ≤ {MAX_AGE_MIN} мин, vol ≥ {MIN_VOLUME_USD}$, liq ≥ {MIN_LIQ_USD}$)")

        for p in filtered:
            pair_addr = p.get("pairAddress")
            if not pair_addr:
                continue

            if pair_addr not in sent_new_signal:
                announce_new_pair(p)
                sent_new_signal.add(pair_addr)

            # слежение за ростом/падением для уже анонсированных
            check_pump_drop(p)

        time.sleep(CHECK_INTERVAL_SEC)

# ─── entry ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🚀 Бот запущен, слежу за Solana...")
    main_loop()
