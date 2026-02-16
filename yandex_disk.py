"""
МОДУЛЬ РАБОТЫ С ЯНДЕКС.ДИСКОМ
Сохраняет все листы Excel
"""

import requests
import pandas as pd
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
    
    return False


def upload_to_yandex(max_retries=3):
    """Загрузить файл с повторными попытками"""
    for attempt in range(max_retries):
        try:
            headers = {"Authorization": f"OAuth {YANDEX_TOKEN}"}
            
            folder_url = "https://cloud-api.yandex.net/v1/disk/resources"
            folder_params = {"path": "/Финансы"}
            requests.put(folder_url, headers=headers, params=folder_params)
            
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
    
    return False


def get_period():
    day = datetime.now().day
    if day <= 9: return "25-9"
    elif day <= 24: return "10-24"
    else: return "25-9"


def get_date():
    return datetime.now().strftime("%d.%m.%y")


def clean_text(text):
    if not text:
        return text
    parts = text.split(" ", 1)
    return parts[1] if len(parts) > 1 and parts[0].startswith(('🛒', '🏠', '🚗', '💳', '🌿', '💊', '🚬', '🐱', '🧹', '🎮', '🔨', '👕', '💇', '📦')) else text


def add_expense(category, amount, payer, payment_method):
    """Добавить расход - СОХРАНЯЕТ ВСЕ ЛИСТЫ"""
    try:
        if not download_from_yandex():
            return "❌ Не удалось скачать файл"
        
        # Открываем файл с openpyxl (сохраняет все листы)
        from openpyxl import load_workbook
        wb = load_workbook(LOCAL_EXCEL_PATH)
        
        # Определяем лист с расходами
        sheet_name = None
        for name in ["Расходы", "расходы", "Лист1", "budget"]:
            if name in wb.sheetnames:
                sheet_name = name
                break
        
        if not sheet_name:
            sheet_name = wb.sheetnames[0]  # первый доступный лист
        
        ws = wb[sheet_name]
        
        # Очищаем от эмодзи
        category_clean = clean_text(category)
        payer_clean = clean_text(payer)
        method_clean = clean_text(payment_method)
        
        # Находим следующую пустую строку
        next_row = ws.max_row + 1
        
        # Добавляем данные
        ws.cell(row=next_row, column=1, value=get_date())        # Дата
        ws.cell(row=next_row, column=2, value=category_clean)    # Категория
        ws.cell(row=next_row, column=3, value="")                # Подкат
        ws.cell(row=next_row, column=4, value=float(amount))     # Сумма
        ws.cell(row=next_row, column=5, value=payer_clean)       # Кто
        ws.cell(row=next_row, column=6, value=get_period())      # Период
        ws.cell(row=next_row, column=7, value=method_clean)      # Способ
        
        # Сохраняем файл (сохраняются ВСЕ листы)
        wb.save(LOCAL_EXCEL_PATH)
        
        if upload_to_yandex():
            return f"✅ Расход записан: {amount:,.0f} ₽, {category_clean}"
        else:
            return "⚠️ Расход записан локально"
            
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return f"❌ Ошибка: {str(e)}"


def add_income(source, amount, payer):
    """Добавить доход - СОХРАНЯЕТ ВСЕ ЛИСТЫ"""
    try:
        if not download_from_yandex():
            return "❌ Не удалось скачать файл"
        
        # Открываем файл с openpyxl
        from openpyxl import load_workbook
        wb = load_workbook(LOCAL_EXCEL_PATH)
        
        # Определяем лист с доходами
        sheet_name = None
        for name in ["Доходы", "доходы", "Лист1", "budget"]:
            if name in wb.sheetnames:
                sheet_name = name
                break
        
        if not sheet_name:
            sheet_name = wb.sheetnames[0]  # первый доступный лист
        
        ws = wb[sheet_name]
        
        source_clean = clean_text(source)
        
        # Находим следующую пустую строку
        next_row = ws.max_row + 1
        
        # Добавляем данные
        ws.cell(row=next_row, column=1, value=get_date())        # Дата
        ws.cell(row=next_row, column=2, value=source_clean)      # Источник
        ws.cell(row=next_row, column=3, value=float(amount))     # Сумма
        ws.cell(row=next_row, column=4, value=get_period())      # Период
        
        # Сохраняем файл (сохраняются ВСЕ листы)
        wb.save(LOCAL_EXCEL_PATH)
        
        if upload_to_yandex():
            return f"✅ Доход записан: {amount:,.0f} ₽, {source_clean}"
        else:
            return "⚠️ Доход записан локально"
            
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return f"❌ Ошибка: {str(e)}"


def delete_last(sheet_name):
    return "⚠️ Функция удаления временно отключена"
