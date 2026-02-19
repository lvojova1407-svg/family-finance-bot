import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
YANDEX_TOKEN = os.getenv("YANDEX_TOKEN", "")
PUBLIC_KEY = os.getenv("PUBLIC_KEY", "")
LOCAL_EXCEL_PATH = "budget.xlsx"
VERSION = "4.0"

PORT = int(os.getenv("PORT", 10000))
RENDER_URL = os.getenv("RENDER_URL", "https://family-finance-bot.onrender.com")
