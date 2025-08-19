import requests
import time
from datetime import datetime, timezone
import os

# ------------------- НАСТРОЙКИ -------------------
BOT_TOKEN = "ТВОЙ_ТОКЕН_БОТА"
CHAT_ID = "ТВОЙ_CHAT_ID"

API_URL = "https://api.dexscreener.com/latest/dex/tokens/"
WATCH_TOKEN = "0x..."   # контракт монеты которую мониторим

CHECK_INTERVAL = 30  # проверка каждые 30 секунд
# -------------------------------------------------


def send_telegram(msg: str):
    """Отправка сообщения в Telegram"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg})
    except Exception as e:
        print("Ошибка отправки в Telegram:", e)


def check_token():
    """Проверка токена на Dexscreener"""
    try:
        url = API_URL + WATCH_TOKEN
        r = requests.get(url, timeout=10)
        data = r.json()

        if "pairs" not in data or len(data["pairs"]) == 0:
            print("⚠ Монета не найдена")
            return

        pair = data["pairs"][0]

        # -------- Возраст пары --------
        created_at = pair.get("pairCreatedAt")
        created_dt = None

        if isinstance(created_at, int):  # timestamp в ms
            created_dt = datetime.fromtimestamp(created_at / 1000, tz=timezone.utc)
        elif isinstance(created_at, str):  # иногда ISO
            try:
                created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            except Exception:
                created_dt = datetime.now(timezone.utc)
        else:
            created_dt = datetime.now(timezone.utc)

        age_min = (datetime.now(timezone.utc) - created_dt).total_seconds() / 60
        # ------------------------------

        # Данные о цене
        price = pair.get("priceUsd", "N/A")
        symbol = pair.get("baseToken", {}).get("symbol", "?")

        msg = (
            f"🚨 Найден токен {symbol}\n"
            f"💰 Цена: {price} USD\n"
            f"⏱ Возраст пары: {age_min:.1f} минут\n"
            f"🌐 Dexscreener: {pair.get('url')}"
        )

        print(msg)
        send_telegram(msg)

    except Exception as e:
        print("Ошибка проверки токена:", e)


def main():
    print("✅ Бот запущен, слежение за монетой...")
    while True:
        check_token()
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
