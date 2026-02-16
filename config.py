"""
КОНФИГУРАЦИЯ БОТА
"""
import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
YANDEX_TOKEN = os.getenv("YANDEX_TOKEN", "")
PUBLIC_KEY = os.getenv("PUBLIC_KEY", "")

LOCAL_EXCEL_PATH = "budget.xlsx"
VERSION = "3.0.0"  # Обновляем версию
