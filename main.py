"""
ОСНОВНОЙ МОДУЛЬ TELEGRAM-БОТА
Версия 9.1 - С НАДЕЖНОЙ АРХИТЕКТУРОЙ (как в проекте А)
"""

import asyncio
import logging
import re
import os
import sys
import threading
import time
import random
from datetime import datetime, timezone, timedelta
from typing import Optional

# Telegram (используем python-telegram-bot как в проекте А)
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application, 
    CommandHandler, 
    CallbackQueryHandler, 
    ContextTypes,
    MessageHandler,
    filters,
    ConversationHandler
)

# FastAPI
from fastapi import FastAPI
import uvicorn
import requests

from config import BOT_TOKEN, VERSION, PORT, RENDER_URL, LOCAL_EXCEL_PATH
from yandex_disk import add_expense, add_income, delete_last, download_from_yandex, get_statistics

# Настройка логгирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ========== FastAPI для Render ==========
app = FastAPI(title="Family Finance Bot")

# Глобальные переменные
bot_app: Optional[Application] = None
startup_time = datetime.now(timezone.utc)

# Состояния для ConversationHandler
(
    WAITING_EXPENSE_AMOUNT, 
    WAITING_INCOME_AMOUNT
) = range(2)

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
    """Получить текущее время по Москве"""
    moscow_tz = timezone(timedelta(hours=3))
    return datetime.now(moscow_tz).strftime("%H:%M:%S")

def get_current_date() -> str:
    """Получить текущую дату"""
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
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text="🗑 Удалить последний расход", callback_data="delete_expense")],
        [InlineKeyboardButton(text="🗑 Удалить последний доход", callback_data="delete_income")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="stats_menu")]
    ])

