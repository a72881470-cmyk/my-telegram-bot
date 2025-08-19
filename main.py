import asyncio
import json
import os
import time
from urllib.parse import quote

import requests
import websockets
from dotenv import load_dotenv
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

# === Загружаем .env ===
load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

bot = Bot(token=BOT_TOKEN)

# === API ===
PUMP_WS = "wss://pumpportal.fun/api/data"
DEX_API = "https://api.dexscreener.com/token-pairs/v1/solana/{mint}"

# === Настройки ===
PUMP_ALERT_PCT = 100.0     # сигнал на рост
DROP_ALERT_PCT = 100.0     # сигнал на падение
TRACK_SECONDS = 6 * 60 * 60  # следим 6 часов за токеном

tokens = {}  # mint -> dict


def percent_change(old, new):
    return (new / old - 1) * 100 if old > 0 else 0


def nice_price(price):
    return f"{price:.8f}".rstrip("0").rstrip(".")


def phantom_link(mint):
    buy = quote(f"solana:101/address:{mint}", safe="")
    sell = quote("solana:101/address:So11111111111111111111111111111111111111112", safe="")
    return f"https://phantom.app/ul/v1/swap?buy={buy}&sell={sell}"


async def send_signal(mint, title, text, price, pair_url):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🟣 Купить в Phantom", url=phantom_link(mint))],
        [InlineKeyboardButton("🌐 Dexscreener", url=pair_url)]
    ])

    msg = (
        f"<b>{title}</b>\n"
        f"{text}\n"
        f"💵 Цена: <code>{nice_price(price)}</code>\n"
        f"🔗 <a href=\"{pair_url}\">Dexscreener</a>"
    )

    await bot.send_message(
        chat_id=CHAT_ID,
        text=msg,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
        reply_markup=kb
    )


async def handle_new_token(mint, name, symbol):
    url = DEX_API.format(mint=mint)
    r = requests.get(url, timeout=10)
    if r.status_code != 200:
        return
    pairs = r.json()
    if not pairs:
        return
    p = pairs[0]

    price = float(p.get("priceUsd") or 0)
    if price <= 0:
        return

    tokens[mint] = {
        "name": name or mint[:6],
        "symbol": symbol or "",
        "first_price": price,
        "last_price": price,
        "high": price,
        "pair_url": p.get("url", ""),
        "created_at": time.time(),
        "pump": False,
        "drop": False,
    }

    await send_signal(
        mint,
        "🆕 Новый токен",
        f"🎯 {tokens[mint]['name']} ({tokens[mint]['symbol']})",
        price,
        tokens[mint]["pair_url"]
    )


async def watcher():
    while True:
        now = time.time()
        for mint, t in list(tokens.items()):
            if now - t["created_at"] > TRACK_SECONDS:
                tokens.pop(mint, None)
                continue

            # обновим цену
            r = requests.get(DEX_API.format(mint=mint), timeout=10)
            if r.status_code != 200:
                continue
            pairs = r.json()
            if not pairs:
                continue
            price = float(pairs[0].get("priceUsd") or 0)
            if price <= 0:
                continue

            t["last_price"] = price
            if price > t["high"]:
                t["high"] = price

            # 🚀 сигнал при росте +100% от старта
            change = percent_change(t["first_price"], price)
            if not t["pump"] and change >= PUMP_ALERT_PCT:
                t["pump"] = True
                await send_signal(mint, "🚀 Рост", f"⤴️ +{change:.1f}% от старта", price, t["pair_url"])

            # 🔻 сигнал при падении −100% от хая
            drop = percent_change(t["high"], price)
            if not t["drop"] and drop <= -DROP_ALERT_PCT:
                t["drop"] = True
                await send_signal(mint, "🔻 Падение", f"⤵️ {drop:.1f}% от хая", price, t["pair_url"])

        await asyncio.sleep(20)


async def pump_listener():
    async with websockets.connect(PUMP_WS) as ws:
        await ws.send(json.dumps({"method": "subscribeNewToken"}))
        async for msg in ws:
            data = json.loads(msg)
            if isinstance(data, dict) and data.get("type") == "new-token":
                mint = data.get("mint")
                name = data.get("name")
                symbol = data.get("symbol")
                await handle_new_token(mint, name, symbol)


async def main():
    await asyncio.gather(
        pump_listener(),
        watcher()
    )


if __name__ == "__main__":
    asyncio.run(main())
