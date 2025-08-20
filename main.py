def fetch_new_tokens():
    # Берём токены по ликвидности
    url = "https://public-api.birdeye.so/defi/tokenlist?sort_by=liquidity&sort_type=desc&offset=0&limit=200"
    headers = {
        "accept": "application/json",
        "x-chain": "solana",
        "X-API-KEY": API_KEY
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            print(f"❌ Ошибка API: статус {resp.status_code}, ответ: {resp.text}")
            return []

        data = resp.json()
        tokens = data.get("data", {}).get("tokens", [])

        new_tokens = []
        now = datetime.utcnow()
        max_age = timedelta(days=2)  # только свежие ≤ 2 дней

        for token in tokens:
            created_at = token.get("created_at")
            if not created_at:
                continue

            try:
                created_at = datetime.utcfromtimestamp(int(created_at))
            except Exception:
                continue

            # ✅ фильтр по дате
            if now - created_at <= max_age:
                vol = float(token.get("volume_usd", 0) or 0)
                liq = float(token.get("liquidity_usd", 0) or 0)

                # ✅ фильтр по метрикам
                if vol > 5000 and liq > 10000:
                    new_tokens.append(token)

        # Сортировка по дате создания (самые новые сверху)
        new_tokens.sort(key=lambda x: int(x.get("created_at", 0)), reverse=True)

        print(f"✅ Найдено {len(new_tokens)} свежих токенов")
        return new_tokens[:5]  # берём топ-5

    except Exception as e:
        print("Ошибка API:", e)
        return []
