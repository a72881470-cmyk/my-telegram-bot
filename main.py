import os
import time
import logging
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv

# ==========================
# Инициализация
# ==========================
load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_IDS = [c.strip() for c in os.getenv("TELEGRAM_CHAT_ID", "").split(",") if c.strip()]

# Фильтры
MIN_LIQ_USD       = float(os.getenv("MIN_LIQ_USD", 500))     # мин. ликвидность $
MIN_PCHANGE_5M    = float(os.getenv("MIN_PCHANGE_5M", 25))   # мин. рост за 5м, %
NEW_MAX_AGE_MIN   = int(os.getenv("NEW_MAX_AGE_MIN", 60))    # макс. возраст пары (мин)
POLL_SECONDS      = int(os.getenv("POLL_SECONDS", 60))       # опрос каждые N секунд

DEX_URL = "https://api.dexscreener.com/latest/dex/search?q=solana"

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_IDS:
    logging.error("❌ TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_ID не заданы в .env")
    raise SystemExit(1)

sent_cache = {}

# ==========================
# Утилиты
# ==========================
def fmt_usd(x) -> str:
    try:
        x = float(x)
        if x >= 1:
            return f"${x:,.2f}"
        return f"${x:,.6f}"
    except Exception:
        return f"${x}"

def fmt_minutes_ago(created_ms: int) -> str:
    if not created_ms:
        return "—"
    age_min = (time.time() - created_ms / 1000.0) / 60.0
    if age_min < 60:
        return f"{age_min:.0f} мин"
    return f"{age_min / 60.0:.1f} ч"

def is_meme(tags) -> bool:
    tags = [str(t).lower() for t in (tags or [])]
    MEME_MARKERS = {"meme", "memecoin", "shitcoin", "pepe", "doge"}
    return any(t in MEME_MARKERS for t in tags)

def build_links(pair: dict):
    pair_addr = pair.get("pairAddress", "")
    token_addr = (pair.get("baseToken") or {}).get("address", "")
    dex_link = f"https://dexscreener.com/solana/{pair_addr}" if pair_addr else ""
    phantom_link = f"https://phantom.app/ul/browse/{token_addr}" if token_addr else ""
    return dex_link, phantom_link

def send_telegram(text: str):
    for chat_id in TELEGRAM_CHAT_IDS:
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json=payload, timeout=10
            )
            if r.status_code != 200:
                logging.warning("Telegram error (%s): %s", chat_id, r.text)
        except Exception as e:
            logging.error("Telegram send error (%s): %s", chat_id, e)

# ==========================
# Логика
# ==========================
def fetch_pairs() -> list[dict]:
    try:
        r = requests.get(DEX_URL, timeout=15)
        if r.status_code != 200:
            logging.warning("DexScreener HTTP %s: %s", r.status_code, r.text[:200])
            return []
        return (r.json() or {}).get("pairs", []) or []
    except Exception as e:
        logging.error("DexScreener request error: %s", e)
        return []

def pair_age_minutes(pair: dict) -> float | None:
    created_ms = pair.get("pairCreatedAt") or (pair.get("info") or {}).get("createdAt")
    if not created_ms:
        return None
    try:
        return (time.time() - float(created_ms) / 1000.0) / 60.0
    except Exception:
        return None

def should_notify(pair: dict) -> tuple[bool, str]:
    if (pair.get("chainId") or "").lower() != "solana":
        return (False, "")
    age_min = pair_age_minutes(pair)
    if age_min is None or age_min > NEW_MAX_AGE_MIN:
        return (False, "")
    price_change_5m = (pair.get("priceChange") or {}).get("m5")
    if price_change_5m is None or float(price_change_5m) < MIN_PCHANGE_5M:
        return (False, "")
    liq_usd = (pair.get("liquidity") or {}).get("usd") or 0
    try:
        liq_usd = float(liq_usd)
    except Exception:
        liq_usd = 0.0
    if liq_usd < MIN_LIQ_USD:
        return (False, "")
    label = "[MEME]" if is_meme(pair.get("tags")) else "[SOL]"
    return (True, label)

def prune_sent_cache():
    cutoff = time.time() - NEW_MAX_AGE_MIN * 60
    for pid, ts in list(sent_cache.items()):
        if ts < cutoff:
            sent_cache.pop(pid, None)

# ==========================
# Запуск
# ==========================
def main():
    logging.info("🚀 Бот запущен. Ищу новые токены Solana с ростом ≥ %.2f%% за 5м…", MIN_PCHANGE_5M)
    while True:
        started = time.monotonic()
        try:
            prune_sent_cache()
            pairs = fetch_pairs()
            found = 0

            for p in pairs:
                ok, label = should_notify(p)
                if not ok:
                    continue

                pair_id = p.get("pairAddress")
                if not pair_id or pair_id in sent_cache:
                    continue

                base = p.get("baseToken") or {}
                name = base.get("name", "Unknown")
                symbol = base.get("symbol", "")
                price = p.get("priceUsd", 0) or 0
                try:
                    price = float(price)
                except Exception:
                    pass
                pchg5 = float((p.get("priceChange") or {}).get("m5", 0) or 0)
                liq_usd = float((p.get("liquidity") or {}).get("usd", 0) or 0)
                created_ms = p.get("pairCreatedAt") or (p.get("info") or {}).get("createdAt")
                age_str = fmt_minutes_ago(created_ms) if created_ms else "—"

                dex_link, phantom_link = build_links(p)

                logging.info(
                    "[Найден токен] %s %s | Рост 5м: %.2f%% | Цена: %s | Ликвидн.: $%s | Возраст: %s | %s",
                    label, f"{name} ({symbol})", pchg5, fmt_usd(price), f"{liq_usd:,.0f}", age_str, dex_link
                )

                msg = (
                    f"{label} <b>{name} ({symbol})</b>\n"
                    f"📈 Рост за 5м: <b>+{pchg5:.2f}%</b>\n"
                    f"💰 Цена: <b>{fmt_usd(price)}</b>\n"
                    f"💵 Ликвидность: <b>${liq_usd:,.0f}</b>\n"
                    f"⏱ Возраст пары: <b>{age_str}</b>\n"
                    f"🔗 <a href='{dex_link}'>DexScreener</a>\n"
                    f"👛 <a href='{phantom_link}'>Открыть в Phantom</a>"
                )
                send_telegram(msg)

                sent_cache[pair_id] = time.time()
                found += 1

            if found == 0:
                logging.info("⏳ Подходящих новых токенов нет. Жду…")

        except Exception as e:
            logging.error("❌ Ошибка цикла: %s", e, exc_info=True)
            time.sleep(5)

        elapsed = time.monotonic() - started
        time.sleep(max(1.0, POLL_SECONDS - elapsed))


if __name__ == "__main__":
    main()
