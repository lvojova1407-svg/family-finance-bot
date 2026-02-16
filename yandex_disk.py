"""
МОДУЛЬ РАБОТЫ С ЯНДЕКС.ДИСКОМ
Используем pandas с фиксированными версиями
"""

import requests
import pandas as pd
import numpy as np  # явно импортируем
from datetime import datetime
import logging
import time
from config import YANDEX_TOKEN, PUBLIC_KEY, LOCAL_EXCEL_PATH

logger = logging.getLogger(__name__)

# Проверяем версии
logger.info(f"Pandas version: {pd.__version__}")
logger.info(f"Numpy version: {np.__version__}")


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
    """Добавить расход"""
    try:
        if not download_from_yandex():
            return "❌ Не удалось скачать файл"
        
        # Пробуем прочитать файл
        try:
            df = pd.read_excel(LOCAL_EXCEL_PATH, sheet_name=0)  # читаем первый лист
            logger.info(f"Прочитано {len(df)} строк")
        except Exception as e:
            logger.error(f"Ошибка чтения: {e}")
            return f"❌ Ошибка чтения файла: {e}"
        
        # Очищаем данные
        category_clean = clean_text(category)
        payer_clean = clean_text(payer)
        method_clean = clean_text(payment_method)
        
        # Создаем новую строку
        new_row = pd.DataFrame({
            'Дата': [get_date()],
            'Категория': [category_clean],
            'Подкат': [''],
            'Сумма': [float(amount)],
            'Кто': [payer_clean],
            'Период': [get_period()],
            'Способ': [method_clean]
        })
        
        # Добавляем строку
        df = pd.concat([df, new_row], ignore_index=True)
        
        # Сохраняем
        df.to_excel(LOCAL_EXCEL_PATH, index=False, engine='openpyxl')
        
        if upload_to_yandex():
            return f"✅ Расход записан: {amount:,.0f} ₽, {category_clean}"
        else:
            return "⚠️ Расход записан локально"
            
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return f"❌ Ошибка: {str(e)}"


def add_income(source, amount, payer):
    """Добавить доход"""
    try:
        if not download_from_yandex():
            return "❌ Не удалось скачать файл"
        
        df = pd.read_excel(LOCAL_EXCEL_PATH, sheet_name=0)
        
        source_clean = clean_text(source)
        
        new_row = pd.DataFrame({
            'Дата': [get_date()],
            'Источник': [source_clean],
            'Сумма': [float(amount)],
            'Период': [get_period()]
        })
        
        df = pd.concat([df, new_row], ignore_index=True)
        df.to_excel(LOCAL_EXCEL_PATH, index=False, engine='openpyxl')
        
        if upload_to_yandex():
            return f"✅ Доход записан: {amount:,.0f} ₽, {source_clean}"
        else:
            return "⚠️ Доход записан локально"
            
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return f"❌ Ошибка: {str(e)}"


def delete_last(sheet_name):
    return "⚠️ Функция удаления временно отключена"
