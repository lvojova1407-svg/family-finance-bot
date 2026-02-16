"""
МОДУЛЬ РАБОТЫ С ЯНДЕКС.ДИСКОМ
Скачивание, загрузка, запись в Excel
"""

import requests
from openpyxl import load_workbook
from datetime import datetime
import logging
from config import YANDEX_TOKEN, PUBLIC_KEY, LOCAL_EXCEL_PATH

logger = logging.getLogger(__name__)


def download_from_yandex():
    """Скачать Excel файл с Яндекс.Диска"""
    try:
        # Получаем прямую ссылку на скачивание
        api_url = "https://cloud-api.yandex.net/v1/disk/public/resources/download"
        params = {"public_key": PUBLIC_KEY}
        response = requests.get(api_url, params=params, timeout=30)
        response.raise_for_status()
        
        download_url = response.json()["href"]
        
        # Скачиваем файл
        response = requests.get(download_url, timeout=60)
        response.raise_for_status()
        
        with open(LOCAL_EXCEL_PATH, "wb") as f:
            f.write(response.content)
        
        logger.info("✅ Файл скачан с Яндекс.Диска")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка скачивания: {e}")
        return False


def upload_to_yandex():
    """Загрузить обновленный файл на Яндекс.Диск"""
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
        
        # Загружаем файл
        with open(LOCAL_EXCEL_PATH, "rb") as f:
            upload_response = requests.put(href, files={"file": f}, timeout=60)
            upload_response.raise_for_status()
        
        logger.info("✅ Файл загружен на Яндекс.Диск")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки: {e}")
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
    parts = text.split(" ", 1)
    return parts[1] if len(parts) > 1 else text


def add_expense(category, amount, payer, payment_method):
    """Добавить расход в Excel"""
    try:
        if not download_from_yandex():
            return "❌ Не удалось скачать файл с Яндекс.Диска"
        
        wb = load_workbook(LOCAL_EXCEL_PATH)
        
        if "Расходы" not in wb.sheetnames:
            ws = wb.create_sheet("Расходы")
            ws.append(["Дата", "Категория", "Подкат", "Сумма", "Кто", "Период", "Способ"])
        else:
            ws = wb["Расходы"]
        
        # Очищаем от эмодзи
        category_clean = clean_text(category)
        payer_clean = clean_text(payer)
        method_clean = clean_text(payment_method)
        
        # Добавляем строку
        ws.append([
            get_date(),
            category_clean,
            "",
            float(amount),
            payer_clean,
            get_period(),
            method_clean
        ])
        
        wb.save(LOCAL_EXCEL_PATH)
        
        if upload_to_yandex():
            return f"✅ Расход записан: {amount:,.0f} ₽, {category_clean}"
        else:
            return "⚠️ Расход записан локально, но не загружен в облако"
            
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return f"❌ Ошибка: {str(e)}"


def add_income(source, amount, payer):
    """Добавить доход в Excel"""
    try:
        if not download_from_yandex():
            return "❌ Не удалось скачать файл"
        
        wb = load_workbook(LOCAL_EXCEL_PATH)
        
        if "Доходы" not in wb.sheetnames:
            ws = wb.create_sheet("Доходы")
            ws.append(["Дата", "Источник", "Сумма", "Период"])
        else:
            ws = wb["Доходы"]
        
        source_clean = clean_text(source)
        
        ws.append([
            get_date(),
            source_clean,
            float(amount),
            get_period()
        ])
        
        wb.save(LOCAL_EXCEL_PATH)
        
        if upload_to_yandex():
            return f"✅ Доход записан: {amount:,.0f} ₽, {source_clean}"
        else:
            return "⚠️ Доход записан локально"
            
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return f"❌ Ошибка: {str(e)}"


def delete_last(sheet_name):
    """Удалить последнюю запись"""
    try:
        if not download_from_yandex():
            return "❌ Не удалось скачать файл"
        
        wb = load_workbook(LOCAL_EXCEL_PATH)
        
        if sheet_name not in wb.sheetnames:
            return f"❌ Лист {sheet_name} не найден"
        
        ws = wb[sheet_name]
        
        if ws.max_row > 1:
            ws.delete_rows(ws.max_row)
            wb.save(LOCAL_EXCEL_PATH)
            
            if upload_to_yandex():
                return f"✅ Последняя запись на листе {sheet_name} удалена"
            else:
                return "⚠️ Запись удалена локально"
        else:
            return "❌ Нет записей для удаления"
            
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return f"❌ Ошибка: {str(e)}"
