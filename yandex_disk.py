def get_statistics(by_categories=False, balance=False, period=None):
    """
    Получение статистики из Excel файла
    """
    try:
        if not download_from_yandex():
            return "❌ Не удалось скачать файл"
        
        wb = load_workbook(LOCAL_EXCEL_PATH, data_only=True)
        
        result = []
        
        # Статистика по расходам
        if by_categories:
            sheet_name = None
            for name in ["Расходы", "расходы", "Лист1", "budget"]:
                if name in wb.sheetnames:
                    sheet_name = name
                    break
            
            if sheet_name:
                ws = wb[sheet_name]
                
                # Собираем суммы по категориям
                categories = {}
                total = 0
                
                for row in range(2, ws.max_row + 1):
                    cat = ws.cell(row=row, column=2).value  # Категория
                    amount = ws.cell(row=row, column=4).value  # Сумма
                    
                    if cat and amount:
                        try:
                            amount = float(amount)
                            categories[cat] = categories.get(cat, 0) + amount
                            total += amount
                        except (ValueError, TypeError):
                            continue
                
                # Сортируем по убыванию
                sorted_cats = sorted(categories.items(), key=lambda x: x[1], reverse=True)
                
                for cat, amt in sorted_cats[:10]:  # Топ-10
                    percent = (amt / total * 100) if total > 0 else 0
                    result.append(f"{cat}: {amt:,.0f} ₽ ({percent:.1f}%)")
                
                result.append(f"\n💰 Всего: {total:,.0f} ₽")
        
        # Баланс
        elif balance:
            income_total = 0
            expense_total = 0
            
            # Считаем доходы
            for name in ["Доходы", "доходы"]:
                if name in wb.sheetnames:
                    ws = wb[name]
                    for row in range(2, ws.max_row + 1):
                        amount = ws.cell(row=row, column=3).value
                        if amount:
                            try:
                                income_total += float(amount)
                            except (ValueError, TypeError):
                                pass
            
            # Считаем расходы
            for name in ["Расходы", "расходы"]:
                if name in wb.sheetnames:
                    ws = wb[name]
                    for row in range(2, ws.max_row + 1):
                        amount = ws.cell(row=row, column=4).value
                        if amount:
                            try:
                                expense_total += float(amount)
                            except (ValueError, TypeError):
                                pass
            
            balance_total = income_total - expense_total
            
            result.append(f"💵 Доходы: {income_total:,.0f} ₽")
            result.append(f"💰 Расходы: {expense_total:,.0f} ₽")
            result.append(f"📊 Баланс: {balance_total:,.0f} ₽")
        
        # Статистика за период
        elif period:
            sheet_name = None
            for name in ["Расходы", "расходы"]:
                if name in wb.sheetnames:
                    sheet_name = name
                    break
            
            if sheet_name:
                ws = wb[sheet_name]
                
                period_map = {
                    "current": "10-24",
                    "previous": "25-9"
                }
                
                target_period = period_map.get(period)
                period_total = 0
                
                for row in range(2, ws.max_row + 1):
                    row_period = ws.cell(row=row, column=6).value  # Период
                    amount = ws.cell(row=row, column=4).value  # Сумма
                    
                    if period == "all" or (target_period and row_period == target_period):
                        if amount:
                            try:
                                period_total += float(amount)
                            except (ValueError, TypeError):
                                pass
                
                if period == "all":
                    result.append(f"📅 Всего за всё время: {period_total:,.0f} ₽")
                else:
                    result.append(f"📅 Расходы за период {target_period}: {period_total:,.0f} ₽")
        
        return "\n".join(result) if result else "❌ Нет данных"
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        return f"❌ Ошибка: {str(e)}"
