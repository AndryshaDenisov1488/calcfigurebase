#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import contextvars
import re
from contextlib import contextmanager
from datetime import datetime, date
from typing import Iterator, List, Optional, Tuple

from flask import has_request_context, request, session


SEASON_SESSION_KEY = 'active_season'
_SEASON_RE = re.compile(r'^(\d{4})/(\d{2})$')
_forced_season: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    'forced_active_season', default=None
)

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


def normalize_season(season: Optional[str]) -> Optional[str]:
    """Нормализует сезон в канонический формат ``YYYY/YY``."""
    value = (season or '').strip().replace('-', '/')
    if value == 'current':
        return get_current_season()

    # Разрешаем короткую запись из интерфейса/разговора: 26/27.
    short_match = re.fullmatch(r'(\d{2})/(\d{2})', value)
    if short_match:
        value = f"20{short_match.group(1)}/{short_match.group(2)}"

    match = _SEASON_RE.fullmatch(value)
    if not match:
        return None
    start_year = int(match.group(1))
    end_year_short = int(match.group(2))
    if (start_year + 1) % 100 != end_year_short:
        return None
    return f"{start_year}/{end_year_short:02d}"


def get_season_date_range(season: Optional[str]) -> Tuple[date, date]:
    """Возвращает полуинтервал дат сезона: [1 июля, 1 июля следующего года)."""
    normalized = normalize_season(season) or get_current_season()
    start_year = int(normalized.split('/')[0])
    return date(start_year, 7, 1), date(start_year + 1, 7, 1)


@contextmanager
def override_active_season(season: Optional[str]) -> Iterator[Optional[str]]:
    """Задаёт сезон для фонового потока без Flask request context."""
    normalized = normalize_season(season)
    if not normalized:
        yield None
        return
    token = _forced_season.set(normalized)
    try:
        yield normalized
    finally:
        _forced_season.reset(token)


def get_active_season(explicit_season: Optional[str] = None) -> str:
    """Возвращает сезон запроса и запоминает корректный явный выбор в сессии."""
    if explicit_season is None:
        forced = _forced_season.get()
        if forced:
            return forced
    if not has_request_context():
        return normalize_season(explicit_season) or get_current_season()

    requested = explicit_season
    if requested is None:
        requested = request.args.get('season')
    normalized = normalize_season(requested)
    if normalized:
        session[SEASON_SESSION_KEY] = normalized
        return normalized

    stored = normalize_season(session.get(SEASON_SESSION_KEY))
    if stored:
        return stored

    current = get_current_season()
    session[SEASON_SESSION_KEY] = current
    return current


def event_in_season(column, season: Optional[str] = None):
    """SQLAlchemy-условие для даты турнира в активном или указанном сезоне."""
    start_date, end_date = get_season_date_range(season or get_active_season())
    return column >= start_date, column < end_date

def get_season_display_name(season: str) -> str:
    """
    Возвращает отображаемое название сезона.
    Например: "2023/24" -> "2023-2024"
    """
    normalized = normalize_season(season)
    if normalized:
        year1, year2 = normalized.split('/')
        return f"{year1}–{year1[:2]}{year2}"
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
