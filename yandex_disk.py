"""
МОДУЛЬ РАБОТЫ С ЯНДЕКС.ДИСКОМ
Полная версия с исправленной функцией удаления
"""

import requests
from datetime import datetime
import logging
import time
from openpyxl import load_workbook
from config import YANDEX_TOKEN, PUBLIC_KEY, LOCAL_EXCEL_PATH

logger = logging.getLogger(__name__)


def download_from_yandex(max_retries=3):
    """Скачать файл с повторными попытками"""
    for attempt in range(max_retries):
        try:
            api_url = "https://cloud-api.yandex.net/v1/disk/public/resources/download"
            params = {"public_key": PUBLIC_KEY}
            response = requests.get(api_url, params=params, timeout=30)
            response.raise_for_status()
            
            download_url = response.json()["href"]
            response = requests.get(download_url, timeout=60)
            response.raise_for_status()
            
            with open(LOCAL_EXCEL_PATH, "wb") as f:
                f.write(response.content)
            
            logger.info("✅ Файл скачан с Яндекс.Диска")
            return True
            
        except Exception as e:
            logger.warning(f"Попытка {attempt + 1}/{max_retries} не удалась: {e}")
            time.sleep(2)
    
    logger.error("❌ Не удалось скачать файл после всех попыток")
    return False


def upload_to_yandex(max_retries=3):
    """Загрузить файл с повторными попытками"""
    for attempt in range(max_retries):
        try:
            headers = {"Authorization": f"OAuth {YANDEX_TOKEN}"}
            
            # Создаем папку Финансы (если её нет)
            folder_url = "https://cloud-api.yandex.net/v1/disk/resources"
            folder_params = {"path": "/Финансы"}
            requests.put(folder_url, headers=headers, params=folder_params)
            
            # Получаем ссылку для загрузки
            upload_url = "https://cloud-api.yandex.net/v1/disk/resources/upload"
            upload_params = {
                "path": "/Финансы/budget.xlsx",
                "overwrite": "true"
            }
            
            response = requests.get(upload_url, headers=headers, params=upload_params, timeout=30)
            response.raise_for_status()
            
            href = response.json()["href"]
            
            with open(LOCAL_EXCEL_PATH, "rb") as f:
                upload_response = requests.put(href, files={"file": f}, timeout=60)
                upload_response.raise_for_status()
            
            logger.info("✅ Файл загружен на Яндекс.Диск")
            return True
            
        except Exception as e:
            logger.warning(f"Попытка {attempt + 1}/{max_retries} не удалась: {e}")
            time.sleep(2)
    
    logger.error("❌ Не удалось загрузить файл после всех попыток")
    return False


def get_period():
    """Определить период по дню месяца"""
    day = datetime.now().day
    if day <= 9: 
        return "25-9"
    elif day <= 24: 
        return "10-24"
    else: 
        return "25-9"


def get_date():
    """Формат даты: ДД.ММ.ГГ"""
    return datetime.now().strftime("%d.%m.%y")


def clean_text(text):
    """Удалить эмодзи из текста"""
    if not text:
        return text
    parts = text.split(" ", 1)
    # Если первая часть - эмодзи, возвращаем вторую часть
    if len(parts) > 1 and parts[0].startswith(('🛒', '🏠', '🚗', '💳', '🌿', '💊', '🚬', '🐱', '🧹', '🎮', '🔨', '👕', '💇', '📦')):
        return parts[1]
    return text


def find_last_data_row(worksheet):
    """Находит последнюю строку с данными"""
    for row in range(worksheet.max_row, 1, -1):
        if worksheet.cell(row=row, column=1).value:
            return row
    return 1