# ========== ОБРАБОТЧИКИ КОМАНД ==========
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    logger.info(f"🚀 /start от {user.id}")
    
    await update.message.reply_text(
        f"👋 <b>Добро пожаловать, {user.first_name}!</b>\n\n"
        f"👇 <b>Выберите действие:</b>",
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
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
    """Обработчик команды /stats"""
    await update.message.reply_text(
        "📊 <b>Меню статистики и файлов:</b>",
        reply_markup=get_stats_keyboard(),
        parse_mode="HTML"
    )

async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /ping"""
    await update.message.reply_text(f"🏓 Pong! Время: {get_moscow_time()}")

async def debug_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /debug - проверка работы"""
    user = update.effective_user
    logger.info(f"🔍 /debug от {user.id}")
    
    response = (
        f"🔧 Диагностика\n\n"
        f"🤖 Бот: ✅\n"
        f"🕐 {get_moscow_time()} · 📅 {get_current_date()}\n"
        f"📊 Версия: {VERSION}"
    )
    
    await update.message.reply_text(response)

# ========== ОБРАБОТЧИКИ КОЛЛБЭКОВ ==========
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на inline-кнопки"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    
    logger.info(f"🔘 Кнопка: {data} от {user_id}")
    
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
                with open(LOCAL_EXCEL_PATH, "rb") as f:
                    await context.bot.send_document(
                        chat_id=query.message.chat_id,
                        document=f,
                        filename="budget.xlsx",
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
        context.user_data["waiting_for"] = "expense"
        await query.edit_message_text(
            "💰 <b>Введите сумму расхода</b>\n(только цифры, например: 1500)",
            parse_mode="HTML"
        )
        return WAITING_EXPENSE_AMOUNT
    
    elif data == "income":
        await query.edit_message_text(
            "💵 <b>Выберите источник дохода:</b>",
            reply_markup=get_income_sources_keyboard(),
            parse_mode="HTML"
        )
    
    elif data.startswith("source_"):
        source = data[7:]
        context.user_data["source"] = source
        context.user_data["waiting_for"] = "income"
        await query.edit_message_text(
            "💰 <b>Введите сумму дохода</b>\n(только цифры, например: 50000)",
            parse_mode="HTML"
        )
        return WAITING_INCOME_AMOUNT
    
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
    
    return ConversationHandler.END

# ========== ОБРАБОТЧИКИ СООБЩЕНИЙ ==========
async def handle_expense_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ввода суммы расхода"""
    text = update.message.text.strip()
    amount_str = re.sub(r"[^\d.,]", "", text).replace(",", ".")
    
    try:
        amount = float(amount_str)
        if amount <= 0 or amount > 1_000_000:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Введите корректное число (от 1 до 1 000 000):")
        return WAITING_EXPENSE_AMOUNT
    
    category = context.user_data.get("category")
    payer = context.user_data.get("payer")
    method = context.user_data.get("method")
    
    if not all([category, payer, method]):
        await update.message.reply_text(
            "❌ Ошибка сессии. Начните заново.",
            reply_markup=get_main_keyboard()
        )
        context.user_data.clear()
        return ConversationHandler.END
    
    result = add_expense(category, amount, payer, method)
    await update.message.reply_text(result)
    await update.message.reply_text(
        "👇 Выберите следующее действие:",
        reply_markup=get_main_keyboard()
    )
    
    context.user_data.clear()
    return ConversationHandler.END

async def handle_income_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ввода суммы дохода"""
    text = update.message.text.strip()
    amount_str = re.sub(r"[^\d.,]", "", text).replace(",", ".")
    
    try:
        amount = float(amount_str)
        if amount <= 0 or amount > 10_000_000:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Введите корректное число (от 1 до 10 000 000):")
        return WAITING_INCOME_AMOUNT
    
    source = context.user_data.get("source")
    
    if not source:
        await update.message.reply_text(
            "❌ Ошибка сессии. Начните заново.",
            reply_markup=get_main_keyboard()
        )
        context.user_data.clear()
        return ConversationHandler.END
    
    payer = "Муж" if "Муж" in source else "Жена"
    result = add_income(source, amount, payer)
    
    await update.message.reply_text(result)
    await update.message.reply_text(
        "👇 Выберите следующее действие:",
        reply_markup=get_main_keyboard()
    )
    
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена действия"""
    await update.message.reply_text(
        "Действие отменено",
        reply_markup=get_main_keyboard()
    )
    context.user_data.clear()
    return ConversationHandler.END

async def handle_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик неизвестных сообщений"""
    await update.message.reply_text(
        "❓ Используйте кнопки меню 👇",
        reply_markup=get_main_keyboard()
    )

# ================== ЗАПУСК ТЕЛЕГРАМ БОТА ==================
async def setup_bot_commands(application: Application):
    """Установка команд для меню Telegram"""
    commands = [
        BotCommand("start", "🏠 Главное меню"),
        BotCommand("stats", "📊 Статистика"),
        BotCommand("help", "❓ Помощь"),
        BotCommand("ping", "🏓 Проверка"),
        BotCommand("debug", "🔧 Диагностика"),
    ]
    await application.bot.set_my_commands(commands)
    logger.info("✅ Команды меню установлены")

async def start_bot():
    """Запуск Telegram бота"""
    global bot_app
    
    logger.info("🤖 Инициализация Telegram бота...")
    
    await asyncio.sleep(5)
    
    try:
        bot_app = Application.builder().token(BOT_TOKEN).build()
        logger.info("✅ Приложение создано")
        
        # Устанавливаем команды меню
        await setup_bot_commands(bot_app)
        
        # Создаем ConversationHandler для расходов и доходов
        expense_conv = ConversationHandler(
            entry_points=[CallbackQueryHandler(button_callback, pattern="^method_")],
            states={
                WAITING_EXPENSE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_expense_amount)]
            },
            fallbacks=[CommandHandler("cancel", cancel)]
        )
        
        income_conv = ConversationHandler(
            entry_points=[CallbackQueryHandler(button_callback, pattern="^source_")],
            states={
                WAITING_INCOME_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_income_amount)]
            },
            fallbacks=[CommandHandler("cancel", cancel)]
        )
        
        # Добавляем обработчики команд
        bot_app.add_handler(CommandHandler("start", start_command))
        bot_app.add_handler(CommandHandler("help", help_command))
        bot_app.add_handler(CommandHandler("stats", stats_command))
        bot_app.add_handler(CommandHandler("ping", ping_command))
        bot_app.add_handler(CommandHandler("debug", debug_command))
        bot_app.add_handler(CommandHandler("cancel", cancel))
        
        # Добавляем ConversationHandler
        bot_app.add_handler(expense_conv)
        bot_app.add_handler(income_conv)
        
        # Добавляем обработчик inline-кнопок (для всех остальных callback)
        bot_app.add_handler(CallbackQueryHandler(button_callback))
        
        # Добавляем обработчик неизвестных сообщений
        bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unknown))
        
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

