"""
МОДУЛЬ РАБОТЫ С ЯНДЕКС.ДИСКОМ
Запись в Excel с сохранением структуры дашбордов
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


def find_last_data_row(sheet):
    """Находит последнюю строку с данными в таблице расходов"""
    for row in range(100, 1, -1):  # Ищем с 100 строки вверх
        # Проверяем есть ли данные в колонках A и B
        val_a = sheet.cell(row=row, column=1).value  # Дата
        val_b = sheet.cell(row=row, column=2).value  # Категория
        if val_a and val_b:
            return row
    return 15  # Если ничего не нашли, начинаем с 16 строки


def add_expense(category, amount, payer, payment_method):
    """Добавить расход в Excel на лист 'Расходы'"""
    try:
        if not download_from_yandex():
            return "❌ Не удалось скачать файл с Яндекс.Диска"
        
        wb = load_workbook(LOCAL_EXCEL_PATH)
        
        # ВАЖНО: Используем существующий лист "Расходы", не создаем новый!
        if "Расходы" not in wb.sheetnames:
            return "❌ Лист 'Расходы' не найден в файле!"
        
        ws = wb["Расходы"]
        
        # Очищаем от эмодзи
        category_clean = clean_text(category)
        payer_clean = clean_text(payer)
        method_clean = clean_text(payment_method)
        
        # Находим последнюю строку с данными
        last_row = find_last_data_row(ws)
        new_row = last_row + 1
        
        logger.info(f"Добавляем расход в строку {new_row}")
        
        # Заполняем данные построчно (как в вашем шаблоне)
        ws.cell(row=new_row, column=1, value=get_date())        # A - Дата
        ws.cell(row=new_row, column=2, value=category_clean)    # B - Категория
        ws.cell(row=new_row, column=3, value="")                # C - Подкат (пусто)
        ws.cell(row=new_row, column=4, value=float(amount))     # D - Сумма
        ws.cell(row=new_row, column=5, value=payer_clean)       # E - Кто
        ws.cell(row=new_row, column=6, value=get_period())      # F - Период
        ws.cell(row=new_row, column=7, value=method_clean)      # G - Способ
        
        # Копируем форматирование с предыдущей строки
        for col in range(1, 8):
            source = ws.cell(row=last_row, column=col)
            target = ws.cell(row=new_row, column=col)
            if source.has_style:
                target.font = source.font.copy()
                target.border = source.border.copy()
                target.fill = source.fill.copy()
                target.number_format = source.number_format
                target.alignment = source.alignment.copy()
        
        wb.save(LOCAL_EXCEL_PATH)
        
        if upload_to_yandex():
            return f"✅ Расход записан: {amount:,.0f} ₽, {category_clean}"
        else:
            return "⚠️ Расход записан локально, но не загружен в облако"
            
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return f"❌ Ошибка: {str(e)}"


def add_income(source, amount, payer):
    """Добавить доход в Excel на лист 'Доходы'"""
    try:
        if not download_from_yandex():
            return "❌ Не удалось скачать файл"
        
        wb = load_workbook(LOCAL_EXCEL_PATH)
        
        # ВАЖНО: Используем существующий лист "Доходы"
        if "Доходы" not in wb.sheetnames:
            return "❌ Лист 'Доходы' не найден в файле!"
        
        ws = wb["Доходы"]
        
        source_clean = clean_text(source)
        
        # Находим последнюю строку с данными
        last_row = ws.max_row
        while last_row > 1 and not ws.cell(row=last_row, column=1).value:
            last_row -= 1
        
        new_row = last_row + 1
        
        # Добавляем данные
        ws.cell(row=new_row, column=1, value=get_date())        # Дата
        ws.cell(row=new_row, column=2, value=source_clean)      # Источник
        ws.cell(row=new_row, column=3, value=float(amount))     # Сумма
        ws.cell(row=new_row, column=4, value=get_period())      # Период
        
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
        
        # Находим последнюю строку с данными
        last_row = ws.max_row
        while last_row > 1 and not ws.cell(row=last_row, column=1).value:
            last_row -= 1
        
        if last_row > 1:
            # Сохраняем данные для сообщения
            date = ws.cell(row=last_row, column=1).value
            desc = ws.cell(row=last_row, column=2).value
            amount = ws.cell(row=last_row, column=4).value
            
            # Удаляем строку
            ws.delete_rows(last_row)
            wb.save(LOCAL_EXCEL_PATH)
            
            if upload_to_yandex():
                if sheet_name == "Расходы":
                    return f"✅ Удалён расход: {date} {desc} {amount:,.0f} ₽"
                else:
                    return f"✅ Удалён доход: {date} {desc} {amount:,.0f} ₽"
            else:
                return "⚠️ Запись удалена локально"
        else:
            return "❌ Нет записей для удаления"
            
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return f"❌ Ошибка: {str(e)}"
