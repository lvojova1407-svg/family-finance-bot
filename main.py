"""
ОСНОВНОЙ МОДУЛЬ TELEGRAM-БОТА
Версия 4.0 - С МИНУТНЫМ ПИНГОМ
"""

import os
import sys
import time
import subprocess
import signal
import asyncio
import logging
import re
import threading
import random
from datetime import datetime, timezone, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramConflictError

from fastapi import FastAPI
import uvicorn
import requests

from config import BOT_TOKEN, VERSION, PORT, RENDER_URL, LOCAL_EXCEL_PATH
from yandex_disk import add_expense, add_income, delete_last, download_from_yandex, get_statistics
from ping_service import ping_service

# ========== БЕЗОПАСНОЕ УБИЙСТВО СТАРЫХ ПРОЦЕССОВ ==========
def kill_old_processes():
    """Убивает все старые процессы бота, сохраняя текущий"""
    current_pid = os.getpid()
    print(f"🔍 Текущий PID: {current_pid}")
    
    try:
        # Получаем список всех процессов
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        lines = result.stdout.split('\n')
        
        killed = 0
        for line in lines:
            # Ищем процессы с main.py
            if 'python' in line and 'main.py' in line:
                parts = line.split()
                if len(parts) > 1:
                    try:
                        pid = int(parts[1])
                        # Не убиваем текущий процесс
                        if pid != current_pid:
                            print(f"🔥 Найден старый процесс PID: {pid}")
                            os.kill(pid, signal.SIGKILL)
                            killed += 1
                            time.sleep(0.5)
                    except (ValueError, IndexError):
                        continue
        
        if killed > 0:
            print(f"✅ Убито {killed} старых процессов")
            time.sleep(2)
        else:
            print("✅ Старых процессов не найдено")
            
    except Exception as e:
        print(f"⚠️ Ошибка при убийстве процессов: {e}")

# Вызываем функцию убийства старых процессов
kill_old_processes()

# Создаем файл блокировки с текущим PID
lock_file = "bot.lock"
with open(lock_file, 'w') as f:
    f.write(str(os.getpid()))
print(f"✅ Файл блокировки создан (PID: {os.getpid()})")

# ========== НАСТРОЙКА ЛОГГИРОВАНИЯ ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ========== ИНИЦИАЛИЗАЦИЯ БОТА ==========
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

logger.info("✅ Бот инициализирован")


# ========== ПРАВИЛЬНЫЙ ОБРАБОТЧИК ОШИБОК ==========
@dp.errors()
async def errors_handler(update: types.Update, exception: Exception):
    """Правильный обработчик ошибок aiogram"""
    try:
        if isinstance(exception, TelegramConflictError):
            logger.warning(f"⚠️ Конфликт (игнорируем)")
            return True
        else:
            logger.error(f"❌ Ошибка: {exception}")
            return True
    except Exception as e:
        logger.error(f"❌ Ошибка в обработчике: {e}")
        return True


class FinanceStates(StatesGroup):
    waiting_for_expense_amount = State()
    waiting_for_income_amount = State()


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
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Расход", callback_data="expense")],
        [InlineKeyboardButton(text="💵 Доход", callback_data="income")],
        [InlineKeyboardButton(text="❌ Удалить последнее", callback_data="delete_last")],
        [InlineKeyboardButton(text="📊 Статистика и файлы", callback_data="stats_menu")]
    ])

def get_stats_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Скачать Excel файл", callback_data="download_excel")],
        [InlineKeyboardButton(text="📈 Статистика за период", callback_data="stats_period")],
        [InlineKeyboardButton(text="💰 Расходы по категориям", callback_data="stats_categories")],
        [InlineKeyboardButton(text="📊 Баланс", callback_data="stats_balance")],
        [InlineKeyboardButton(text="🔙 Назад в главное меню", callback_data="back_main")]
    ])

