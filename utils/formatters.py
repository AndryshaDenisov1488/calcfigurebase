#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Formatting helpers for templates and API."""
def format_season(date_obj):
    """Format date into season YYYY/YY."""
    if not date_obj:
        return "Неизвестно"
    if date_obj.month >= 7:
        start_year = date_obj.year
        end_year = date_obj.year + 1
    else:
        start_year = date_obj.year - 1
        end_year = date_obj.year
    return f"{start_year}/{str(end_year)[-2:]}"

def format_month_filter(month_str):
    """Format month YYYY-MM to Russian text."""
    if not month_str:
        return ""
    months_ru = {
        '01': 'Январь', '02': 'Февраль', '03': 'Март', '04': 'Апрель',
        '05': 'Май', '06': 'Июнь', '07': 'Июль', '08': 'Август',
        '09': 'Сентябрь', '10': 'Октябрь', '11': 'Ноябрь', '12': 'Декабрь'
    }
    try:
        year, month = month_str.split('-')
        return f"{months_ru.get(month, month)} {year}"
    except (ValueError, AttributeError):
        return month_str
