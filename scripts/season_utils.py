#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from datetime import datetime, date
from typing import List, Optional

def get_season_from_date(event_date: date) -> str:
    """
    Определяет сезон по дате события.
    Сезон начинается 1 июля и заканчивается 30 июня следующего года.
    Например: 2024-07-01 -> 2024/25, 2025-06-30 -> 2024/25
    """
    if event_date.month >= 7:  # Июль-декабрь
        return f"{event_date.year}/{str(event_date.year + 1)[-2:]}"
    else:  # Январь-июнь
        return f"{event_date.year - 1}/{str(event_date.year)[-2:]}"

def get_all_seasons_from_events(events) -> List[str]:
    """
    Получает все уникальные сезоны из списка событий.
    
    Args:
        events: Список объектов Event или словарей с полем begin_date
        
    Returns:
        List[str]: Отсортированный список сезонов в формате "2023/24"
    """
    seasons = set()
    
    for event in events:
        if hasattr(event, 'begin_date') and event.begin_date:
            # Объект Event из базы данных
            season = get_season_from_date(event.begin_date)
            seasons.add(season)
        elif isinstance(event, dict) and event.get('begin_date'):
            try:
                # Парсим дату из строки
                if isinstance(event['begin_date'], str):
                    # Проверяем формат даты
                    if len(event['begin_date']) == 8 and event['begin_date'].isdigit():
                        # Формат YYYYMMDD
                        event_date = datetime.strptime(event['begin_date'], '%Y%m%d').date()
                    else:
                        # Формат YYYY-MM-DD
                        event_date = datetime.strptime(event['begin_date'], '%Y-%m-%d').date()
                else:
                    event_date = event['begin_date']
                season = get_season_from_date(event_date)
                seasons.add(season)
            except (ValueError, TypeError):
                continue
    
    return sorted(seasons, reverse=True)

def get_current_season() -> str:
    """
    Возвращает текущий сезон.
    """
    return get_season_from_date(date.today())

def get_season_display_name(season: str) -> str:
    """
    Возвращает отображаемое название сезона.
    Например: "2023/24" -> "2023-2024"
    """
    if '/' in season:
        year1, year2 = season.split('/')
        return f"20{year1}-20{year2}"
    return season

def parse_xml_date_to_season(date_str: str) -> str:
    """
    Парсит дату из XML формата (YYYYMMDD) и возвращает сезон.
    """
    if not date_str:
        return None
    try:
        event_date = datetime.strptime(date_str, '%Y%m%d').date()
        return get_season_from_date(event_date)
    except ValueError:
        return None