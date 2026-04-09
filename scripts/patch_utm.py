"""
Одноразовый скрипт: дописывает utm_source в Supabase из mock_orders.json.
Матчинг по номеру телефона.
Запуск: python scripts/patch_utm.py
"""
import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()

SB_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.getenv("SUPABASE_SECRET_KEY", "")

HEADERS = {
    "Authorization": f"Bearer {SB_KEY}",
    "apikey": SB_KEY,
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}


def patch_utm():
    mock_path = os.path.join(os.path.dirname(__file__), "..", "mock_orders.json")
    with open(mock_path, "r", encoding="utf-8") as f:
        orders = json.load(f)

    updated, skipped = 0, 0

    for order in orders:
        phone = order.get("phone", "")
        utm = (order.get("customFields") or {}).get("utm_source", "")

        if not phone or not utm:
            skipped += 1
            continue

        resp = requests.patch(
            f"{SB_URL}/rest/v1/orders",
            headers=HEADERS,
            params={"phone": f"eq.{phone}"},
            json={"utm_source": utm},
            timeout=10,
        )

        if resp.status_code in (200, 204):
            print(f"✓ {phone}  →  {utm}")
            updated += 1
        else:
            print(f"✗ {phone}  ошибка: {resp.status_code} {resp.text[:80]}")
            skipped += 1

    print(f"\nОбновлено: {updated}  |  Пропущено: {skipped}")


if __name__ == "__main__":
    patch_utm()
