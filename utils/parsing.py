#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Утилиты для парсинга данных
"""

from datetime import datetime
import json

def parse_date(date_str):
    """Парсит дату из строки формата YYYYMMDD или возвращает объект date"""
    if not date_str:
        return None
    
    # Если это уже объект date, возвращаем его
    if hasattr(date_str, 'year') and hasattr(date_str, 'month') and hasattr(date_str, 'day'):
        return date_str
    
    # Если это строка, парсим её
    if isinstance(date_str, str):
        if len(date_str) != 8:
            return None
        try:
            return datetime.strptime(date_str, '%Y%m%d').date()
        except ValueError:
            return None
    
    return None

def parse_time(time_str):
    """Парсит время из строки формата HH:MM:SS"""
    if not time_str:
        return None
    try:
        return datetime.strptime(time_str, '%H:%M:%S').time()
    except ValueError:
        return None

def parse_datetime(datetime_str):
    """Парсит дату и время из строки"""
    if not datetime_str:
        return None
    try:
        # Пробуем разные форматы
        for fmt in ['%Y%m%d%H%M%S', '%Y-%m-%d %H:%M:%S', '%Y%m%d']:
            try:
                return datetime.strptime(datetime_str, fmt)
            except ValueError:
                continue
        return None
    except ValueError:
        return None

