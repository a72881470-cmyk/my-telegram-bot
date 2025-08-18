import os
import json
import time
import math
import threading
import http.server
import socketserver
import logging
import requests
import websocket
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# === ENV ===
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_CHAT  = os.getenv("TELEGRAM_CHAT_ID")

NEW_MAX_AGE_MIN        = float(os.getenv("NEW_MAX_AGE_MIN", 8))
MAX_LIQ_USD            = float(os.getenv("MAX_LIQ_USD", 25000))
MAX_FDV_USD            = float(os.getenv("MAX_FDV_USD", 3000000))
MIN_TXNS_5M            = int(os.getenv("MIN_TXNS_5M", 15))
MIN_BUYS_RATIO_5M      = float(os.getenv("MIN_BUYS_RATIO_5M", 0.55))
MIN_PCHANGE_5M_BUY     = float(os.getenv("MIN_PCHANGE_5M_BUY", 4))
MIN_PCHANGE_5M_ALERT   = float(os.getenv("MIN_PCHANGE_5M_ALERT", 12))

TRAIL_START_PCT        = float(os.getenv("TRAIL_START_PCT", 20))
TRAIL_GAP_PCT          = float(os.getenv("TRAIL_GAP_PCT", 15))
MAX_DRAWNDOWN_PCT      = float(os.getenv("MAX_DRAWNDOWN_PCT", 30))
LIQ_DROP_RUG_PCT       = float(os.getenv("LIQ_DROP_RUG_PCT", 50))

PORT                   = int(os.getenv("PORT", 8080))
PING_INTERVAL          = int(os.getenv("PING_INTERVAL", 30))
PING_TIMEOUT           = int(os.getenv("PING_TIMEOUT", 12))

OPENAI_API_KEY         = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL           = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

DEX_TOKEN_URL = "https://api.dexscreener.com/latest/dex/tokens/"  # + {mint}

# === State ===
sent_basic = set()          # чтобы не спамить одинаковыми «новая мемка»
tracked = {}                # mint -> dict (entry, peak, liq_peak, last_signal_ts, ...)
last_signal_ts = 0

def now_s():
    return int(time.time())

# === Helpers ===
def tglink(text, url):
    return f"<a href='{url}'>{text}</a>"

def phantom_link(mint):
    return f"https://phantom.com/tokens/solana/{mint}"

def dexs_link_any(url):
    return url or ""

def fmt_money(x):
    try:
        x = float(x)
    except: 
        return str(x)
    if x >= 1:
        return f"${x:,.0f}"
    return f"${x:,.6f}"

def percent(a, b):
    try:
        if b == 0: return 0.0
        return (a - b) / b * 100.0
    except:
        return 0.0

def is_meme_by_name(symbol, name):
    s = (symbol or "").lower()
    n = (name or "").lower()
    markers = ("meme","pepe","doge","inu","pump","moon","bonk","elon","cat","pug","wif")
    return any(m in s or m in n for m in markers)

def send_tg(text, html=True):
    if not TG_TOKEN or not TG_CHAT:
        logging.warning("TG creds missing")
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={
                "chat_id": TG_CHAT,
                "text": text,
                "parse_mode": "HTML" if html else None,
                "disable_web_page_preview": True
            },
            timeout=10
        )
    except Exception as e:
        logging.error(f"Telegram send error: {e}")

# === GPT analysis (optional) ===
def gpt_brief(symbol, name, ds_pair):
    if not OPENAI_API_KEY:
        return ""
    try:
        meta = {
            "symbol": symbol, "name": name,
            "priceChange_5m": (ds_pair.get("priceChange") or {}).get("m5"),
            "txns_5m": (ds_pair.get("txns") or {}).get("m5"),
            "liquidity": (ds_pair.get("liquidity") or {}).get("usd"),
            "fdv": ds_pair.get("fdv"),
            "pairUrl": ds_pair.get("url")
        }
        prompt = (
            "Дай короткую (1–2 строки) оценку риска/потенциала мемкоина по данным:\n"
            f"{json.dumps(meta, ensure_ascii=False)}\n"
            "Без общих фраз, конкретно по этим метрикам."
        )
        # OpenAI API (HTTP)
        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
        body = {
            "model": OPENAI_MODEL,
            "messages": [{"role":"user","content":prompt}],
            "temperature": 0.3,
            "max_tokens": 80,
        }
        r = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=body, timeout=10)
        js = r.json()
        txt = js["choices"][0]["message"]["content"].strip()
        return f"\n🤖 <i>{txt}</i>"
    except Exception as e:
        logging.warning(f"GPT error: {e}")
        return ""

