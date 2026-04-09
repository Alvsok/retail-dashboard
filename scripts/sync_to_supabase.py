"""
Шаг 2: Синхронизация заказов RetailCRM → Supabase + Telegram-уведомления.
Запуск: python scripts/sync_to_supabase.py
"""
import json
import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

CRM_URL = os.getenv("RETAILCRM_URL", "").rstrip("/")
CRM_KEY = os.getenv("RETAILCRM_API_KEY", "")
SB_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.getenv("SUPABASE_SECRET_KEY", "")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TG_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
HIGH_VALUE_THRESHOLD = int(os.getenv("HIGH_VALUE_THRESHOLD", "50000"))

SB_HEADERS = {
    "Authorization": f"Bearer {SB_KEY}",
    "apikey": SB_KEY,
    "Content-Type": "application/json",
}



# ─── 1. Fetch from RetailCRM ──────────────────────────────────────────────────

def fetch_crm_orders():
    all_orders = []
    page = 1

    while True:
        resp = requests.get(
            f"{CRM_URL}/api/v5/orders",
            params={"apiKey": CRM_KEY, "limit": 100, "page": page},
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()

        if not data.get("success"):
            print(f"  CRM ошибка: {data.get('errorMsg')}")
            break

        batch = data.get("orders", [])
        all_orders.extend(batch)

        pagination = data.get("pagination", {})
        total_pages = pagination.get("totalPageCount", 1)
        print(f"  Страница {page}/{total_pages} — получено {len(batch)} заказов")

        if page >= total_pages:
            break
        page += 1
        time.sleep(0.2)

    return all_orders


# ─── 2. Upsert to Supabase ────────────────────────────────────────────────────

def build_row(order):
    # Считаем сумму: берём totalSumm, если 0 — суммируем items
    total = float(order.get("totalSumm", 0) or 0)
    if total == 0:
        for item in order.get("items", []):
            total += float(item.get("initialPrice", 0)) * float(item.get("quantity", 1))

    city = ""
    delivery = order.get("delivery") or {}
    addr = delivery.get("address") or {}
    city = addr.get("city", "")

    utm_source = ""
    custom = order.get("customFields") or {}
    utm_source = custom.get("utm_source", "")

    return {
        "crm_id": str(order["id"]),
        "crm_number": str(order.get("number", "")),
        "customer_name": f"{order.get('firstName', '')} {order.get('lastName', '')}".strip(),
        "phone": order.get("phone", ""),
        "email": order.get("email", ""),
        "total_sum": total,
        "status": order.get("status", ""),
        "city": city,
        "utm_source": utm_source,
        "created_at": order.get("createdAt"),
    }


def upsert_orders(orders):
    rows = [build_row(o) for o in orders]

    batch_size = 20
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        resp = requests.post(
            f"{SB_URL}/rest/v1/orders",
            headers={**SB_HEADERS, "Prefer": "resolution=merge-duplicates,return=minimal"},
            json=batch,
            timeout=20,
        )
        if resp.status_code in (200, 201, 204):
            print(f"  Upsert строк {i + 1}–{i + len(batch)}: ✓")
        else:
            print(f"  Upsert ошибка [{resp.status_code}]: {resp.text[:200]}")


# ─── 3. Telegram alerts ───────────────────────────────────────────────────────

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    resp = requests.post(
        url,
        json={"chat_id": TG_CHAT_ID, "text": text, "parse_mode": "HTML"},
        timeout=10,
    )
    return resp.json().get("ok", False)


def process_alerts():
    # Заказы с суммой > 50k, алерт ещё не отправлен
    resp = requests.get(
        f"{SB_URL}/rest/v1/orders",
        headers=SB_HEADERS,
        params={
            "select": "*",
            "total_sum": f"gt.{HIGH_VALUE_THRESHOLD}",
            "alert_sent": "eq.false",
        },
        timeout=15,
    )

    if resp.status_code != 200:
        print(f"  Ошибка выборки: {resp.text}")
        return

    pending = resp.json()
    print(f"  Ожидают алерт: {len(pending)} заказов")

    for order in pending:
        msg = (
            f"🔔 <b>Крупный заказ &gt; {HIGH_VALUE_THRESHOLD:,} ₸!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>{order['customer_name']}</b>\n"
            f"📦 Заказ №{order['crm_number']}\n"
            f"💰 Сумма: <b>{order['total_sum']:,.0f} ₸</b>\n"
            f"🏙 Город: {order['city'] or '—'}\n"
            f"📢 Источник: {order['utm_source'] or '—'}"
        )
        ok = send_telegram(msg)

        if ok:
            print(f"  ✓ Telegram → №{order['crm_number']}  {order['total_sum']:,.0f} ₸")
            # Помечаем что алерт отправлен
            requests.patch(
                f"{SB_URL}/rest/v1/orders",
                headers={**SB_HEADERS, "Prefer": "return=minimal"},
                params={"crm_id": f"eq.{order['crm_id']}"},
                json={"alert_sent": True},
                timeout=10,
            )
        else:
            print(f"  ✗ Telegram не ответил для №{order['crm_number']}")


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("RetailCRM → Supabase Sync + Telegram Alerts")
    print("=" * 50)

    print("\n[1/3] Получаем заказы из RetailCRM...")
    orders = fetch_crm_orders()
    print(f"      Итого: {len(orders)} заказов")

    print("\n[2/3] Записываем в Supabase...")
    upsert_orders(orders)

    print("\n[3/3] Отправляем Telegram-уведомления...")
    process_alerts()

    print("\n✅ Готово!")
