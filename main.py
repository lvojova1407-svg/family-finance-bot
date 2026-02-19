"""
ОСНОВНОЙ МОДУЛЬ TELEGRAM-БОТА
Версия 5.2 - С ВЕБ-СЕРВЕРОМ ДЛЯ RENDER
"""

import os
import sys
import asyncio
import logging
import threading
import time
import requests
import re
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List

from fastapi import FastAPI
import uvicorn

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)

from config import BOT_TOKEN, VERSION, PORT, RENDER_URL
from yandex_disk import add_expense, add_income, delete_last, download_from_yandex, get_statistics

# ========== НАСТРОЙКА ЛОГГИРОВАНИЯ ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ========== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ==========
bot_app: Optional[Application] = None
startup_time = datetime.now(timezone.utc)

# ========== FASTAPI ПРИЛОЖЕНИЕ ==========
web_app = FastAPI(
    title="Family Finance Bot",
    description="Бот для учета семейных финансов",
    version=VERSION
)

# ========== ДАННЫЕ ==========
ALL_CATEGORIES = [
    "🛒 Продукты", "🏠 Коммуналка", "🚗 Транспорт", "💳 Кредиты",
    "🌿 Зелень", "💊 Лекарства и лечение", "🚬 Сигареты и алко",
    "🐱 Кошка", "🧹 Быт расходники", "🎮 Развлечения и хобби",
    "🔨 Дом/ремонт", "👕 Одежда и обувь", "💇 Красота/Уход", "📦 Другое"
]

PRIORITY_CATEGORIES = [
    "🛒 Продукты", "🚗 Транспорт", "🚬 Сигареты и алко",
    "🏠 Коммуналка", "💳 Кредиты", "🎮 Развлечения и хобби"
]

HIDDEN_CATEGORIES = [cat for cat in ALL_CATEGORIES if cat not in PRIORITY_CATEGORIES]

INCOME_SOURCES = ["💼 Зарплата (Жена)", "💼 Зарплата (Муж)", "💻 Подработка (Муж)"]
PAYERS = ["👩 Жена", "👨 Муж"]
PAYMENT_METHODS = ["💵 Наличные", "💳 Карта Муж", "💳 Карта Жена", "📌 Другое"]


# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
def get_moscow_time() -> str:
    moscow_tz = timezone(timedelta(hours=3))
    return datetime.now(moscow_tz).strftime("%H:%M:%S")

def get_current_date() -> str:
    return datetime.now(timezone(timedelta(hours=3))).strftime("%Y-%m-%d")


