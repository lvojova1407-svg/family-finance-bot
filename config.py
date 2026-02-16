"""
КОНФИГУРАЦИЯ БОТА
Токены загружаются из переменных окружения!
"""

import os

# ========== TELEGRAM ==========
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# ========== ЯНДЕКС.ДИСК ==========
YANDEX_TOKEN = os.getenv("YANDEX_TOKEN", "")
PUBLIC_KEY = os.getenv("PUBLIC_KEY", "")

# ========== НАСТРОЙКИ ==========
LOCAL_EXCEL_PATH = "budget.xlsx"
VERSION = "2.0.0"