def get_period_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Текущий период (10-24)", callback_data="period_current")],
        [InlineKeyboardButton(text="📅 Предыдущий период (25-9)", callback_data="period_previous")],
        [InlineKeyboardButton(text="📅 За всё время", callback_data="period_all")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="stats_menu")]
    ])

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
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_hidden_categories_keyboard():
    keyboard = []
    for i in range(0, len(HIDDEN_CATEGORIES), 2):
        row = []
        row.append(InlineKeyboardButton(text=HIDDEN_CATEGORIES[i], callback_data=f"cat_{HIDDEN_CATEGORIES[i]}"))
        if i + 1 < len(HIDDEN_CATEGORIES):
            row.append(InlineKeyboardButton(text=HIDDEN_CATEGORIES[i + 1], callback_data=f"cat_{HIDDEN_CATEGORIES[i + 1]}"))
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton(text="🔙 Назад к основным категориям", callback_data="back_to_main_categories")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_payers_keyboard():
    keyboard = [[InlineKeyboardButton(text=p, callback_data=f"payer_{p}")] for p in PAYERS]
    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_categories")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_payment_methods_keyboard():
    keyboard = []
    for i in range(0, len(PAYMENT_METHODS), 2):
        row = []
        row.append(InlineKeyboardButton(text=PAYMENT_METHODS[i], callback_data=f"method_{PAYMENT_METHODS[i]}"))
        if i + 1 < len(PAYMENT_METHODS):
            row.append(InlineKeyboardButton(text=PAYMENT_METHODS[i + 1], callback_data=f"method_{PAYMENT_METHODS[i + 1]}"))
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_payers")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_income_sources_keyboard():
    keyboard = [[InlineKeyboardButton(text=s, callback_data=f"source_{s}")] for s in INCOME_SOURCES]
    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_delete_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Удалить последний расход", callback_data="delete_expense")],
        [InlineKeyboardButton(text="🗑 Удалить последний доход", callback_data="delete_income")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="stats_menu")]
    ])


# ========== FASTAPI ДЛЯ ПИНГА ==========
app = FastAPI(title="Family Finance Bot")

@app.get("/")
@app.get("/health")
@app.get("/ping")
async def ping_endpoint():
    """Универсальный эндпоинт для пинга"""
    return {
        "status": "alive",
        "time": get_moscow_time(),
        "date": get_current_date(),
        "pid": os.getpid()
    }


