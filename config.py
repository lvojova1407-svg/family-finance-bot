"""
КОНФИГУРАЦИЯ БОТА
Версия 6.1
"""

import os

# ========== TELEGRAM ==========
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# ========== ЯНДЕКС.ДИСК ==========
YANDEX_TOKEN = os.getenv("YANDEX_TOKEN", "")
PUBLIC_KEY = os.getenv("PUBLIC_KEY", "")

# ========== НАСТРОЙКИ ==========
LOCAL_EXCEL_PATH = "budget.xlsx"
VERSION = "6.1"

# ========== ДЛЯ ВЕБ-СЕРВЕРА И ПИНГА ==========
PORT = int(os.getenv("PORT", 10000))
RENDER_URL = os.getenv("RENDER_URL", "")
