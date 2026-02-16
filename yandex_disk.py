"""
МОДУЛЬ РАБОТЫ С ЯНДЕКС.ДИСКОМ
Стабильная версия с обработкой всех ошибок
"""

import requests
import pandas as pd
from datetime import datetime
import logging
import time
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
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"Попытка {attempt + 1}/{max_retries} не удалась: {e}")
            time.sleep(2)
        except Exception as e:
            logger.error(f"Неожиданная ошибка: {e}")
            time.sleep(2)
    
    logger.error("❌ Не удалось скачать файл после всех попыток")
    return False


def upload_to_yandex(max_retries=3):
    """Загрузить файл с повторными попытками"""
    for attempt in range(max_retries):
        try:
            headers = {"Authorization": f"OAuth {YANDEX_TOKEN}"}
            
            # Создаем папку если нужно
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
    
    logger.error("❌ Не удалось загрузить файл")
    return False


def get_period():
    """Определить период по дню месяца"""
    day = datetime.now().day
    if day <= 9: return "25-9"
    elif day <= 24: return "10-24"
    else: return "25-9"


def get_date():
    """Формат даты: ДД.ММ.ГГ"""
    return datetime.now().strftime("%d.%m.%y")


def clean_text(text):
    """Удалить эмодзи из текста"""
    if not text:
        return text
    # Оставляем только текст после пробела если есть эмодзи
    parts = text.split(" ", 1)
    return parts[1] if len(parts) > 1 and parts[0].startswith(('🛒', '🏠', '🚗', '💳', '🌿', '💊', '🚬', '🐱', '🧹', '🎮', '🔨', '👕', '💇', '📦')) else text


def add_expense(category, amount, payer, payment_method):
    """Добавить расход - стабильная версия"""
    try:
        # Скачиваем файл
        if not download_from_yandex():
            return "❌ Не удалось скачать файл с Яндекс.Диска"
        
        # Пытаемся прочитать файл разными способами
        try:
            # Способ 1: Читаем все листы
            excel_file = pd.ExcelFile(LOCAL_EXCEL_PATH)
            sheet_names = excel_file.sheet_names
            logger.info(f"Доступные листы: {sheet_names}")
        except Exception as e:
            logger.error(f"Не удалось прочитать файл: {e}")
            return f"❌ Файл поврежден: {e}"
        
        # Ищем лист с расходами
        target_sheet = None
        for name in ["Расходы", "расходы", "Лист1", "budget", "Sheet1"]:
            if name in sheet_names:
                target_sheet = name
                break
        
        if not target_sheet:
            return f"❌ Не найден лист с расходами. Доступны: {sheet_names}"
        
        # Читаем данные
        try:
            df = pd.read_excel(LOCAL_EXCEL_PATH, sheet_name=target_sheet)
            logger.info(f"Прочитано {len(df)} строк из листа {target_sheet}")
        except Exception as e:
            logger.error(f"Ошибка чтения данных: {e}")
            return f"❌ Ошибка чтения данных: {e}"
        
        # Очищаем данные
        category_clean = clean_text(category)
        payer_clean = clean_text(payer)
        method_clean = clean_text(payment_method)
        
        # Создаем новую строку
        new_row = {
            'Дата': get_date(),
            'Категория': category_clean,
            'Подкат': '',
            'Сумма': float(amount),
            'Кто': payer_clean,
            'Период': get_period(),
            'Способ': method_clean
        }
        
        # Добавляем строку
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        
        # Сохраняем
        try:
            with pd.ExcelWriter(LOCAL_EXCEL_PATH, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name=target_sheet, index=False)
            logger.info("✅ Данные сохранены")
        except Exception as e:
            logger.error(f"Ошибка сохранения: {e}")
            return f"❌ Ошибка сохранения: {e}"
        
        # Загружаем обратно
        if upload_to_yandex():
            return f"✅ Расход записан: {amount:,.0f} ₽, {category_clean}"
        else:
            return "⚠️ Расход записан локально, но не загружен в облако"
            
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        return f"❌ Критическая ошибка: {str(e)}"


def add_income(source, amount, payer):
    """Добавить доход - стабильная версия"""
    try:
        if not download_from_yandex():
            return "❌ Не удалось скачать файл"
        
        excel_file = pd.ExcelFile(LOCAL_EXCEL_PATH)
        sheet_names = excel_file.sheet_names
        
        target_sheet = None
        for name in ["Доходы", "доходы", "Лист1", "budget", "Sheet1"]:
            if name in sheet_names:
                target_sheet = name
                break
        
        if not target_sheet:
            return f"❌ Не найден лист с доходами. Доступны: {sheet_names}"
        
        df = pd.read_excel(LOCAL_EXCEL_PATH, sheet_name=target_sheet)
        
        source_clean = clean_text(source)
        
        new_row = {
            'Дата': get_date(),
            'Источник': source_clean,
            'Сумма': float(amount),
            'Период': get_period()
        }
        
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        
        with pd.ExcelWriter(LOCAL_EXCEL_PATH, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name=target_sheet, index=False)
        
        if upload_to_yandex():
            return f"✅ Доход записан: {amount:,.0f} ₽, {source_clean}"
        else:
            return "⚠️ Доход записан локально"
            
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return f"❌ Ошибка: {str(e)}"


def delete_last(sheet_name):
    """Удалить последнюю запись (временно отключено)"""
    return "⚠️ Функция удаления временно отключена для сохранения структуры данных"