# ================== АВТО-ПИНГ ==================
def start_auto_ping():
    """Запускает авто-пинг в отдельном потоке (как в проекте А)"""
    def ping_worker():
        time.sleep(30)
        url = f"{RENDER_URL.rstrip('/')}"
        logger.info(f"🧵 Авто-пинг запущен для {url}")
        
        ping_count = 0
        while True:
            ping_count += 1
            try:
                # Пингуем health-эндпоинт
                response = requests.get(f"{url}/health", timeout=10)
                if response.status_code == 200:
                    logger.info(f"✅ Авто-пинг #{ping_count} успешен")
                else:
                    logger.warning(f"⚠️ Авто-пинг #{ping_count}: код {response.status_code}")
            except Exception as e:
                logger.error(f"❌ Ошибка авто-пинга #{ping_count}: {e}")
            
            # Пинг каждые 8 минут (480 секунд) - как в проекте А
            time.sleep(480)
    
    thread = threading.Thread(target=ping_worker, daemon=True)
    thread.start()
    logger.info("✅ Поток авто-пинга создан")
    return thread

# ================== FASTAPI ЭНДПОИНТЫ ==================
@app.get("/")
@app.get("/health")
@app.get("/ping")
async def health_check():
    """Health check для Render"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "bot_running": bool(bot_app),
        "time_moscow": get_moscow_time(),
        "version": VERSION
    }

@app.get("/status")
async def status():
    """Статус системы"""
    return {
        "server": {
            "uptime": str(datetime.now(timezone.utc) - startup_time),
            "port": PORT,
            "startup_time": startup_time.isoformat()
        },
        "bot": {
            "initialized": bool(bot_app),
            "version": VERSION
        }
    }

# ================== ЗАПУСК ПРИЛОЖЕНИЯ ==================
@app.on_event("startup")
async def startup_event():
    """Запуск при старте приложения"""
    logger.info("=" * 60)
    logger.info(f"🚀 ЗАПУСК ФИНАНСОВОГО БОТА v{VERSION}")
    logger.info("=" * 60)
    
    logger.info(f"✅ Токен бота: Найден")
    logger.info(f"⏰ Время по Москве: {get_moscow_time()}")
    logger.info(f"📅 Дата: {get_current_date()}")
    logger.info(f"🌐 Порт: {PORT}")
    logger.info(f"🌍 Render URL: {RENDER_URL}")
    logger.info("=" * 60)
    
    # Запускаем авто-пинг (как в проекте А)
    start_auto_ping()
    logger.info("🔧 Авто-пинг запущен (пинг каждые 8 минут)")
    
    # Запускаем бота
    success = await start_bot()
    
    if success:
        logger.info("🎉 Все системы запущены и готовы к работе!")
    else:
        logger.error("💥 Не удалось запустить бота!")

@app.on_event("shutdown")
async def shutdown_event():
    """Остановка при завершении"""
    logger.info("🛑 Завершение работы...")
    
    if bot_app:
        try:
            await bot_app.updater.stop()
            await bot_app.stop()
            await bot_app.shutdown()
            logger.info("✅ Telegram бот остановлен")
        except Exception as e:
            logger.error(f"❌ Ошибка при остановке бота: {e}")
    
    logger.info("👋 Сервер остановлен")

# ================== ТОЧКА ВХОДА ==================
def main():
    """Основная функция запуска"""
    logger.info(f"🌍 Запуск сервера на порту {PORT}...")
    
    uvicorn.run(
        "main:app",  # Важно: используем строковый импорт
        host="0.0.0.0",
        port=PORT,
        access_log=False,
        log_level="info",
        reload=False  # Отключаем reload для продакшена
    )

if __name__ == "__main__":
    main()