# ========== ОБРАБОТЧИКИ КОМАНД ==========
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_name = message.from_user.first_name
    await message.answer(
        f"👋 <b>Добро пожаловать, {user_name}!</b>\n\n"
        f"👇 <b>Выберите действие:</b>",
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
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
    await message.answer(help_text, parse_mode="HTML")

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    await message.answer(
        "📊 <b>Меню статистики и файлов:</b>",
        reply_markup=get_stats_keyboard(),
        parse_mode="HTML"
    )

@dp.message(Command("ping"))
async def cmd_ping(message: types.Message):
    """Ручная проверка пинга"""
    await message.answer(f"🏓 Pong! Время: {get_moscow_time()}")


# ========== ОБРАБОТЧИКИ КОЛЛБЭКОВ ==========
@dp.callback_query()
async def process_callback(callback: types.CallbackQuery, state: FSMContext):
    data = callback.data
    
    if data == "back_main":
        await callback.message.edit_text(
            "Выберите действие:",
            reply_markup=get_main_keyboard()
        )
        await callback.answer()
    
    elif data == "stats_menu":
        await callback.message.edit_text(
            "📊 <b>Меню статистики и файлов:</b>\n\nВыберите нужный пункт:",
            reply_markup=get_stats_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()
    
    elif data == "download_excel":
        await callback.message.edit_text("⏬ Скачиваю файл с Яндекс.Диска...")
        
        if download_from_yandex():
            try:
                file_to_send = FSInputFile(LOCAL_EXCEL_PATH)
                await callback.message.answer_document(
                    file_to_send,
                    caption="📁 Ваш файл budget.xlsx"
                )
                await callback.message.answer(
                    "Выберите действие:",
                    reply_markup=get_stats_keyboard()
                )
            except Exception as e:
                logger.error(f"Ошибка отправки файла: {e}")
                await callback.message.answer(
                    "❌ Ошибка при отправке файла",
                    reply_markup=get_stats_keyboard()
                )
        else:
            await callback.message.answer(
                "❌ Не удалось скачать файл с Яндекс.Диска",
                reply_markup=get_stats_keyboard()
            )
        await callback.answer()
    
    elif data == "stats_period":
        await callback.message.edit_text(
            "📅 <b>Выберите период:</b>",
            reply_markup=get_period_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()
    
    elif data == "stats_categories":
        await callback.message.edit_text("⏳ Считаю расходы по категориям...")
        stats_text = get_statistics(by_categories=True)
        await callback.message.edit_text(
            f"📊 <b>Расходы по категориям:</b>\n\n{stats_text}",
            reply_markup=get_stats_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()
    
    elif data == "stats_balance":
        await callback.message.edit_text("⏳ Считаю баланс...")
        balance_text = get_statistics(balance=True)
        await callback.message.edit_text(
            f"💰 <b>Текущий баланс:</b>\n\n{balance_text}",
            reply_markup=get_stats_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()
    
    elif data == "period_current":
        await callback.message.edit_text("⏳ Считаю статистику за текущий период...")
        stats_text = get_statistics(period="current")
        await callback.message.edit_text(
            f"📊 <b>Статистика за текущий период (10-24):</b>\n\n{stats_text}",
            reply_markup=get_stats_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()
    
    elif data == "period_previous":
        await callback.message.edit_text("⏳ Считаю статистику за предыдущий период...")
        stats_text = get_statistics(period="previous")
        await callback.message.edit_text(
            f"📊 <b>Статистика за предыдущий период (25-9):</b>\n\n{stats_text}",
            reply_markup=get_stats_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()
    
    elif data == "period_all":
        await callback.message.edit_text("⏳ Считаю статистику за всё время...")
        stats_text = get_statistics(period="all")
        await callback.message.edit_text(
            f"📊 <b>Статистика за всё время:</b>\n\n{stats_text}",
            reply_markup=get_stats_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()
    
    elif data == "expense":
        await callback.message.edit_text(
            "📌 <b>Выберите категорию расхода:</b>",
            reply_markup=get_categories_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()
    
    elif data == "show_hidden_categories":
        await callback.message.edit_text(
            "📌 <b>Дополнительные категории:</b>",
            reply_markup=get_hidden_categories_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()
    
    elif data == "back_to_main_categories":
        await callback.message.edit_text(
            "📌 <b>Выберите категорию расхода:</b>",
            reply_markup=get_categories_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()
    
    elif data == "back_to_categories":
        await callback.message.edit_text(
            "📌 <b>Выберите категорию расхода:</b>",
            reply_markup=get_categories_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()
    
    elif data.startswith("cat_"):
        category = data[4:]
        await state.update_data(category=category)
        await callback.message.edit_text(
            "👤 <b>Кто платил?</b>",
            reply_markup=get_payers_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()
    
    elif data.startswith("payer_"):
        payer = data[6:]
        await state.update_data(payer=payer)
        await callback.message.edit_text(
            "💳 <b>Способ оплаты:</b>",
            reply_markup=get_payment_methods_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()
    
    elif data == "back_to_payers":
        await callback.message.edit_text(
            "👤 <b>Кто платил?</b>",
            reply_markup=get_payers_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()
    
    elif data.startswith("method_"):
        method = data[7:]
        await state.update_data(method=method)
        await state.set_state(FinanceStates.waiting_for_expense_amount)
        await callback.message.edit_text(
            "💰 <b>Введите сумму расхода</b>\n(только цифры, например: 1500)",
            parse_mode="HTML"
        )
        await callback.answer()
    
    elif data == "income":
        await callback.message.edit_text(
            "💵 <b>Выберите источник дохода:</b>",
            reply_markup=get_income_sources_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()
    
    elif data.startswith("source_"):
        source = data[7:]
        await state.update_data(source=source)
        await state.set_state(FinanceStates.waiting_for_income_amount)
        await callback.message.edit_text(
            "💰 <b>Введите сумму дохода</b>\n(только цифры, например: 50000)",
            parse_mode="HTML"
        )
        await callback.answer()
    
    elif data == "delete_last":
        await callback.message.edit_text(
            "❓ <b>Что удалить?</b>",
            reply_markup=get_delete_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()
    
    elif data == "delete_expense":
        result = delete_last("Расходы")
        await callback.message.answer(result)
        await callback.message.answer(
            "Выберите действие:",
            reply_markup=get_stats_keyboard()
        )
        await callback.answer()
    
    elif data == "delete_income":
        result = delete_last("Доходы")
        await callback.message.answer(result)
        await callback.message.answer(
            "Выберите действие:",
            reply_markup=get_stats_keyboard()
        )
        await callback.answer()


# ========== ОБРАБОТЧИКИ СООБЩЕНИЙ ==========
@dp.message(FinanceStates.waiting_for_expense_amount)
async def process_expense_amount(message: types.Message, state: FSMContext):
    text = message.text.strip()
    amount_str = re.sub(r"[^\d.,]", "", text).replace(",", ".")
    
    try:
        amount = float(amount_str)
        if amount <= 0 or amount > 1_000_000:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите корректное число (от 1 до 1 000 000):")
        return
    
    data = await state.get_data()
    category = data.get("category")
    payer = data.get("payer")
    method = data.get("method")
    
    if not all([category, payer, method]):
        await message.answer(
            "❌ Ошибка сессии. Начните заново.",
            reply_markup=get_main_keyboard()
        )
        await state.clear()
        return
    
    result = add_expense(category, amount, payer, method)
    await message.answer(result)
    await message.answer(
        "👇 Выберите следующее действие:",
        reply_markup=get_main_keyboard()
    )
    await state.clear()

@dp.message(FinanceStates.waiting_for_income_amount)
async def process_income_amount(message: types.Message, state: FSMContext):
    text = message.text.strip()
    amount_str = re.sub(r"[^\d.,]", "", text).replace(",", ".")
    
    try:
        amount = float(amount_str)
        if amount <= 0 or amount > 10_000_000:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите корректное число (от 1 до 10 000 000):")
        return
    
    data = await state.get_data()
    source = data.get("source")
    
    if not source:
        await message.answer(
            "❌ Ошибка сессии. Начните заново.",
            reply_markup=get_main_keyboard()
        )
        await state.clear()
        return
    
    payer = "Муж" if "Муж" in source else "Жена"
    result = add_income(source, amount, payer)
    
    await message.answer(result)
    await message.answer(
        "👇 Выберите следующее действие:",
        reply_markup=get_main_keyboard()
    )
    await state.clear()

@dp.message()
async def handle_unknown(message: types.Message):
    await message.answer(
        "❓ Используйте кнопки меню 👇",
        reply_markup=get_main_keyboard()
    )


# ========== ЗАПУСК БОТА ==========
async def main():
    logger.info("=" * 50)
    logger.info(f"🚀 ЗАПУСК БОТА v{VERSION} (PID: {os.getpid()})")
    logger.info("=" * 50)
    
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Вебхук удален")
    except Exception as e:
        logger.warning(f"⚠️ Ошибка удаления вебхука: {e}")
    
    # Случайная задержка
    delay = random.randint(5, 15)
    logger.info(f"⏳ Ожидание {delay} секунд...")
    await asyncio.sleep(delay)
    
    # Запускаем активный пинг (каждую минуту)
    ping_service.start()
    
    logger.info("✅ Запуск polling...")
    
    # ПРОСТО ЗАПУСКАЕМ - без while True
    await dp.start_polling(bot)


def run_fastapi():
    """Запуск FastAPI в отдельном потоке"""
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="error")


if __name__ == "__main__":
    # FastAPI в фоне
    fastapi_thread = threading.Thread(target=run_fastapi, daemon=True)
    fastapi_thread.start()
    logger.info(f"🌍 FastAPI запущен на порту {PORT}")
    
    # Небольшая пауза
    time.sleep(3)
    
    # Запуск бота
    asyncio.run(main())
