#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Утилиты для универсального поиска
"""

import re
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
    
    # Используем ILIKE для поиска без учета регистра
    # Это работает для большинства случаев
    return model_field.ilike(f'%{normalized_search}%')


def create_multi_field_search_filter(search_term, *fields):
    """Создает фильтр для поиска по нескольким полям
    
    Поддерживает:
    - Поиск по части слова
    - Поиск по нескольким словам (AND логика)
    - Поиск без учета регистра
    - Поиск по любому из полей (OR логика)
    
    Args:
        search_term: Поисковый запрос
        *fields: SQLAlchemy поля для поиска
        
    Returns:
        SQLAlchemy OR filter condition или None
    """
    if not search_term or not fields:
        return None
    
    from sqlalchemy import or_, and_
    
    normalized_search = normalize_search_term(search_term)
    
    # Разбиваем поисковый запрос на слова
    search_words = normalized_search.split()
    
    # Если одно слово - простой поиск
    if len(search_words) == 1:
        filters = []
        for field in fields:
            if field is not None:
                filters.append(field.ilike(f'%{normalized_search}%'))
        return or_(*filters) if filters else None
    
    # Если несколько слов - ищем все слова в любом из полей
    # Это более гибкий поиск: "Иван Петров" найдет и "Иван Петров", и "Петров Иван"
    filters = []
    for field in fields:
        if field is not None:
            # Каждое слово должно быть найдено в поле (AND между словами)
            word_filters = [field.ilike(f'%{word}%') for word in search_words]
            if word_filters:
                filters.append(and_(*word_filters))
    
    return or_(*filters) if filters else None


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