# === DexScreener ===
def fetch_ds(mint):
    try:
        r = requests.get(DEX_TOKEN_URL + mint, timeout=10)
        if r.status_code != 200:
            return None
        js = r.json()
        pairs = js.get("pairs") or []
        # берем solana пары
        pairs = [p for p in pairs if (p.get("chainId") or "").lower() == "solana"]
        if not pairs:
            return None
        # приоритет: raydium -> первая
        pairs.sort(key=lambda p: (p.get("dexId") != "raydium", -(p.get("liquidity") or {}).get("usd",0)))
        return pairs[0]
    except Exception as e:
        logging.error(f"DexScreener error: {e}")
        return None

def ds_ok_for_meme(ds):
    """Фильтруем мемку и отсечем фарм"""
    liq = float((ds.get("liquidity") or {}).get("usd") or 0)
    fdv = float(ds.get("fdv") or 0)
    age_ms = ds.get("pairCreatedAt") or (ds.get("info") or {}).get("createdAt") or 0
    age_min = max(0.0, (now_s() - age_ms/1000.0)/60.0) if age_ms else 9999

    tx = ds.get("txns") or {}
    t5 = tx.get("m5") or {}
    buys = int(t5.get("buys") or 0)
    sells = int(t5.get("sells") or 0)
    total = buys + sells
    buy_ratio = (buys / total) if total>0 else 0.0

    if age_min > NEW_MAX_AGE_MIN:      return False, "old"
    if liq > MAX_LIQ_USD:              return False, "liq_too_high"
    if fdv and fdv > MAX_FDV_USD:      return False, "fdv_high"
    if total < MIN_TXNS_5M:            return False, "low_txns"
    if buy_ratio < MIN_BUYS_RATIO_5M:  return False, "low_buy_ratio"
    return True, "ok"

# === Trading logic (alerts only) ===
def consider_entries(symbol, name, mint, ds):
    """Отправляем сигналы на покупку / рост"""
    global tracked
    url = ds.get("url")
    liq = float((ds.get("liquidity") or {}).get("usd") or 0)
    price = float(ds.get("priceUsd") or 0)
    p5 = float((ds.get("priceChange") or {}).get("m5") or 0)
    tx5 = (ds.get("txns") or {}).get("m5") or {}
    buys = int(tx5.get("buys") or 0); sells=int(tx5.get("sells") or 0)

    # базовый «новая мемка» (1 раз)
    if mint not in sent_basic:
        sent_basic.add(mint)
        msg = (
            f"🟢 <b>Новый мемкоин (Solana)</b>\n"
            f"🪙 <b>{name}</b> ({symbol})\n"
            f"💧 Ликвидность: <b>{fmt_money(liq)}</b>\n"
            f"📈 5м: <b>{p5:.2f}%</b> | 🟢 {buys} / 🔴 {sells}\n"
            f"{tglink('Phantom', phantom_link(mint))} | {tglink('DexScreener', url)}"
        )
        msg += gpt_brief(symbol, name, ds)
        send_tg(msg)

    # сигнал на покупку (ранний)
    if p5 >= MIN_PCHANGE_5M_BUY and mint not in tracked:
        tracked[mint] = {
            "entry_price": price,
            "peak_price": price,
            "liq_peak": liq,
            "enter_ts": now_s(),
            "last_alert_ts": 0
        }
        msg = (
            f"✅ <b>Потенциал входа</b>\n"
            f"🪙 <b>{name}</b> ({symbol})\n"
            f"💰 Цена: <b>{fmt_money(price)}</b> | 5м: <b>{p5:.2f}%</b>\n"
            f"💧 Ликвидность: <b>{fmt_money(liq)}</b>\n"
            f"{tglink('Phantom', phantom_link(mint))} | {tglink('DexScreener', url)}"
        )
        send_tg(msg)

    # усиленный алерт «растёт»
    if p5 >= MIN_PCHANGE_5M_ALERT:
        send_tg(
            f"🚀 <b>Сильный импульс</b> — {name} ({symbol}) | 5м: <b>{p5:.2f}%</b>\n"
            f"{tglink('DexScreener', url)}"
        )

