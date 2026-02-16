"""
МОДУЛЬ РАБОТЫ С ЯНДЕКС.ДИСКОМ
Стабильная запись в Excel с сохранением структуры дашбордов
Aiogram 3.4 | Python 3.11
"""

import io
import logging
import requests
from datetime import datetime
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
from config import YANDEX_DISK_TOKEN, EXCEL_FILE_PATH

logger = logging.getLogger(__name__)

class ExcelManager:
    def __init__(self, token, file_path):
        """
        Инициализация менеджера Excel
        :param token: Токен Яндекс.Диска
        :param file_path: Путь к файлу на Яндекс.Диске
        """
        self.token = token
        self.file_path = file_path
        self.base_url = "https://cloud-api.yandex.net/v1/disk/resources"
        self.headers = {"Authorization": f"OAuth {self.token}"}
        
        # Настройка листов
        self.sheets_config = {
            'expenses': {
                'name': 'Расходы',
                'columns': ['Дата', 'Категория', 'Сумма', 'Кто платил', 'Способ оплаты', 'Комментарий']
            },
            'income': {
                'name': 'Доходы', 
                'columns': ['Дата', 'Источник', 'Сумма', 'Кто получил', 'Комментарий']
            }
        }
    
    def download_excel(self):
        """
        Скачивает Excel файл с Яндекс.Диска
        :return: Байтовый поток файла или None при ошибке
        """
        try:
            # Получаем ссылку на скачивание
            response = requests.get(
                f"{self.base_url}/download",
                headers=self.headers,
                params={"path": self.file_path}
            )
            response.raise_for_status()
            download_url = response.json()["href"]
            
            # Скачиваем файл
            file_response = requests.get(download_url)
            file_response.raise_for_status()
            
            logger.info(f"Файл успешно скачан: {self.file_path}")
            return io.BytesIO(file_response.content)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка скачивания файла: {e}")
            return None
        except KeyError as e:
            logger.error(f"Неверный формат ответа API: {e}")
            return None
    
    def upload_excel(self, file_bytes):
        """
        Загружает обновленный Excel файл на Яндекс.Диск
        :param file_bytes: Байтовый поток файла
        :return: True при успехе, False при ошибке
        """
        try:
            # Получаем ссылку на загрузку
            response = requests.get(
                f"{self.base_url}/upload",
                headers=self.headers,
                params={"path": self.file_path, "overwrite": "true"}
            )
            response.raise_for_status()
            upload_url = response.json()["href"]
            
            # Загружаем файл
            file_bytes.seek(0)
            upload_response = requests.put(upload_url, files={"file": file_bytes})
            upload_response.raise_for_status()
            
            logger.info(f"Файл успешно загружен: {self.file_path}")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка загрузки файла: {e}")
            return False
    
    def ensure_sheet_structure(self, workbook, sheet_config):
        """
        Проверяет и создает структуру листа если нужно
        :param workbook: Рабочая книга Excel
        :param sheet_config: Конфигурация листа
        :return: Лист Excel
        """
        sheet_name = sheet_config['name']
        
        # Создаем лист если не существует
        if sheet_name not in workbook.sheetnames:
            sheet = workbook.create_sheet(sheet_name)
            # Добавляем заголовки
            for col_idx, header in enumerate(sheet_config['columns'], 1):
                sheet.cell(row=1, column=col_idx, value=header)
                # Делаем заголовки жирными
                sheet.cell(row=1, column=col_idx).font = openpyxl.styles.Font(bold=True)
            logger.info(f"Создан новый лист: {sheet_name}")
        else:
            sheet = workbook[sheet_name]
        
        return sheet
    
    def find_table(self, sheet):
        """
        Ищет умную таблицу на листе
        :param sheet: Лист Excel
        :return: Таблица или None
        """
        for table in sheet.tables.values():
            # Проверяем, что таблица содержит данные
            if table.ref and ":" in table.ref:
                return table
        return None
    
    def add_to_table(self, sheet, table, row_data):
        """
        Добавление строки в умную таблицу Excel
        :param sheet: Лист Excel
        :param table: Умная таблица
        :param row_data: Данные для добавления
        :return: Номер добавленной строки
        """
        # Получаем диапазон таблицы
        min_col, min_row, max_col, max_row = self.get_range_boundaries(table.ref)
        
        # Вставляем строку после последней строки таблицы
        new_row = max_row + 1
        sheet.insert_rows(new_row)
        
        # Обновляем ссылку таблицы
        new_ref = f"{get_column_letter(min_col)}{min_row}:{get_column_letter(max_col)}{new_row}"
        table.ref = new_ref
        
        # Заполняем данные
        for col_idx, value in enumerate(row_data, min_col):
            cell = sheet.cell(row=new_row, column=col_idx, value=value)
            
            # Копируем формат с предыдущей строки если есть
            if max_row >= min_row:
                source_cell = sheet.cell(row=max_row, column=col_idx)
                if source_cell.has_style:
                    cell.font = source_cell.font.copy()
                    cell.border = source_cell.border.copy()
                    cell.fill = source_cell.fill.copy()
                    cell.number_format = source_cell.number_format
                    cell.alignment = source_cell.alignment.copy()
        
        return new_row
    
    def add_to_sheet_safe(self, sheet, row_data):
        """
        Безопасное добавление строки в обычный лист
        :param sheet: Лист Excel
        :param row_data: Данные для добавления
        :return: Номер добавленной строки
        """
        # Находим последнюю заполненную строку
        last_row = sheet.max_row
        if last_row == 1 and all(sheet.cell(row=1, column=c).value is None for c in range(1, len(row_data)+1)):
            last_row = 0
        
        new_row = last_row + 1
        
        # Заполняем данные
        for col_idx, value in enumerate(row_data, 1):
            cell = sheet.cell(row=new_row, column=col_idx, value=value)
            
            # Копируем формат с предыдущей строки если есть
            if last_row > 0:
                source_cell = sheet.cell(row=last_row, column=col_idx)
                if source_cell.has_style:
                    cell.font = source_cell.font.copy()
                    cell.border = source_cell.border.copy()
                    cell.fill = source_cell.fill.copy()
                    cell.number_format = source_cell.number_format
                    cell.alignment = source_cell.alignment.copy()
        
        return new_row
    
    def get_range_boundaries(self, range_str):
        """
        Преобразует строку диапазона в числа
        :param range_str: Строка диапазона (например "A1:C10")
        :return: (min_col, min_row, max_col, max_row)
        """
        import re
        pattern = r'([A-Z]+)(\d+):([A-Z]+)(\d+)'
        match = re.match(pattern, range_str)
        
        if match:
            min_col_letter, min_row_str, max_col_letter, max_row_str = match.groups()
            min_col = self.column_letter_to_number(min_col_letter)
            max_col = self.column_letter_to_number(max_col_letter)
            return min_col, int(min_row_str), max_col, int(max_row_str)
        
        return 1, 1, len(range_str), 1
    
    def column_letter_to_number(self, letters):
        """Преобразует буквы колонки в число"""
        number = 0
        for char in letters.upper():
            number = number * 26 + (ord(char) - ord('A') + 1)
        return number
    
    def add_row(self, sheet_type, row_data):
        """
        Основной метод добавления строки
        :param sheet_type: Тип листа ('expenses' или 'income')
        :param row_data: Список данных для добавления
        :return: (success, message)
        """
        try:
            # Проверяем тип листа
            if sheet_type not in self.sheets_config:
                return False, f"Неизвестный тип листа: {sheet_type}"
            
            sheet_config = self.sheets_config[sheet_type]
            
            # Проверяем количество колонок
            if len(row_data) != len(sheet_config['columns']):
                return False, f"Неверное количество колонок. Ожидалось: {len(sheet_config['columns'])}, получено: {len(row_data)}"
            
            # Скачиваем файл
            file_bytes = self.download_excel()
            if file_bytes is None:
                return False, "Не удалось скачать файл"
            
            # Загружаем рабочую книгу
            wb = load_workbook(file_bytes)
            
            # Проверяем структуру листа
            sheet = self.ensure_sheet_structure(wb, sheet_config)
            
            # Ищем умную таблицу
            table = self.find_table(sheet)
            
            # Добавляем строку
            if table:
                new_row = self.add_to_table(sheet, table, row_data)
                method = "умная таблица"
            else:
                new_row = self.add_to_sheet_safe(sheet, row_data)
                method = "обычный лист"
            
            # Сохраняем файл
            output = io.BytesIO()
            wb.save(output)
            output.seek(0)
            
            # Загружаем обратно
            if self.upload_excel(output):
                logger.info(f"Строка добавлена в {sheet_config['name']} (строка {new_row}, метод: {method})")
                return True, f"✅ Данные добавлены в {sheet_config['name']}"
            else:
                return False, "❌ Не удалось загрузить файл"
            
        except Exception as e:
            logger.error(f"Ошибка в add_row: {e}")
            return False, f"❌ Ошибка: {str(e)}"
    
    def delete_last_row(self, sheet_type):
        """
        Удаление последней строки из листа
        :param sheet_type: Тип листа ('expenses' или 'income')
        :return: (success, message, deleted_data)
        """
        try:
            if sheet_type not in self.sheets_config:
                return False, f"Неизвестный тип листа: {sheet_type}", None
            
            sheet_config = self.sheets_config[sheet_type]
            
            # Скачиваем файл
            file_bytes = self.download_excel()
            if file_bytes is None:
                return False, "Не удалось скачать файл", None
            
            # Загружаем рабочую книгу
            wb = load_workbook(file_bytes)
            
            # Проверяем наличие листа
            if sheet_config['name'] not in wb.sheetnames:
                return False, f"Лист {sheet_config['name']} не найден", None
            
            sheet = wb[sheet_config['name']]
            
            # Находим последнюю строку с данными (не заголовок)
            last_data_row = sheet.max_row
            while last_data_row > 1 and all(sheet.cell(row=last_data_row, column=c).value is None 
                                            for c in range(1, len(sheet_config['columns'])+1)):
                last_data_row -= 1
            
            if last_data_row <= 1:
                return False, "Нет данных для удаления", None
            
            # Сохраняем удаляемые данные
            deleted_data = []
            for col_idx in range(1, len(sheet_config['columns'])+1):
                deleted_data.append(sheet.cell(row=last_data_row, column=col_idx).value)
            
            # Удаляем строку
            sheet.delete_rows(last_data_row)
            
            # Сохраняем файл
            output = io.BytesIO()
            wb.save(output)
            output.seek(0)
            
            # Загружаем обратно
            if self.upload_excel(output):
                logger.info(f"Строка {last_data_row} удалена из {sheet_config['name']}")
                return True, f"✅ Последняя запись удалена из {sheet_config['name']}", deleted_data
            else:
                return False, "❌ Не удалось загрузить файл", None
            
        except Exception as e:
            logger.error(f"Ошибка в delete_last_row: {e}")
            return False, f"❌ Ошибка: {str(e)}", None


