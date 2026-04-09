"""
Unit-тесты: трансформация данных CRM → Supabase.
Эти тесты не обращаются к внешним API — работают полностью офлайн.
Запуск: pytest tests/test_transform.py -v
"""
import sys
import os

# Делаем scripts/ доступным для импорта
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.sync_to_supabase import build_row


# ─── Фикстуры ────────────────────────────────────────────────────────────────

FULL_ORDER = {
    "id": 42,
    "number": "S-42",
    "firstName": "Айгуль",
    "lastName": "Касымова",
    "phone": "+77001234501",
    "email": "aigul@example.com",
    "totalSumm": 15000.0,
    "status": "new",
    "createdAt": "2024-01-15T10:30:00+06:00",
    "delivery": {
        "address": {"city": "Алматы", "text": "ул. Абая 150"}
    },
    "customFields": {"utm_source": "instagram"},
    "items": [
        {"productName": "Корсет Nova", "quantity": 1, "initialPrice": 15000}
    ],
}

ORDER_WITHOUT_TOTAL = {
    **FULL_ORDER,
    "totalSumm": 0,
    "items": [
        {"productName": "Корсет Nova", "quantity": 2, "initialPrice": 15000},
        {"productName": "Шорты Nova Shape", "quantity": 1, "initialPrice": 12000},
    ],
}

ORDER_HIGH_VALUE = {
    **FULL_ORDER,
    "totalSumm": 75000.0,
}

MINIMAL_ORDER = {
    "id": 99,
    "number": "S-99",
}


# ─── Тесты build_row ─────────────────────────────────────────────────────────

class TestBuildRow:
    def test_basic_fields_mapped(self):
        row = build_row(FULL_ORDER)
        assert row["crm_id"] == "42"
        assert row["crm_number"] == "S-42"
        assert row["phone"] == "+77001234501"
        assert row["email"] == "aigul@example.com"
        assert row["status"] == "new"

    def test_customer_name_concatenated(self):
        row = build_row(FULL_ORDER)
        assert row["customer_name"] == "Айгуль Касымова"

    def test_total_sum_from_totalSumm(self):
        """Берёт totalSumm если он > 0"""
        row = build_row(FULL_ORDER)
        assert row["total_sum"] == 15000.0

    def test_total_sum_calculated_from_items(self):
        """Если totalSumm == 0 — считает из items"""
        row = build_row(ORDER_WITHOUT_TOTAL)
        # 2 * 15000 + 1 * 12000 = 42000
        assert row["total_sum"] == 42000.0

    def test_city_extracted_from_delivery(self):
        row = build_row(FULL_ORDER)
        assert row["city"] == "Алматы"

    def test_utm_source_extracted(self):
        row = build_row(FULL_ORDER)
        assert row["utm_source"] == "instagram"

    def test_high_value_order(self):
        row = build_row(ORDER_HIGH_VALUE)
        assert row["total_sum"] > 50000

    def test_minimal_order_no_crash(self):
        """Заказ с минимальными полями не роняет скрипт"""
        row = build_row(MINIMAL_ORDER)
        assert row["crm_id"] == "99"
        assert row["customer_name"] == ""
        assert row["total_sum"] == 0.0
        assert row["city"] == ""
        assert row["utm_source"] == ""

    def test_crm_id_always_string(self):
        """crm_id всегда строка (для Supabase TEXT UNIQUE)"""
        row = build_row(FULL_ORDER)
        assert isinstance(row["crm_id"], str)

    def test_missing_delivery_no_crash(self):
        order = {**FULL_ORDER, "delivery": None}
        row = build_row(order)
        assert row["city"] == ""

    def test_missing_custom_fields_no_crash(self):
        order = {**FULL_ORDER, "customFields": None}
        row = build_row(order)
        assert row["utm_source"] == ""


# ─── Тесты порогового значения ────────────────────────────────────────────────

class TestHighValueThreshold:
    THRESHOLD = 50_000

    def test_order_below_threshold(self):
        row = build_row(FULL_ORDER)  # 15000
        assert row["total_sum"] <= self.THRESHOLD

    def test_order_above_threshold(self):
        row = build_row(ORDER_HIGH_VALUE)  # 75000
        assert row["total_sum"] > self.THRESHOLD

    def test_order_at_exact_threshold(self):
        order = {**FULL_ORDER, "totalSumm": 50000.0}
        row = build_row(order)
        # Ровно 50000 НЕ триггерит алерт (> 50000, не >=)
        assert not (row["total_sum"] > self.THRESHOLD)
