"""
Шаг 1: Импорт 50 тестовых заказов из mock_orders.json в RetailCRM.
Запуск: python scripts/import_to_crm.py
"""
import json
import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

CRM_URL = os.getenv("RETAILCRM_URL", "").rstrip("/")
CRM_KEY = os.getenv("RETAILCRM_API_KEY", "")
REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", "0.3"))


def get_site_code():
    """Получаем код сайта из CRM (нужен для создания заказов)."""
    resp = requests.get(
        f"{CRM_URL}/api/v5/reference/sites",
        params={"apiKey": CRM_KEY},
        timeout=10,
    )
    data = resp.json()
    if data.get("success"):
        sites = data.get("sites", {})
        if sites:
            code = list(sites.keys())[0]
            print(f"  Найден сайт: '{code}'")
            return code
    print(f"  Не удалось получить сайт: {data.get('errorMsg')}")
    return None


def get_valid_statuses():
    """Получаем доступные статусы заказов."""
    resp = requests.get(
        f"{CRM_URL}/api/v5/reference/statuses",
        params={"apiKey": CRM_KEY},
        timeout=10,
    )
    data = resp.json()
    if data.get("success"):
        return list(data.get("statuses", {}).keys())
    return []


def build_crm_order(raw, valid_statuses):
    """Формируем безопасный объект заказа для RetailCRM."""
    order = {
        "firstName": raw.get("firstName", ""),
        "lastName": raw.get("lastName", ""),
        "phone": raw.get("phone", ""),
        "email": raw.get("email", ""),
        "items": raw.get("items", []),
    }

    # Доставка — RetailCRM принимает только нужные поля
    delivery = raw.get("delivery", {})
    if delivery:
        order["delivery"] = delivery

    # Статус только если он существует в CRM
    raw_status = raw.get("status", "")
    if raw_status and raw_status in valid_statuses:
        order["status"] = raw_status

    return order


def import_orders():
    mock_path = os.path.join(os.path.dirname(__file__), "..", "mock_orders.json")
    with open(mock_path, "r", encoding="utf-8") as f:
        orders = json.load(f)

    print(f"Загружено {len(orders)} заказов из mock_orders.json\n")

    print("Получаем конфигурацию RetailCRM...")
    site_code = get_site_code()
    valid_statuses = get_valid_statuses()
    print(f"  Доступные статусы: {valid_statuses[:5]}{'...' if len(valid_statuses) > 5 else ''}\n")

    params = {"apiKey": CRM_KEY}
    if site_code:
        params["site"] = site_code

    success, errors = 0, 0

    for i, order in enumerate(orders, 1):
        safe_order = build_crm_order(order, valid_statuses)
        try:
            resp = requests.post(
                f"{CRM_URL}/api/v5/orders/create",
                params=params,
                data={"order": json.dumps(safe_order, ensure_ascii=False)},
                timeout=15,
            )
            data = resp.json()

            if data.get("success"):
                order_id = data.get("id", "?")
                print(f"[{i:02d}/50] ✓ ID: {order_id}  {order.get('firstName')} {order.get('lastName')}")
                success += 1
            else:
                msg = data.get("errorMsg") or json.dumps(data, ensure_ascii=False)
                errors_detail = data.get("errors", {})
                print(f"[{i:02d}/50] ✗ {msg}  {errors_detail}")
                errors += 1

        except requests.RequestException as e:
            print(f"[{i:02d}/50] ✗ Сетевая ошибка: {e}")
            errors += 1

        time.sleep(REQUEST_DELAY)

    print(f"\n{'='*40}")
    print(f"Готово!  Успешно: {success}  |  Ошибок: {errors}")


if __name__ == "__main__":
    import_orders()