# Инициализация менеджера
excel_manager = ExcelManager(YANDEX_DISK_TOKEN, EXCEL_FILE_PATH)


def add_expense(category, amount, payer, payment_method):
    """
    Добавление расхода с сохранением структуры
    """
    try:
        row_data = [
            datetime.now().strftime("%d.%m.%Y"),  # Дата
            category,                              # Категория
            float(amount),                          # Сумма (число)
            payer,                                  # Кто платил
            payment_method,                         # Способ оплаты
            ""                                      # Комментарий (пустой)
        ]
        
        success, message = excel_manager.add_row('expenses', row_data)
        
        if success:
            return f"✅ Расход добавлен:\n{category}: {amount:,.0f} ₽\nПлательщик: {payer}\nОплата: {payment_method}"
        else:
            return message
            
    except Exception as e:
        logger.error(f"Ошибка add_expense: {e}")
        return f"❌ Ошибка: {e}"


def add_income(source, amount, payer):
    """
    Добавление дохода с сохранением структуры
    """
    try:
        row_data = [
            datetime.now().strftime("%d.%m.%Y"),  # Дата
            source,                                 # Источник
            float(amount),                          # Сумма (число)
            payer,                                  # Кто получил
            ""                                      # Комментарий
        ]
        
        success, message = excel_manager.add_row('income', row_data)
        
        if success:
            return f"✅ Доход добавлен:\n{source}: {amount:,.0f} ₽"
        else:
            return message
            
    except Exception as e:
        logger.error(f"Ошибка add_income: {e}")
        return f"❌ Ошибка: {e}"


