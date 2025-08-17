import os
import time
import json
import requests
import logging
import websocket
from dotenv import load_dotenv

# === Загружаем .env ===
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# === Фильтры ===
MIN_LIQ_USD = float(os.getenv("MIN_LIQ_USD", 300))
MIN_PCHANGE_5M = float(os.getenv("MIN_PCHANGE_5M", 25))
MIN_TRADES_5M = int(os.getenv("MIN_TRADES_5M", 10))
NEW_MAX_AGE_MIN = int(os.getenv("NEW_MAX_AGE_MIN", 10))
POLL_SECONDS = int(os.getenv("POLL_SECONDS", 30))

# === Логирование ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

sent_tokens = set()
ws_active = False  # флаг активности WebSocket

# === Telegram ===
def send_telegram(msg: str):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        logging.error(f"Ошибка отправки в Telegram: {e}")

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
        return pairs[0]
    except Exception as e:
        logging.error(f"Dexscreener error: {e}")
        return None

# === Pump.fun API (резерв) ===
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
            if age_min <= NEW_MAX_AGE_MIN:
                fresh.append({
                    "symbol": c.get("symbol", "???"),
                    "address": c.get("mint"),
                    "age_min": round(age_min, 1)
                })
        return fresh
    except Exception as e:
        logging.error(f"Pump.fun (REST) error: {e}")
        return []

# === Обработка события ===
def handle_token(address, symbol="???", age_min=0):
    try:
        if address in sent_tokens:
            return

        info = get_token_info(address)
        if not info:
            return

        liq = info.get("liquidity", {}).get("usd", 0)
        trades_5m = info.get("txns", {}).get("m5", {}).get("buys", 0) + info.get("txns", {}).get("m5", {}).get("sells", 0)
        change_5m = info.get("priceChange", {}).get("m5", 0)

        if liq >= MIN_LIQ_USD and change_5m >= MIN_PCHANGE_5M and trades_5m >= MIN_TRADES_5M:
            phantom_url = f"https://phantom.app/tokens/solana/{address}"
            msg = (
                f"🚀 *Новый мемкоин Solana!*\n\n"
                f"🪙 {symbol}\n"
                f"⏱ Возраст: {age_min:.1f} мин\n"
                f"💧 Ликвидность: ${liq:,.0f}\n"
                f"📈 Рост (5м): {change_5m:.2f}%\n"
                f"⚡ Сделок (5м): {trades_5m}\n\n"
                f"[DexScreener]({info.get('url')}) | [Phantom]({phantom_url})"
            )
            send_telegram(msg)
            sent_tokens.add(address)
            logging.info(f"✅ Сигнал отправлен: {symbol} ({address})")
    except Exception as e:
        logging.error(f"Ошибка обработки токена: {e}")

# === WebSocket PumpPortal ===
def on_message(ws, message):
    global ws_active
    ws_active = True
    try:
        data = json.loads(message)
        if data.get("type") == "trade":
            mint = data.get("mint")
            symbol = data.get("symbol", "???")
            created = data.get("created_timestamp", time.time())
            age_min = (time.time() - created) / 60 if created else 9999
            if age_min <= NEW_MAX_AGE_MIN:
                handle_token(mint, symbol, age_min)
    except Exception as e:
        logging.error(f"Ошибка в on_message: {e}")

def on_error(ws, error):
    global ws_active
    ws_active = False
    logging.error(f"WebSocket ошибка: {error}")

def on_close(ws, close_status_code, close_msg):
    global ws_active
    ws_active = False
    logging.warning("WebSocket закрыт.")

def on_open(ws):
    global ws_active
    ws_active = True
    logging.info("✅ Подключено к PumpPortal WebSocket")

def run_ws():
    ws = websocket.WebSocketApp(
        "wss://pumpportal.fun/api/trades",
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
        on_open=on_open
    )
    ws.run_forever()

# === Failover режим ===
def fallback_loop():
    while True:
        if not ws_active:
            logging.info("⚠️ WebSocket недоступен → используем Pump.fun API")
            tokens = get_new_pumpfun_tokens()
            for t in tokens:
                handle_token(t["address"], t["symbol"], t["age_min"])
        time.sleep(POLL_SECONDS)

if __name__ == "__main__":
    from threading import Thread
    logging.info("🚀 Бот запущен. Мониторинг мемкоинов…")

    # Запускаем WebSocket и Failover параллельно
    Thread(target=run_ws, daemon=True).start()
    fallback_loop()
