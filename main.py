import requests
import time
from datetime import datetime, timezone

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
        r = requests.post(url, data={"chat_id": CHAT_ID, "text": msg}, timeout=10)
        if r.status_code != 200:
            print(f"⚠ Ошибка отправки в Telegram: {r.text}")
    except Exception as e:
        print("⚠ Исключение при отправке в Telegram:", e)


def check_token():
    """Проверка токена на Dexscreener"""
    try:
        url = API_URL + WATCH_TOKEN
        r = requests.get(url, timeout=10)

        if r.status_code != 200:
            print(f"⚠ Ошибка API Dexscreener: {r.status_code}")
            return

        data = r.json()

        # Проверка структуры ответа
        if not data or "pairs" not in data or not data["pairs"]:
            print("⚠ Монета не найдена или API вернул пустой ответ")
            return

        pair = data["pairs"][0]

        # -------- Возраст пары --------
        created_at = pair.get("pairCreatedAt")
        created_dt = None

        if isinstance(created_at, int):  # timestamp в ms
            created_dt = datetime.fromtimestamp(created_at / 1000, tz=timezone.utc)
        elif isinstance(created_at, str):  # ISO8601
            try:
                created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            except Exception:
                created_dt = datetime.now(timezone.utc)
        else:
            created_dt = datetime.now(timezone.utc)

        age_min = (datetime.now(timezone.utc) - created_dt).total_seconds() / 60
        # ------------------------------

        # Данные о цене
        price = pair.get("priceUsd") or "N/A"
        symbol = pair.get("baseToken", {}).get("symbol", "?")
        url_dex = pair.get("url", "Нет ссылки")

        msg = (
            f"🚨 Найден токен {symbol}\n"
            f"💰 Цена: {price} USD\n"
            f"⏱ Возраст пары: {age_min:.1f} минут\n"
            f"🌐 Dexscreener: {url_dex}"
        )

        print(msg)
        send_telegram(msg)

    except Exception as e:
        print("⚠ Ошибка проверки токена:", e)


def main():
    print("✅ Бот запущен, слежение за монетой...")
    while True:
        check_token()
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
