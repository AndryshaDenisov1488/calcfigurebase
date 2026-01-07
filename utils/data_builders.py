#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Функции для построения данных для отображения
"""

from models import db, Event, Category, Athlete, Participant, Club
from utils.category_normalization import (
    normalize_category_name, get_rank_catalog, _create_rank_entry
)

def build_rank_groups(event_id=None):
    """Формирует данные по разрядам и спортсменам для страницы разрядов"""
    rank_catalog = get_rank_catalog()
    
    participants_query = db.session.query(
        Athlete.id.label('athlete_id'),
        Athlete.first_name,
        Athlete.last_name,
        Athlete.full_name_xml,
        Category.name.label('category_name'),
        Category.gender.label('category_gender'),
        Category.normalized_name.label('normalized_name'),
        db.func.count(Participant.id).label('participations'),
        db.func.count(db.distinct(Participant.event_id)).label('events_count'),
        db.func.min(Participant.total_place).label('best_place'),
        db.func.max(Participant.total_points).label('best_points'),
        db.func.max(Event.begin_date).label('last_event_date'),
        db.func.sum(
            db.case((Participant.pct_ppname == 'БЕСП', 1), else_=0)
        ).label('free_participations'),
        db.func.max(
            db.case((Participant.pct_ppname == 'БЕСП', 1), else_=0)
        ).label('has_free_participation')
    ).join(
        Participant, Athlete.id == Participant.athlete_id
    ).join(
        Category, Participant.category_id == Category.id
    ).join(
        Event, Participant.event_id == Event.id
    )
    
    if event_id:
        participants_query = participants_query.filter(Event.id == event_id)
    
    participants_query = participants_query.group_by(
        Athlete.id,
        Athlete.first_name,
        Athlete.last_name,
        Athlete.full_name_xml,
        Category.name,
        Category.gender,
        Category.normalized_name
    )
    
    results = participants_query.all()
    
    for row in results:
        rank_name = row.normalized_name or normalize_category_name(row.category_name, row.category_gender)
        gender_code = (row.category_gender or 'U').upper()
        
        if rank_name not in rank_catalog:
            rank_catalog[rank_name] = _create_rank_entry(rank_name, gender_code, rank_name.split(',')[0].strip())
        
        rank_entry = rank_catalog[rank_name]
        
        best_points_value = 0
        if row.best_points is not None:
            try:
                best_points_value = round(float(row.best_points) / 100, 2)
            except (TypeError, ValueError):
                best_points_value = 0
        
        athlete_name_parts = [row.last_name or '', row.first_name or '']
        athlete_name = row.full_name_xml or ' '.join(part for part in athlete_name_parts if part).strip()
        
        athlete_data = {
            'id': row.athlete_id,
            'name': athlete_name,
            'participations': int(row.participations or 0),
            'events_count': int(row.events_count or 0),
            'best_place': int(row.best_place) if row.best_place is not None else None,
            'best_points': best_points_value if best_points_value else 0,
            'last_event_date': row.last_event_date.isoformat() if row.last_event_date else None,
            'free_participations': int(row.free_participations or 0),
            'has_free_participation': bool(row.has_free_participation)
        }
        
        rank_entry['athletes'].append(athlete_data)
        rank_entry['athlete_count'] += 1
        rank_entry['total_participations'] += athlete_data['participations']
        rank_entry['total_free_participations'] += athlete_data['free_participations']
        rank_entry['total_events'] += athlete_data['events_count']
        rank_entry['has_data'] = True
        
        if athlete_data['best_place'] is not None:
            if rank_entry['best_place'] is None or athlete_data['best_place'] < rank_entry['best_place']:
                rank_entry['best_place'] = athlete_data['best_place']
        
        if athlete_data['best_points']:
            rank_entry['max_points'] = max(rank_entry['max_points'], athlete_data['best_points'])
    
    # Сортируем спортсменов внутри каждого разряда по умолчанию по лучшему месту и баллам
    for rank_entry in rank_catalog.values():
        rank_entry['athletes'].sort(
            key=lambda athlete: (
                athlete['best_place'] if athlete['best_place'] is not None else 999,
                -athlete['best_points']
            )
        )
        rank_entry['max_points'] = round(rank_entry['max_points'], 2) if rank_entry['max_points'] else 0
    
    # Возвращаем отсортированный список разрядов
    rank_groups = sorted(
        rank_catalog.values(),
        key=lambda item: (item['weight'], item['display_name'].lower())
    )
    
    return rank_groups


def build_best_results(rank_name=None):
    """Формирует данные о лучших результатах спортсменов по разрядам"""
    rank_catalog = get_rank_catalog()
    
    # Запрос для получения всех результатов с информацией о спортсменах, разрядах и турнирах
    best_results_query = db.session.query(
        Athlete.id.label('athlete_id'),
        Athlete.first_name,
        Athlete.last_name,
        Athlete.full_name_xml,
        Category.normalized_name.label('rank_name'),
        Category.gender.label('category_gender'),
        Participant.total_place.label('place'),
        Participant.total_points.label('points'),
        Event.id.label('event_id'),
        Event.name.label('event_name'),
        Event.begin_date.label('event_date'),
        Event.place.label('event_place'),
        Club.id.label('club_id'),
        Club.name.label('club_name')
    ).join(
        Participant, Athlete.id == Participant.athlete_id
    ).join(
        Category, Participant.category_id == Category.id
    ).join(
        Event, Participant.event_id == Event.id
    ).outerjoin(
        Club, Athlete.club_id == Club.id
    ).filter(
        Category.normalized_name.isnot(None),
        Participant.total_place.isnot(None)
    )
    
    if rank_name:
        best_results_query = best_results_query.filter(Category.normalized_name == rank_name)
    
    results = best_results_query.all()
    
    # Группируем результаты по разрядам и спортсменам, находим лучший результат для каждого
    rank_athletes = {}  # {(rank_name, athlete_id): best_result_data}
    
    for row in results:
        rank_name_val = row.rank_name or normalize_category_name('', row.category_gender)
        gender_code = (row.category_gender or 'U').upper()
        
        if rank_name_val not in rank_catalog:
            rank_catalog[rank_name_val] = _create_rank_entry(rank_name_val, gender_code, rank_name_val.split(',')[0].strip())
        
        key = (rank_name_val, row.athlete_id)
        
        # Форматируем баллы
        points_value = 0
        if row.points is not None:
            try:
                points_float = float(row.points)
                # Если значение больше 1000, делим на 100 (например, 12284 -> 122.84)
                if points_float > 1000:
                    points_value = round(points_float / 100, 2)
                else:
                    points_value = round(points_float, 2)
            except (TypeError, ValueError):
                points_value = 0
        
        athlete_name_parts = [row.last_name or '', row.first_name or '']
        athlete_name = row.full_name_xml or ' '.join(part for part in athlete_name_parts if part).strip()
        
        event_date_iso = None
        event_date_display = 'Дата не указана'
        if row.event_date:
            try:
                event_date_iso = row.event_date.isoformat()
                event_date_display = row.event_date.strftime('%d.%m.%Y')
            except (AttributeError, ValueError):
                pass
        
        result_data = {
            'id': row.athlete_id,
            'name': athlete_name,
            'best_place': int(row.place) if row.place is not None else None,
            'best_points': points_value,
            'event_id': row.event_id,
            'event_name': row.event_name or 'Неизвестно',
            'event_date': event_date_iso,
            'event_date_display': event_date_display,
            'event_place': row.event_place or '',
            'club_id': row.club_id,
            'club_name': row.club_name or 'Не указан'
        }
        
        # Сохраняем лучший результат (максимальные баллы)
        if key not in rank_athletes:
            rank_athletes[key] = result_data
        else:
            existing = rank_athletes[key]
            # Приоритет: максимальные баллы
            if result_data['best_points'] > existing['best_points']:
                rank_athletes[key] = result_data
            elif result_data['best_points'] == existing['best_points']:
                # Если баллы одинаковые, берем с лучшим местом (меньшим числом)
                if (result_data['best_place'] is not None and 
                    (existing['best_place'] is None or result_data['best_place'] < existing['best_place'])):
                    rank_athletes[key] = result_data
    
    # Подсчитываем количество участий для каждого спортсмена в каждом разряде
    participations_query = db.session.query(
        Athlete.id.label('athlete_id'),
        Category.normalized_name.label('rank_name'),
        db.func.count(Participant.id).label('participations_count')
    ).join(
        Participant, Athlete.id == Participant.athlete_id
    ).join(
        Category, Participant.category_id == Category.id
    ).filter(
        Category.normalized_name.isnot(None)
    ).group_by(
        Athlete.id,
        Category.normalized_name
    )
    
    if rank_name:
        participations_query = participations_query.filter(Category.normalized_name == rank_name)
    
    participations_results = participations_query.all()
    
    # Создаем словарь для быстрого доступа к количеству участий
    participations_dict = {}
    for row in participations_results:
        rank_name_val = row.rank_name or normalize_category_name('', None)
        key = (rank_name_val, row.athlete_id)
        participations_dict[key] = int(row.participations_count or 0)
    
    # Группируем по разрядам и добавляем количество участий
    for (rank_name_val, athlete_id), athlete_data in rank_athletes.items():
        key = (rank_name_val, athlete_id)
        athlete_data['participations_count'] = participations_dict.get(key, 0)
        
        rank_entry = rank_catalog[rank_name_val]
        rank_entry['athletes'].append(athlete_data)
        rank_entry['athlete_count'] += 1
        rank_entry['has_data'] = True
        
        # Обновляем лучший результат разряда
        if athlete_data['best_place'] is not None:
            if rank_entry['best_place'] is None or athlete_data['best_place'] < rank_entry['best_place']:
                rank_entry['best_place'] = athlete_data['best_place']
        
        if athlete_data['best_points']:
            rank_entry['max_points'] = max(rank_entry['max_points'], athlete_data['best_points'])
    
    # Сортируем спортсменов внутри каждого разряда по максимальным баллам (от большего к меньшему)
    for rank_entry in rank_catalog.values():
        rank_entry['athletes'].sort(
            key=lambda athlete: (
                -athlete['best_points'] if athlete['best_points'] else 0,
                athlete['best_place'] if athlete['best_place'] is not None else 999
            )
        )
        rank_entry['max_points'] = round(rank_entry['max_points'], 2) if rank_entry['max_points'] else 0
    
    # Возвращаем отсортированный список разрядов с данными
    rank_groups = sorted(
        [r for r in rank_catalog.values() if r['has_data']],
        key=lambda item: (item['weight'], item['display_name'].lower())
    )
    
    return rank_groups


def analyze_categories_from_xml(parser):
    """Анализирует категории из XML и возвращает список для ручной нормализации"""
    from utils.category_normalization import normalize_category_name
    
    categories_analysis = []
    
    for category in parser.categories:
        category_name = category.get('name', '')
        gender = category.get('gender', '')
        
        # Пытаемся нормализовать
        normalized = normalize_category_name(category_name, gender)
        
        # ВСЕГДА требуем ручную проверку для обеспечения качества данных
        # Это гарантирует, что в БД не попадут записи с "Другой"
        categories_analysis.append({
            'original_name': category_name,
            'gender': gender,
            'normalized': normalized,
            'needs_manual': True  # Всегда требуем ручную проверку
        })
    
    return categories_analysis