def consider_exits(symbol, name, mint, ds):
    """Отправляем сигналы на продажу по правилам"""
    st = tracked.get(mint)
    if not st:
        return
    price = float(ds.get("priceUsd") or 0)
    liq   = float((ds.get("liquidity") or {}).get("usd") or 0)
    url   = ds.get("url")

    # обновляем пики
    if price > st["peak_price"]:
        st["peak_price"] = price
    if liq > st["liq_peak"]:
        st["liq_peak"] = liq

    gain_from_entry = percent(price, st["entry_price"])
    drop_from_peak  = percent(price, st["peak_price"])  # отрицательное, если падаем
    liq_drop_from_peak = percent(liq, st["liq_peak"])

    # 1) крупная просадка от входа
    if gain_from_entry <= -MAX_DRAWNDOWN_PCT:
        send_tg(
            f"🔻 <b>Стоп-лосс</b> — {name} ({symbol})\n"
            f"Падение от входа: <b>{gain_from_entry:.1f}%</b>\n"
            f"{tglink('DexScreener', url)}"
        )
        tracked.pop(mint, None)
        return

    # 2) включён трейлинг? (после роста от входа >= TRAIL_START_PCT)
    if gain_from_entry >= TRAIL_START_PCT:
        if drop_from_peak <= -TRAIL_GAP_PCT:
            send_tg(
                f"📉 <b>Трейлинг-стоп</b> — {name} ({symbol})\n"
                f"С пика: <b>{drop_from_peak:.1f}%</b> | От входа: <b>{gain_from_entry:.1f}%</b>\n"
                f"{tglink('DexScreener', url)}"
            )
            tracked.pop(mint, None)
            return

    # 3) резкий слив ликвидности
    if st["liq_peak"] > 0 and liq_drop_from_peak <= -LIQ_DROP_RUG_PCT:
        send_tg(
            f"⛔ <b>Опасность ликвидности</b> — {name} ({symbol})\n"
            f"Ликвидность упала на <b>{abs(liq_drop_from_peak):.0f}%</b> от пика\n"
            f"{tglink('DexScreener', url)}"
        )
        tracked.pop(mint, None)
        return

# === WS callbacks ===
def on_open(ws):
    logging.info("🔗 WS connected to PumpPortal")
    send_tg("🔗 Подключено к PumpPortal (мемки Solana)")

def on_error(ws, error):
    logging.error(f"WS error: {error}")

def on_close(ws, code, msg):
    logging.warning(f"WS closed: {code} {msg}")

def on_message(ws, message):
    """
    PumpPortal шлёт события новых монет. Берём: mint, name, symbol.
    """
    try:
        data = json.loads(message)
        mint   = data.get("mint")
        name   = data.get("name")
        symbol = data.get("symbol")

        # минимальная валидация + хард-фильтр на мем-маркеры
        if not mint or not symbol:
            return
        if not is_meme_by_name(symbol, name):
            return

        # тянем данные из DexScreener и фильтруем «мемки старта»
        ds = fetch_ds(mint)
        if not ds:
            return

        ok, reason = ds_ok_for_meme(ds)
        if not ok:
            # логируем причину, но не спамим в ТГ
            logging.info(f"Skip {symbol} ({mint}) — {reason}")
            return

        # Сигналы входа/роста и постановка на слежение
        consider_entries(symbol, name, mint, ds)
        consider_exits(symbol, name, mint, ds)

    except Exception as e:
        logging.error(f"Message error: {e}")

def ws_loop():
    while True:
        try:
            ws = websocket.WebSocketApp(
                "wss://pumpportal.fun/api/data",
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close
            )
            ws.run_forever(ping_interval=PING_INTERVAL, ping_timeout=PING_TIMEOUT)
        except Exception as e:
            logging.error(f"WS fatal: {e}")
        send_tg("♻️ Переподключение к PumpPortal через 5с…")
        time.sleep(5)

# === Keepalive HTTP (Railway) ===
def run_http():
    class Handler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"OK: Solana meme sentinel online")
    with socketserver.TCPServer(("0.0.0.0", PORT), Handler) as httpd:
        logging.info(f"HTTP keepalive on {PORT}")
        httpd.serve_forever()

# === Main ===
if __name__ == "__main__":
    send_tg("🤖 Бот запущен: мониторинг мемкоинов Solana (старт/рост/выходы)")
    threading.Thread(target=run_http, daemon=True).start()
    ws_loop()
