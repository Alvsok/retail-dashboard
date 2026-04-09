"""
Smoke-тесты: проверяем что все внешние API доступны и ключи валидны.
Запуск: pytest tests/test_connections.py -v
"""
import os

import pytest
import requests
from dotenv import load_dotenv

load_dotenv()

CRM_URL = os.getenv("RETAILCRM_URL", "").rstrip("/")
CRM_KEY = os.getenv("RETAILCRM_API_KEY", "")
SB_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SB_SECRET = os.getenv("SUPABASE_SECRET_KEY", "")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TG_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


# ─── RetailCRM ────────────────────────────────────────────────────────────────

class TestRetailCRM:
    def test_env_vars_present(self):
        """Ключи заданы в .env"""
        assert CRM_URL, "RETAILCRM_URL не задан"
        assert CRM_KEY, "RETAILCRM_API_KEY не задан"

    def test_api_key_valid_and_orders_accessible(self):
        """API-ключ принят CRM и эндпоинт заказов отвечает"""
        resp = requests.get(
            f"{CRM_URL}/api/v5/orders",
            params={"apiKey": CRM_KEY, "limit": 20, "page": 1},
            timeout=10,
        )
        assert resp.status_code == 200, f"HTTP {resp.status_code}"
        data = resp.json()
        assert data.get("success") is True, (
            f"CRM вернул ошибку: {data.get('errorMsg')}. "
            "Проверь RETAILCRM_API_KEY в .env"
        )

    def test_orders_endpoint_accessible(self):
        """Эндпоинт заказов возвращает корректный ответ"""
        resp = requests.get(
            f"{CRM_URL}/api/v5/orders",
            params={"apiKey": CRM_KEY, "limit": 20, "page": 1},
            timeout=10,
        )
        data = resp.json()
        assert data.get("success") is True
        assert "orders" in data
        assert "pagination" in data


# ─── Supabase ─────────────────────────────────────────────────────────────────

class TestSupabase:
    HEADERS = {
        "Authorization": f"Bearer {SB_SECRET}",
        "apikey": SB_SECRET,
        "Content-Type": "application/json",
    }

    def test_env_vars_present(self):
        """Ключи Supabase заданы в .env"""
        assert SB_URL, "SUPABASE_URL не задан"
        assert SB_SECRET, "SUPABASE_SECRET_KEY не задан"

    def test_api_reachable(self):
        """Supabase REST API отвечает"""
        resp = requests.get(
            f"{SB_URL}/rest/v1/",
            headers=self.HEADERS,
            timeout=10,
        )
        # 200 = ок, 404 = нет таблицы (всё равно API живой)
        assert resp.status_code in (200, 404), f"Неожиданный статус: {resp.status_code}"

    def test_orders_table_exists(self):
        """Таблица orders создана (нужно сначала запустить supabase/schema.sql)"""
        resp = requests.get(
            f"{SB_URL}/rest/v1/orders",
            headers=self.HEADERS,
            params={"limit": "1"},
            timeout=10,
        )
        assert resp.status_code == 200, (
            f"Таблица не найдена (статус {resp.status_code}). "
            "Запусти supabase/schema.sql в Supabase SQL Editor."
        )

    def test_orders_table_schema(self):
        """Таблица возвращает JSON-массив"""
        resp = requests.get(
            f"{SB_URL}/rest/v1/orders",
            headers=self.HEADERS,
            params={"limit": "1"},
            timeout=10,
        )
        data = resp.json()
        assert isinstance(data, list), f"Ожидали список, получили: {type(data)}"


# ─── Telegram ─────────────────────────────────────────────────────────────────

class TestTelegram:
    def test_env_vars_present(self):
        """Telegram-переменные заданы в .env"""
        assert TG_TOKEN, "TELEGRAM_BOT_TOKEN не задан"
        assert TG_CHAT_ID, "TELEGRAM_CHAT_ID не задан"

    def test_bot_token_valid(self):
        """Токен бота валиден"""
        resp = requests.get(
            f"https://api.telegram.org/bot{TG_TOKEN}/getMe",
            timeout=10,
        )
        data = resp.json()
        assert data.get("ok") is True, f"Telegram ошибка: {data.get('description')}"

    def test_bot_info(self):
        """Бот существует и активен"""
        resp = requests.get(
            f"https://api.telegram.org/bot{TG_TOKEN}/getMe",
            timeout=10,
        )
        bot = resp.json().get("result", {})
        assert bot.get("is_bot") is True
        print(f"\n  Бот: @{bot.get('username')} (ID: {bot.get('id')})")

    def test_can_send_message(self):
        """Бот может отправить сообщение в чат (тестовый пинг)"""
        resp = requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={
                "chat_id": TG_CHAT_ID,
                "text": "✅ <b>Тест соединения</b>\nRetail Dashboard подключён.",
                "parse_mode": "HTML",
            },
            timeout=10,
        )
        data = resp.json()
        assert data.get("ok") is True, (
            f"Не удалось отправить сообщение: {data.get('description')}. "
            f"Убедись что ты написал боту /start в Telegram."
        )