# ========== КЛАВИАТУРЫ ==========
def get_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("💰 Расход", callback_data="expense")],
        [InlineKeyboardButton("💵 Доход", callback_data="income")],
        [InlineKeyboardButton("❌ Удалить последнее", callback_data="delete_last")],
        [InlineKeyboardButton("📊 Статистика и файлы", callback_data="stats_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_stats_keyboard():
    keyboard = [
        [InlineKeyboardButton("📥 Скачать Excel файл", callback_data="download_excel")],
        [InlineKeyboardButton("📈 Статистика за период", callback_data="stats_period")],
        [InlineKeyboardButton("💰 Расходы по категориям", callback_data="stats_categories")],
        [InlineKeyboardButton("📊 Баланс", callback_data="stats_balance")],
        [InlineKeyboardButton("🔙 Назад в главное меню", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_period_keyboard():
    keyboard = [
        [InlineKeyboardButton("📅 Текущий период (10-24)", callback_data="period_current")],
        [InlineKeyboardButton("📅 Предыдущий период (25-9)", callback_data="period_previous")],
        [InlineKeyboardButton("📅 За всё время", callback_data="period_all")],
        [InlineKeyboardButton("🔙 Назад", callback_data="stats_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_categories_keyboard():
    keyboard = []
    for i in range(0, len(PRIORITY_CATEGORIES), 2):
        row = []
        row.append(InlineKeyboardButton(text=PRIORITY_CATEGORIES[i], callback_data=f"cat_{PRIORITY_CATEGORIES[i]}"))
        if i + 1 < len(PRIORITY_CATEGORIES):
            row.append(InlineKeyboardButton(text=PRIORITY_CATEGORIES[i + 1], callback_data=f"cat_{PRIORITY_CATEGORIES[i + 1]}"))
        keyboard.append(row)
    
    if HIDDEN_CATEGORIES:
        keyboard.append([InlineKeyboardButton(text="📋 Другие категории...", callback_data="show_hidden_categories")])
    
    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(keyboard)

def get_hidden_categories_keyboard():
    keyboard = []
    for i in range(0, len(HIDDEN_CATEGORIES), 2):
        row = []
        row.append(InlineKeyboardButton(text=HIDDEN_CATEGORIES[i], callback_data=f"cat_{HIDDEN_CATEGORIES[i]}"))
        if i + 1 < len(HIDDEN_CATEGORIES):
            row.append(InlineKeyboardButton(text=HIDDEN_CATEGORIES[i + 1], callback_data=f"cat_{HIDDEN_CATEGORIES[i + 1]}"))
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton(text="🔙 Назад к основным категориям", callback_data="back_to_main_categories")])
    return InlineKeyboardMarkup(keyboard)

def get_payers_keyboard():
    keyboard = [[InlineKeyboardButton(text=p, callback_data=f"payer_{p}")] for p in PAYERS]
    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_categories")])
    return InlineKeyboardMarkup(keyboard)

def get_payment_methods_keyboard():
    keyboard = []
    for i in range(0, len(PAYMENT_METHODS), 2):
        row = []
        row.append(InlineKeyboardButton(text=PAYMENT_METHODS[i], callback_data=f"method_{PAYMENT_METHODS[i]}"))
        if i + 1 < len(PAYMENT_METHODS):
            row.append(InlineKeyboardButton(text=PAYMENT_METHODS[i + 1], callback_data=f"method_{PAYMENT_METHODS[i + 1]}"))
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_payers")])
    return InlineKeyboardMarkup(keyboard)

def get_income_sources_keyboard():
    keyboard = [[InlineKeyboardButton(text=s, callback_data=f"source_{s}")] for s in INCOME_SOURCES]
    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(keyboard)

def get_delete_keyboard():
    keyboard = [
        [InlineKeyboardButton(text="🗑 Удалить последний расход", callback_data="delete_expense")],
        [InlineKeyboardButton(text="🗑 Удалить последний доход", callback_data="delete_income")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="stats_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


# ========== FASTAPI ЭНДПОИНТЫ ==========
@web_app.get("/")
@web_app.get("/health")
@web_app.get("/ping")
async def health_check():
    """Health check для Render"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "bot_running": bool(bot_app),
        "time_moscow": get_moscow_time(),
        "date": get_current_date(),
        "version": VERSION
    }

@web_app.get("/stats")
async def stats():
    """Статистика сервера"""
    return {
        "uptime": str(datetime.now(timezone.utc) - startup_time),
        "port": PORT,
        "bot_initialized": bool(bot_app)
    }


# ========== ЗАПУСК ВЕБ-СЕРВЕРА В ОТДЕЛЬНОМ ПОТОКЕ ==========
def run_web_server():
    """Запуск FastAPI сервера в отдельном потоке"""
    uvicorn.run(web_app, host="0.0.0.0", port=PORT, log_level="error")

# Запускаем веб-сервер сразу
web_thread = threading.Thread(target=run_web_server, daemon=True)
web_thread.start()
logger.info(f"🌍 Веб-сервер запущен на порту {PORT}")


# ========== АВТО-ПИНГ ==========
def start_auto_ping():
    """Запускает авто-пинг в отдельном потоке"""
    def ping_worker():
        time.sleep(30)  # Даем время на запуск
        url = f"{RENDER_URL.rstrip('/')}/health"
        logger.info(f"🧵 Авто-пинг запущен для {url}")
        
        ping_count = 0
        while True:
            ping_count += 1
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    logger.info(f"✅ Авто-пинг #{ping_count} успешен")
                else:
                    logger.info(f"📡 Авто-пинг #{ping_count}: код {response.status_code}")
            except Exception as e:
                logger.debug(f"Авто-пинг #{ping_count}: {e}")
            
            time.sleep(240)  # 4 минуты (Render убивает через 5 минут)
    
    thread = threading.Thread(target=ping_worker, daemon=True)
    thread.start()
    logger.info("✅ Поток авто-пинга создан")


# ========== ОБРАБОТЧИКИ КОМАНД ==========
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    await update.message.reply_text(
        f"👋 <b>Добро пожаловать, {user_name}!</b>\n\n"
        f"👇 <b>Выберите действие:</b>",
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
<b>🤖 КАК ПОЛЬЗОВАТЬСЯ:</b>

💰 <b>РАСХОД:</b>
1. Нажмите "💰 Расход"
2. Выберите категорию
3. Выберите кто платил
4. Выберите способ оплаты
5. Введите сумму

💵 <b>ДОХОД:</b>
1. Нажмите "💵 Доход"
2. Выберите источник
3. Введите сумму

❌ <b>УДАЛИТЬ:</b>
1. Нажмите "❌ Удалить последнее"
2. Выберите что удалить

📊 <b>СТАТИСТИКА:</b>
1. Нажмите "📊 Статистика и файлы"
2. Выберите нужный пункт
    """
    await update.message.reply_text(help_text, parse_mode="HTML")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📊 <b>Меню статистики и файлов:</b>",
        reply_markup=get_stats_keyboard(),
        parse_mode="HTML"
    )

async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🏓 Pong! Время: {get_moscow_time()}")


# ========== ОБРАБОТЧИКИ КОЛЛБЭКОВ ==========
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "back_main":
        await query.edit_message_text(
            "Выберите действие:",
            reply_markup=get_main_keyboard()
        )
    
    elif data == "stats_menu":
        await query.edit_message_text(
            "📊 <b>Меню статистики и файлов:</b>\n\nВыберите нужный пункт:",
            reply_markup=get_stats_keyboard(),
            parse_mode="HTML"
        )
    
    elif data == "download_excel":
        await query.edit_message_text("⏬ Скачиваю файл с Яндекс.Диска...")
        
        if download_from_yandex():
            try:
                with open("budget.xlsx", "rb") as f:
                    await context.bot.send_document(
                        chat_id=query.message.chat_id,
                        document=f,
                        caption="📁 Ваш файл budget.xlsx"
                    )
                await query.message.reply_text(
                    "Выберите действие:",
                    reply_markup=get_stats_keyboard()
                )
            except Exception as e:
                logger.error(f"Ошибка отправки файла: {e}")
                await query.message.reply_text(
                    "❌ Ошибка при отправке файла",
                    reply_markup=get_stats_keyboard()
                )
        else:
            await query.message.reply_text(
                "❌ Не удалось скачать файл с Яндекс.Диска",
                reply_markup=get_stats_keyboard()
            )
    
    elif data == "stats_period":
        await query.edit_message_text(
            "📅 <b>Выберите период:</b>",
            reply_markup=get_period_keyboard(),
            parse_mode="HTML"
        )
    
    elif data == "stats_categories":
        await query.edit_message_text("⏳ Считаю расходы по категориям...")
        stats_text = get_statistics(by_categories=True)
        await query.edit_message_text(
            f"📊 <b>Расходы по категориям:</b>\n\n{stats_text}",
            reply_markup=get_stats_keyboard(),
            parse_mode="HTML"
        )
    
    elif data == "stats_balance":
        await query.edit_message_text("⏳ Считаю баланс...")
        balance_text = get_statistics(balance=True)
        await query.edit_message_text(
            f"💰 <b>Текущий баланс:</b>\n\n{balance_text}",
            reply_markup=get_stats_keyboard(),
            parse_mode="HTML"
        )
    
    elif data == "period_current":
        await query.edit_message_text("⏳ Считаю статистику за текущий период...")
        stats_text = get_statistics(period="current")
        await query.edit_message_text(
            f"📊 <b>Статистика за текущий период (10-24):</b>\n\n{stats_text}",
            reply_markup=get_stats_keyboard(),
            parse_mode="HTML"
        )
    
    elif data == "period_previous":
        await query.edit_message_text("⏳ Считаю статистику за предыдущий период...")
        stats_text = get_statistics(period="previous")
        await query.edit_message_text(
            f"📊 <b>Статистика за предыдущий период (25-9):</b>\n\n{stats_text}",
            reply_markup=get_stats_keyboard(),
            parse_mode="HTML"
        )
    
    elif data == "period_all":
        await query.edit_message_text("⏳ Считаю статистику за всё время...")
        stats_text = get_statistics(period="all")
        await query.edit_message_text(
            f"📊 <b>Статистика за всё время:</b>\n\n{stats_text}",
            reply_markup=get_stats_keyboard(),
            parse_mode="HTML"
        )
    
    elif data == "expense":
        await query.edit_message_text(
            "📌 <b>Выберите категорию расхода:</b>",
            reply_markup=get_categories_keyboard(),
            parse_mode="HTML"
        )
    
    elif data == "show_hidden_categories":
        await query.edit_message_text(
            "📌 <b>Дополнительные категории:</b>",
            reply_markup=get_hidden_categories_keyboard(),
            parse_mode="HTML"
        )
    
    elif data == "back_to_main_categories":
        await query.edit_message_text(
            "📌 <b>Выберите категорию расхода:</b>",
            reply_markup=get_categories_keyboard(),
            parse_mode="HTML"
        )
    
    elif data == "back_to_categories":
        await query.edit_message_text(
            "📌 <b>Выберите категорию расхода:</b>",
            reply_markup=get_categories_keyboard(),
            parse_mode="HTML"
        )
    
    elif data.startswith("cat_"):
        category = data[4:]
        context.user_data["category"] = category
        await query.edit_message_text(
            "👤 <b>Кто платил?</b>",
            reply_markup=get_payers_keyboard(),
            parse_mode="HTML"
        )
    
    elif data.startswith("payer_"):
        payer = data[6:]
        context.user_data["payer"] = payer
        await query.edit_message_text(
            "💳 <b>Способ оплаты:</b>",
            reply_markup=get_payment_methods_keyboard(),
            parse_mode="HTML"
        )
    
    elif data == "back_to_payers":
        await query.edit_message_text(
            "👤 <b>Кто платил?</b>",
            reply_markup=get_payers_keyboard(),
            parse_mode="HTML"
        )
    
    elif data.startswith("method_"):
        method = data[7:]
        context.user_data["method"] = method
        context.user_data["awaiting"] = "expense_amount"
        await query.edit_message_text(
            "💰 <b>Введите сумму расхода</b>\n(только цифры, например: 1500)",
            parse_mode="HTML"
        )
    
    elif data == "income":
        await query.edit_message_text(
            "💵 <b>Выберите источник дохода:</b>",
            reply_markup=get_income_sources_keyboard(),
            parse_mode="HTML"
        )
    
    elif data.startswith("source_"):
        source = data[7:]
        context.user_data["source"] = source
        context.user_data["awaiting"] = "income_amount"
        await query.edit_message_text(
            "💰 <b>Введите сумму дохода</b>\n(только цифры, например: 50000)",
            parse_mode="HTML"
        )
    
    elif data == "delete_last":
        await query.edit_message_text(
            "❓ <b>Что удалить?</b>",
            reply_markup=get_delete_keyboard(),
            parse_mode="HTML"
        )
    
    elif data == "delete_expense":
        result = delete_last("Расходы")
        await query.message.reply_text(result)
        await query.message.reply_text(
            "Выберите действие:",
            reply_markup=get_stats_keyboard()
        )
    
    elif data == "delete_income":
        result = delete_last("Доходы")
        await query.message.reply_text(result)
        await query.message.reply_text(
            "Выберите действие:",
            reply_markup=get_stats_keyboard()
        )


# ========== ОБРАБОТЧИКИ СООБЩЕНИЙ ==========
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    awaiting = context.user_data.get("awaiting")
    
    if awaiting == "expense_amount":
        amount_str = re.sub(r"[^\d.,]", "", text).replace(",", ".")
        
        try:
            amount = float(amount_str)
            if amount <= 0 or amount > 1_000_000:
                raise ValueError
        except ValueError:
            await update.message.reply_text("❌ Введите корректное число (от 1 до 1 000 000):")
            return
        
        category = context.user_data.get("category")
        payer = context.user_data.get("payer")
        method = context.user_data.get("method")
        
        if not all([category, payer, method]):
            await update.message.reply_text(
                "❌ Ошибка сессии. Начните заново.",
                reply_markup=get_main_keyboard()
            )
            context.user_data.clear()
            return
        
        result = add_expense(category, amount, payer, method)
        await update.message.reply_text(result)
        await update.message.reply_text(
            "👇 Выберите следующее действие:",
            reply_markup=get_main_keyboard()
        )
        context.user_data.clear()
    
    elif awaiting == "income_amount":
        amount_str = re.sub(r"[^\d.,]", "", text).replace(",", ".")
        
        try:
            amount = float(amount_str)
            if amount <= 0 or amount > 10_000_000:
                raise ValueError
        except ValueError:
            await update.message.reply_text("❌ Введите корректное число (от 1 до 10 000 000):")
            return
        
        source = context.user_data.get("source")
        
        if not source:
            await update.message.reply_text(
                "❌ Ошибка сессии. Начните заново.",
                reply_markup=get_main_keyboard()
            )
            context.user_data.clear()
            return
        
        payer = "Муж" if "Муж" in source else "Жена"
        result = add_income(source, amount, payer)
        
        await update.message.reply_text(result)
        await update.message.reply_text(
            "👇 Выберите следующее действие:",
            reply_markup=get_main_keyboard()
        )
        context.user_data.clear()
    
    else:
        await update.message.reply_text(
            "❓ Используйте кнопки меню 👇",
            reply_markup=get_main_keyboard()
        )


# ========== ЗАПУСК ТЕЛЕГРАМ БОТА ==========
async def start_bot():
    """Запуск Telegram бота"""
    global bot_app
    
    logger.info("🤖 Инициализация Telegram бота...")
    
    try:
        bot_app = Application.builder().token(BOT_TOKEN).build()
        logger.info("✅ Приложение создано")
        
        # Добавляем обработчики команд
        bot_app.add_handler(CommandHandler("start", start_command))
        bot_app.add_handler(CommandHandler("help", help_command))
        bot_app.add_handler(CommandHandler("stats", stats_command))
        bot_app.add_handler(CommandHandler("ping", ping_command))
        
        # Добавляем обработчик inline-кнопок
        bot_app.add_handler(CallbackQueryHandler(button_callback))
        
        # Добавляем обработчик сообщений
        bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        logger.info("✅ Все обработчики добавлены")
        
        await bot_app.initialize()
        await bot_app.start()
        
        await bot_app.updater.start_polling(
            poll_interval=1.0,
            timeout=20,
            drop_pending_updates=True
        )
        
        logger.info("✅ Telegram бот успешно запущен!")
        return True
        
    except Exception as e:
        logger.error(f"💥 Ошибка при запуске бота: {e}")
        return False


# ========== ОСНОВНАЯ ФУНКЦИЯ ==========
async def main():
    logger.info("=" * 50)
    logger.info(f"🚀 ЗАПУСК БОТА v{VERSION}")
    logger.info("=" * 50)
    
    logger.info(f"✅ Токен бота: Найден")
    logger.info(f"⏰ Время по Москве: {get_moscow_time()}")
    logger.info(f"📅 Дата: {get_current_date()}")
    logger.info(f"🌐 Порт: {PORT}")
    
    # Запускаем авто-пинг
    start_auto_ping()
    logger.info("🔧 Авто-пинг запущен (пинг каждые 4 минуты)")
    
    # Запускаем бота
    success = await start_bot()
    
    if success:
        logger.info("🎉 Бот успешно запущен!")
    else:
        logger.error("💥 Не удалось запустить бота!")


# ========== ТОЧКА ВХОДА ==========
if __name__ == "__main__":
    try:
        asyncio.run(main())
        # Бесконечное ожидание после завершения asyncio.run
        while True:
            time.sleep(60)
            logger.debug("Главный поток ожидает...")
    except KeyboardInterrupt:
        logger.info("👋 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")
        # Даже при ошибке держим процесс живым
        while True:
            time.sleep(60)