def add_expense(category, amount, payer, payment_method):
    """Добавить расход"""
    try:
        if not download_from_yandex():
            return "❌ Не удалось скачать файл"
        
        wb = load_workbook(LOCAL_EXCEL_PATH)
        
        # Ищем лист с расходами
        sheet_name = None
        for name in ["Расходы", "расходы", "Лист1", "budget", "Sheet1"]:
            if name in wb.sheetnames:
                sheet_name = name
                break
        
        if not sheet_name:
            sheet_name = wb.sheetnames[0]  # первый доступный лист
            logger.info(f"Лист расходов не найден, используем: {sheet_name}")
        
        ws = wb[sheet_name]
        
        # Очищаем от эмодзи
        category_clean = clean_text(category)
        payer_clean = clean_text(payer)
        method_clean = clean_text(payment_method)
        
        # Находим последнюю строку с данными
        last_row = find_last_data_row(ws)
        new_row = last_row + 1
        
        # Добавляем данные
        ws.cell(row=new_row, column=1, value=get_date())        # A - Дата
        ws.cell(row=new_row, column=2, value=category_clean)    # B - Категория
        ws.cell(row=new_row, column=3, value="")                # C - Подкат
        ws.cell(row=new_row, column=4, value=float(amount))     # D - Сумма
        ws.cell(row=new_row, column=5, value=payer_clean)       # E - Кто
        ws.cell(row=new_row, column=6, value=get_period())      # F - Период
        ws.cell(row=new_row, column=7, value=method_clean)      # G - Способ
        
        # Сохраняем файл
        wb.save(LOCAL_EXCEL_PATH)
        
        if upload_to_yandex():
            return f"✅ Расход записан: {amount:,.0f} ₽, {category_clean}"
        else:
            return "⚠️ Расход записан локально, но не загружен в облако"
            
    except Exception as e:
        logger.error(f"Ошибка добавления расхода: {e}")
        return f"❌ Ошибка: {str(e)}"


def add_income(source, amount, payer):
    """Добавить доход"""
    try:
        if not download_from_yandex():
            return "❌ Не удалось скачать файл"
        
        wb = load_workbook(LOCAL_EXCEL_PATH)
        
        # Ищем лист с доходами
        sheet_name = None
        for name in ["Доходы", "доходы", "Лист1", "budget", "Sheet1"]:
            if name in wb.sheetnames:
                sheet_name = name
                break
        
        if not sheet_name:
            sheet_name = wb.sheetnames[0]  # первый доступный лист
            logger.info(f"Лист доходов не найден, используем: {sheet_name}")
        
        ws = wb[sheet_name]
        
        # Очищаем от эмодзи
        source_clean = clean_text(source)
        
        # Находим последнюю строку с данными
        last_row = find_last_data_row(ws)
        new_row = last_row + 1
        
        # Добавляем данные
        ws.cell(row=new_row, column=1, value=get_date())        # A - Дата
        ws.cell(row=new_row, column=2, value=source_clean)      # B - Источник
        ws.cell(row=new_row, column=3, value=float(amount))     # C - Сумма
        ws.cell(row=new_row, column=4, value=get_period())      # D - Период
        
        # Сохраняем файл
        wb.save(LOCAL_EXCEL_PATH)
        
        if upload_to_yandex():
            return f"✅ Доход записан: {amount:,.0f} ₽, {source_clean}"
        else:
            return "⚠️ Доход записан локально"
            
    except Exception as e:
        logger.error(f"Ошибка добавления дохода: {e}")
        return f"❌ Ошибка: {str(e)}"


def delete_last(sheet_name):
    """
    Удалить последнюю запись из указанного листа
    sheet_name: "Расходы" или "Доходы"
    """
    try:
        if not download_from_yandex():
            return "❌ Не удалось скачать файл"
        
        wb = load_workbook(LOCAL_EXCEL_PATH)
        
        # Находим лист
        target_sheet = None
        for name in [sheet_name, sheet_name.lower(), "Лист1", "budget", "Sheet1"]:
            if name in wb.sheetnames:
                target_sheet = name
                break
        
        if not target_sheet:
            return f"❌ Лист {sheet_name} не найден"
        
        ws = wb[target_sheet]
        
        # Находим последнюю строку с данными (не заголовок)
        last_row = find_last_data_row(ws)
        
        if last_row <= 1:
            return "❌ Нет записей для удаления"
        
        # Сохраняем данные для сообщения
        date = ws.cell(row=last_row, column=1).value
        category = ws.cell(row=last_row, column=2).value
        amount = ws.cell(row=last_row, column=4).value
        
        # 🔧 ИСПРАВЛЕНИЕ БАГА: преобразуем amount в число для форматирования
        try:
            amount_float = float(amount) if amount else 0
        except (ValueError, TypeError):
            amount_float = 0
            logger.warning(f"Не удалось преобразовать сумму в число: {amount}")
        
        # Удаляем строку
        ws.delete_rows(last_row)
        
        # Сохраняем файл
        wb.save(LOCAL_EXCEL_PATH)
        
        if upload_to_yandex():
            if sheet_name == "Расходы":
                return f"✅ Удалён расход: {date} | {category} | {amount_float:,.0f} ₽"
            else:
                return f"✅ Удалён доход: {date} | {category} | {amount_float:,.0f} ₽"
        else:
            return "⚠️ Запись удалена локально"
            
    except Exception as e:
        logger.error(f"Ошибка удаления: {e}")
        return f"❌ Ошибка удаления: {str(e)}"
