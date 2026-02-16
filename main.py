"""
ОСНОВНОЙ МОДУЛЬ TELEGRAM-БОТА
Aiogram 3.4 | Python 3.11
"""

import asyncio
import logging
import re
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, VERSION
from yandex_disk import add_expense, add_income, delete_last

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ========== ИНИЦИАЛИЗАЦИЯ ==========
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)  # ← dp ДОЛЖЕН БЫТЬ ЗДЕСЬ, ДО ВСЕХ ДЕКОРАТОРОВ!

# ========== СОСТОЯНИЯ FSM ==========
class FinanceStates(StatesGroup):
    waiting_for_expense_amount = State()
    waiting_for_income_amount = State()


# ========== ДАННЫЕ ==========
# Полный список всех категорий
ALL_CATEGORIES = [
    "🛒 Продукты", "🏠 Коммуналка", "🚗 Транспорт", "💳 Кредиты",
    "🌿 Зелень", "💊 Лекарства и лечение", "🚬 Сигареты и алко",
    "🐱 Кошка", "🧹 Быт расходники", "🎮 Развлечения и хобби",
    "🔨 Дом/ремонт", "👕 Одежда и обувь", "💇 Красота/Уход", "📦 Другое"
]

# Приоритетные категории (в нужном порядке)
PRIORITY_CATEGORIES = [
    "🛒 Продукты",
    "🚗 Транспорт", 
    "🚬 Сигареты и алко",
    "🏠 Коммуналка",
    "💳 Кредиты",
    "🎮 Развлечения и хобби"
]

# Скрытые категории (остальные)
HIDDEN_CATEGORIES = [cat for cat in ALL_CATEGORIES if cat not in PRIORITY_CATEGORIES]

INCOME_SOURCES = ["💼 Зарплата (Жена)", "💼 Зарплата (Муж)", "💻 Подработка (Муж)"]
PAYERS = ["👩 Жена", "👨 Муж"]
PAYMENT_METHODS = ["💵 Наличные", "💳 Карта Муж", "💳 Карта Жена", "📌 Другое"]


# ========== КЛАВИАТУРЫ ==========
def get_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Расход", callback_data="expense")],
        [InlineKeyboardButton(text="💵 Доход", callback_data="income")],
        [InlineKeyboardButton(text="❌ Удалить последнее", callback_data="delete_last")]
    ])


def get_categories_keyboard():
    """Создает клавиатуру с приоритетными и скрытыми категориями"""
    keyboard = []
    
    # Добавляем приоритетные категории по две в ряд
    for i in range(0, len(PRIORITY_CATEGORIES), 2):
        row = []
        row.append(InlineKeyboardButton(
            text=PRIORITY_CATEGORIES[i], 
            callback_data=f"cat_{PRIORITY_CATEGORIES[i]}"
        ))
        if i + 1 < len(PRIORITY_CATEGORIES):
            row.append(InlineKeyboardButton(
                text=PRIORITY_CATEGORIES[i + 1], 
                callback_data=f"cat_{PRIORITY_CATEGORIES[i + 1]}"
            ))
        keyboard.append(row)
    
    # Добавляем кнопку "Другие категории"
    if HIDDEN_CATEGORIES:
        keyboard.append([
            InlineKeyboardButton(
                text="📋 Другие категории...", 
                callback_data="show_hidden_categories"
            )
        ])
    
    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_hidden_categories_keyboard():
    """Создает клавиатуру со скрытыми категориями"""
    keyboard = []
    
    # Показываем скрытые категории по две в ряд
    for i in range(0, len(HIDDEN_CATEGORIES), 2):
        row = []
        row.append(InlineKeyboardButton(
            text=HIDDEN_CATEGORIES[i], 
            callback_data=f"cat_{HIDDEN_CATEGORIES[i]}"
        ))
        if i + 1 < len(HIDDEN_CATEGORIES):
            row.append(InlineKeyboardButton(
                text=HIDDEN_CATEGORIES[i + 1], 
                callback_data=f"cat_{HIDDEN_CATEGORIES[i + 1]}"
            ))
        keyboard.append(row)
    
    # Кнопка возврата к основным категориям
    keyboard.append([
        InlineKeyboardButton(
            text="🔙 Назад к основным категориям", 
            callback_data="back_to_main_categories"
        )
    ])
    
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
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
    ])


# ========== ОБРАБОТЧИКИ ==========
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
    """
    await message.answer(help_text, parse_mode="HTML")


@dp.callback_query()
async def process_callback(callback: types.CallbackQuery, state: FSMContext):
    data = callback.data
    
    if data == "back_main":
        await callback.message.edit_text(
            "Выберите действие:",
            reply_markup=get_main_keyboard()
        )
        await callback.answer()
    
    elif data == "expense":
        await callback.message.edit_text(
            "📌 <b>Выберите категорию расхода:</b>\n\n"
            "📋 <b>Основные категории:</b>",
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
            "📌 <b>Выберите категорию расхода:</b>\n\n"
            "📋 <b>Основные категории:</b>",
            reply_markup=get_categories_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()
    
    elif data == "back_to_categories":
        await callback.message.edit_text(
            "📌 <b>Выберите категорию расхода:</b>\n\n"
            "📋 <b>Основные категории:</b>",
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
            "💰 <b>Введите сумму расхода</b>\n"
            "(только цифры, например: 1500)",
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
            "💰 <b>Введите сумму дохода</b>\n"
            "(только цифры, например: 50000)",
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
            reply_markup=get_main_keyboard()
        )
        await callback.answer()
    
    elif data == "delete_income":
        result = delete_last("Доходы")
        await callback.message.answer(result)
        await callback.message.answer(
            "Выберите действие:",
            reply_markup=get_main_keyboard()
        )
        await callback.answer()


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
    
    if "Муж" in source:
        payer = "Муж"
    else:
        payer = "Жена"
    
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


# ========== ЗАПУСК ==========
async def main():
    logger.info("=" * 50)
    logger.info(f"🚀 ЗАПУСК ФИНАНСОВОГО БОТА v{VERSION}")
    logger.info("=" * 50)
    
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