def delete_last(record_type):
    """
    Удаление последней записи
    :param record_type: "Расходы" или "Доходы"
    """
    try:
        sheet_map = {
            "Расходы": "expenses",
            "Доходы": "income"
        }
        
        if record_type not in sheet_map:
            return f"❌ Неизвестный тип: {record_type}"
        
        sheet_type = sheet_map[record_type]
        success, message, deleted_data = excel_manager.delete_last_row(sheet_type)
        
        if success and deleted_data:
            # Формируем сообщение с информацией об удаленной записи
            if sheet_type == 'expenses':
                return (f"{message}\n"
                       f"📋 Удалено:\n"
                       f"Дата: {deleted_data[0]}\n"
                       f"Категория: {deleted_data[1]}\n"
                       f"Сумма: {deleted_data[2]:,.0f} ₽\n"
                       f"Плательщик: {deleted_data[3]}")
            else:
                return (f"{message}\n"
                       f"📋 Удалено:\n"
                       f"Дата: {deleted_data[0]}\n"
                       f"Источник: {deleted_data[1]}\n"
                       f"Сумма: {deleted_data[2]:,.0f} ₽")
        else:
            return message
            
    except Exception as e:
        logger.error(f"Ошибка delete_last: {e}")
        return f"❌ Ошибка: {e}"
