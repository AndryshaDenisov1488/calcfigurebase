#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Утилиты для универсального поиска
"""

import re
from sqlalchemy import func
from utils.normalizers import normalize_string, fix_latin_to_cyrillic


def normalize_search_term(search_term):
    """Нормализует поисковый запрос для гибкого поиска
    
    - Убирает лишние пробелы
    - Приводит к нижнему регистру
    - Исправляет латинские символы на кириллические
    - Убирает специальные символы
    """
    if not search_term:
        return ''
    
    # Убираем лишние пробелы
    normalized = ' '.join(search_term.strip().split())
    
    # Исправляем латинские символы на кириллические
    normalized = fix_latin_to_cyrillic(normalized)
    
    # Приводим к нижнему регистру
    normalized = normalized.lower()
    
    return normalized


def create_search_filter(model_field, search_term):
    """Создает фильтр для поиска с учетом нормализации
    
    Args:
        model_field: SQLAlchemy поле модели
        search_term: Поисковый запрос
        
    Returns:
        SQLAlchemy filter condition
    """
    if not search_term:
        return None
    
    normalized_search = normalize_search_term(search_term)
    
    # Для SQLite используем поиск в разных регистрах (более надежно, чем func.lower)
    # Это работает лучше с кириллицей в SQLite
    from sqlalchemy import or_
    search_lower = normalized_search.lower()
    search_upper = normalized_search.upper()
    search_title = normalized_search.capitalize()
    
    return or_(
        model_field.like(f'%{search_lower}%'),
        model_field.like(f'%{search_upper}%'),
        model_field.like(f'%{search_title}%'),
        model_field.like(f'%{normalized_search}%')
    )


def create_multi_field_search_filter(search_term, *fields):
    """Создает фильтр для поиска по нескольким полям
    
    Поддерживает:
    - Поиск по части слова (от 2 символов)
    - Поиск по нескольким словам в любом порядке
    - Поиск без учета регистра
    - Поиск по любому из полей (OR логика)
    - Гибкий поиск: "Иван Петров" найдет "Петров Иван", "Иван Петрович" и т.д.
    
    Args:
        search_term: Поисковый запрос (может быть коротким, от 2 символов)
        *fields: SQLAlchemy поля для поиска
        
    Returns:
        SQLAlchemy OR filter condition или None
    """
    if not search_term or not fields:
        return None
    
    from sqlalchemy import or_, and_
    
    normalized_search = normalize_search_term(search_term)
    
    # Минимальная длина для поиска - 2 символа
    if len(normalized_search) < 2:
        return None
    
    # Разбиваем поисковый запрос на слова
    search_words = [w for w in normalized_search.split() if len(w) >= 2]
    
    if not search_words:
        return None
    
    # Если одно слово - простой поиск по всем полям
    if len(search_words) == 1:
        word = search_words[0]
        filters = []
        for field in fields:
            if field is not None:
                # Для SQLite используем поиск в разных регистрах (более надежно, чем func.lower)
                # Это работает лучше с кириллицей в SQLite
                word_lower = word.lower()
                word_upper = word.upper()
                word_title = word.capitalize()
                
                # Поиск в нижнем регистре
                filters.append(field.like(f'%{word_lower}%'))
                # Поиск в верхнем регистре
                filters.append(field.like(f'%{word_upper}%'))
                # Поиск с заглавной буквы
                filters.append(field.like(f'%{word_title}%'))
                # Поиск в исходном регистре (на случай, если пользователь ввел с заглавной)
                filters.append(field.like(f'%{word}%'))
        return or_(*filters) if filters else None
    
    # Если несколько слов - максимально гибкий поиск
    # Стратегия 1: все слова в одном поле (в любом порядке)
    # Например: "Иван Петров" найдет "Иван Петров", "Петров Иван" в любом поле
    field_filters = []
    for field in fields:
        if field is not None:
            # Поле должно содержать все слова (AND между словами)
            # Для каждого слова создаем фильтры в разных регистрах
            word_combinations = []
            for word in search_words:
                word_lower = word.lower()
                word_upper = word.upper()
                word_title = word.capitalize()
                # Создаем OR для всех вариантов регистра одного слова
                word_variants = [
                    field.like(f'%{word_lower}%'),
                    field.like(f'%{word_upper}%'),
                    field.like(f'%{word_title}%'),
                    field.like(f'%{word}%')
                ]
                word_combinations.append(or_(*word_variants))
            # Все слова должны быть найдены (AND между словами)
            if word_combinations:
                field_filters.append(and_(*word_combinations))
    
    # Стратегия 2: слова могут быть распределены по разным полям
    # Например: "Иван" в имени + "Петров" в фамилии
    # Каждое слово должно быть найдено хотя бы в одном поле (OR для каждого слова)
    # Но все слова должны быть найдены (AND между словами)
    word_or_filters = []
    for word in search_words:
        word_field_filters = []
        for field in fields:
            if field is not None:
                # Для каждого слова создаем фильтры в разных регистрах
                word_lower = word.lower()
                word_upper = word.upper()
                word_title = word.capitalize()
                word_field_filters.extend([
                    field.like(f'%{word_lower}%'),
                    field.like(f'%{word_upper}%'),
                    field.like(f'%{word_title}%'),
                    field.like(f'%{word}%')
                ])
        if word_field_filters:
            word_or_filters.append(or_(*word_field_filters))
    
    # Объединяем обе стратегии: либо все слова в одном поле, либо распределены
    all_filters = field_filters
    if word_or_filters:
        all_filters.append(and_(*word_or_filters))
    
    return or_(*all_filters) if all_filters else None


def normalize_for_client_side_search(text):
    """Нормализует текст для клиентского поиска (JavaScript)
    
    Используется для нормализации данных перед поиском на клиенте
    """
    if not text:
        return ''
    
    # Убираем лишние пробелы и приводим к нижнему регистру
    normalized = ' '.join(str(text).strip().split()).lower()
    
    # Убираем все не-буквенные символы для более гибкого поиска
    # Но оставляем пробелы
    normalized = re.sub(r'[^\w\s]', '', normalized, flags=re.UNICODE)
    
    return normalized
