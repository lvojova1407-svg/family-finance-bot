"""
КОНФИГУРАЦИЯ БОТА
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Токен Telegram бота
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Токен Яндекс.Диска (получить можно на https://yandex.ru/dev/disk/poligon/)
YANDEX_DISK_TOKEN = os.getenv("YANDEX_DISK_TOKEN")

# Путь к Excel файлу на Яндекс.Диске
EXCEL_FILE_PATH = "disk:/Финансы/budget.xlsx"

# Версия бота
VERSION = "2.0.0"
