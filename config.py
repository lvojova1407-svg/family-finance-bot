"""
КОНФИГУРАЦИЯ БОТА
"""

import os

# ========== TELEGRAM ==========
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# ========== ЯНДЕКС.ДИСК ==========
YANDEX_TOKEN = os.getenv("YANDEX_TOKEN", "")
PUBLIC_KEY = os.getenv("PUBLIC_KEY", "")

# ========== НАСТРОЙКИ ==========
LOCAL_EXCEL_PATH = "budget.xlsx"
VERSION = "5.0"

# ========== ДЛЯ АВТО-ПИНГА ==========
PORT = int(os.getenv("PORT", 10000))
RENDER_URL = os.getenv("RENDER_URL", "https://family-finance-bot.onrender.com")
