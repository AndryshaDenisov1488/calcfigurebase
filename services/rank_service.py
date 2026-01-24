#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rank normalization and analytics helpers."""
import base64

from extensions import db
from models import Athlete, Category, Participant, Event, Club

RANK_DICTIONARY = {
    'мс': {
        'name': 'МС',
        'genders': {'F': 'МС, Женщины', 'M': 'МС, Мужчины'},
        'keywords': ['мс', 'мастер спорта', 'мастер спорта россии']
    },
    'кмс': {
        'name': 'КМС',
        'genders': {'F': 'КМС, Девушки', 'M': 'КМС, Юноши'},
        'keywords': ['кмс', 'кандидат в мастера спорта', 'кандидат в мастера спорта россии', 'кандидат в мастера', 'кандидат мастера спорта', 'кандидат в мастера спорта, юниоры', 'кандидат в мастера спорта, юниорки']
    },
    '1 спортивный': {
        'name': '1 Спортивный',
        'genders': {'F': '1 Спортивный, Девочки', 'M': '1 Спортивный, Мальчики'},
        'keywords': ['1 спортивный', 'первый спортивный', '1 спорт', '1 спортивный разряд', 'первый спортивный разряд']
    },
    '2 спортивный': {
        'name': '2 Спортивный',
        'genders': {'F': '2 Спортивный, Девочки', 'M': '2 Спортивный, Мальчики'},
        'keywords': ['2 спортивный', 'второй спортивный', '2 спорт', '2 спортивный разряд', 'второй спортивный разряд']
    },
    '3 спортивный': {
        'name': '3 Спортивный',
        'genders': {'F': '3 Спортивный, Девочки', 'M': '3 Спортивный, Мальчики'},
        'keywords': ['3 спортивный', 'третий спортивный', '3 спорт', '3 спортивный разряд', 'третий спортивный разряд']
    },
    '1 юношеский': {
        'name': '1 Юношеский',
        'genders': {'F': '1 Юношеский, Девочки', 'M': '1 Юношеский, Мальчики'},
        'keywords': ['1 юношеский', 'первый юношеский', '1 юн']
    },
    '2 юношеский': {
        'name': '2 Юношеский',
        'genders': {'F': '2 Юношеский, Девочки', 'M': '2 Юношеский, Мальчики'},
        'keywords': ['2 юношеский', 'второй юношеский', '2 юн']
    },
    '3 юношеский': {
        'name': '3 Юношеский',
        'genders': {'F': '3 Юношеский, Девочки', 'M': '3 Юношеский, Мальчики'},
        'keywords': ['3 юношеский', 'третий юношеский', '3 юн']
    },
    'юный фигурист': {
        'name': 'Юный Фигурист',
        'genders': {'F': 'Юный Фигурист, Девочки', 'M': 'Юный Фигурист, Мальчики'},
        'keywords': ['юный фигурист', 'юный', 'юф']
    },
    'дебют': {
        'name': 'Дебют',
        'genders': {'F': 'Дебют, Девочки', 'M': 'Дебют, Мальчики'},
        'keywords': ['дебют', 'дебютный']
    },
    'новичок': {
        'name': 'Новичок',
        'genders': {'F': 'Новичок, Девочки', 'M': 'Новичок, Мальчики'},
        'keywords': ['новичок', 'начинающий']
    },
    'пары_1 спортивный': {
        'name': '1 Спортивный, Пары',
        'genders': {'F': '1 Спортивный, Пары', 'M': '1 Спортивный, Пары'},
        'keywords': ['парное катание, 1 спортивный', 'пары, 1 спортивный', 'парное, 1 спортивный', 'парное катание, 1 спортивный разряд']
    },
    'пары_2 спортивный': {
        'name': '2 Спортивный, Пары',
        'genders': {'F': '2 Спортивный, Пары', 'M': '2 Спортивный, Пары'},
        'keywords': ['парное катание, 2 спортивный', 'пары, 2 спортивный', 'парное, 2 спортивный']
    },
    'пары_3 спортивный': {
        'name': '3 Спортивный, Пары',
        'genders': {'F': '3 Спортивный, Пары', 'M': '3 Спортивный, Пары'},
        'keywords': ['парное катание, 3 спортивный', 'пары, 3 спортивный', 'парное, 3 спортивный']
    },
    'пары_кмс': {
        'name': 'КМС, Пары',
        'genders': {'F': 'КМС, Пары', 'M': 'КМС, Пары'},
        'keywords': ['парное катание, кандидат в мастера спорта', 'пары, кандидат в мастера спорта', 'парное, кандидат в мастера спорта', 'парное катание, кмс', 'пары, кмс', 'парное катание, кандидат в мастера спорта']
    },
    'пары_мс': {
        'name': 'МС, Пары',
        'genders': {'F': 'МС, Пары', 'M': 'МС, Пары'},
        'keywords': ['парное катание, мастер спорта', 'пары, мастер спорта', 'парное, мастер спорта', 'парное катание, мс', 'пары, мс']
    },
    'танцы_1 спортивный': {
        'name': '1 Спортивный, Танцы',
        'genders': {'F': '1 Спортивный, Танцы', 'M': '1 Спортивный, Танцы'},
        'keywords': ['танцы на льду, 1 спортивный', 'танцы, 1 спортивный', 'ледяные танцы, 1 спортивный', 'танцы на льду, 1 спортивный разряд']
    },
    'танцы_2 спортивный': {
        'name': '2 Спортивный, Танцы',
        'genders': {'F': '2 Спортивный, Танцы', 'M': '2 Спортивный, Танцы'},
        'keywords': ['танцы на льду, 2 спортивный', 'танцы, 2 спортивный', 'ледяные танцы, 2 спортивный']
    },
    'танцы_3 спортивный': {
        'name': '3 Спортивный, Танцы',
        'genders': {'F': '3 Спортивный, Танцы', 'M': '3 Спортивный, Танцы'},
        'keywords': ['танцы на льду, 3 спортивный', 'танцы, 3 спортивный', 'ледяные танцы, 3 спортивный']
    },
    'танцы_кмс': {
        'name': 'КМС, Танцы',
        'genders': {'F': 'КМС, Танцы', 'M': 'КМС, Танцы'},
        'keywords': ['танцы на льду, кандидат в мастера спорта', 'танцы, кандидат в мастера спорта', 'ледяные танцы, кандидат в мастера спорта', 'танцы на льду, кмс', 'танцы, кмс', 'танцы на льду, кандидат в мастера спорта']
    },
    'танцы_мс': {
        'name': 'МС, Танцы',
        'genders': {'F': 'МС, Танцы', 'M': 'МС, Танцы'},
        'keywords': ['танцы на льду, мастер спорта', 'танцы, мастер спорта', 'ледяные танцы, мастер спорта', 'танцы на льду, мс', 'танцы, мс']
    }
}

GENDER_LABELS = {'F': 'Женский', 'M': 'Мужской', 'X': 'Смешанный', 'U': 'Не указан'}

def analyze_categories_from_xml(parser):
    """Анализирует категории из XML и возвращает список для ручной нормализации."""
    categories_analysis = []
    for category in parser.categories:
        category_name = category.get('name', '')
        gender = category.get('gender', '')
        normalized = normalize_category_name(category_name, gender)
        categories_analysis.append({
            'original_name': category_name,
            'gender': gender,
            'normalized': normalized,
            'needs_manual': True
        })
    return categories_analysis

def normalize_category_name(category_name, gender=None):
    """Нормализует название категории для группировки по разрядам с учетом пола."""
    if not category_name:
        return "Неизвестно"
    
    # Импортируем функцию замены латинских букв на русские
    from utils.normalizers import fix_latin_to_cyrillic
    
    # Сначала заменяем латинские буквы на русские (o->о, e->е, c->с, p->р, a->а и т.д.)
    category_name = fix_latin_to_cyrillic(category_name)
    
    name_lower = category_name.lower()
    name_lower = name_lower.replace('девочки', 'девочки')
    name_lower = name_lower.replace('спортивный', 'спортивный')

    for rank_data in RANK_DICTIONARY.values():
        for keyword in rank_data['keywords']:
            if keyword in name_lower:
                if gender and gender.upper() in rank_data['genders']:
                    return rank_data['genders'][gender.upper()]
                return rank_data['name']

    gender_suffix = ""
    if gender:
        if gender.upper() == 'F':
            gender_suffix = ", Девочки"
        elif gender.upper() == 'M':
            gender_suffix = ", Мальчики"
    return f"Другой{gender_suffix}"

def get_rank_weight(rank_name):
    """Возвращает вес разряда для ранжирования (меньше = лучше)."""
    base_weights = {
        'МС': 1, 'КМС': 2, '1 Спортивный': 3, '2 Спортивный': 4, '3 Спортивный': 5,
        '1 Юношеский': 6, '2 Юношеский': 7, '3 Юношеский': 8, 'Юный Фигурист': 9,
        'Дебют': 10, 'Новичок': 11, 'Другой': 12
    }
    base_rank = rank_name.split(',')[0].strip()
    return base_weights.get(base_rank, 12)

def _create_rank_entry(display_name, gender_code='U', base_name=None):
    normalized_gender = (gender_code or 'U').upper()
    if normalized_gender not in GENDER_LABELS:
        normalized_gender = 'U'
    anchor = base64.urlsafe_b64encode(display_name.encode('utf-8')).decode('ascii').rstrip('=')
    return {
        'display_name': display_name,
        'base_name': base_name or display_name.split(',')[0].strip(),
        'gender': normalized_gender,
        'gender_label': GENDER_LABELS.get(normalized_gender, GENDER_LABELS['U']),
        'weight': get_rank_weight(display_name),
        'anchor': anchor,
        'athletes': [],
        'athlete_count': 0,
        'total_participations': 0,
        'total_free_participations': 0,
        'total_events': 0,
        'best_place': None,
        'max_points': 0,
        'max_free_participations': 0,
        'has_data': False
    }

def get_rank_catalog():
    catalog = {}
    for rank_data in RANK_DICTIONARY.values():
        genders = rank_data.get('genders')
        if genders:
            for gender_code, name in genders.items():
                catalog[name] = _create_rank_entry(name, gender_code, rank_data.get('name'))
        else:
            base_name = rank_data.get('name')
            catalog[base_name] = _create_rank_entry(base_name, 'U', base_name)
    return catalog

def build_rank_groups(event_id=None):
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
        db.func.sum(db.case((Participant.pct_ppname == 'БЕСП', 1), else_=0)).label('free_participations'),
        db.func.max(db.case((Participant.pct_ppname == 'БЕСП', 1), else_=0)).label('has_free_participation')
    ).join(Participant, Athlete.id == Participant.athlete_id).join(
        Category, Participant.category_id == Category.id
    ).join(Event, Category.event_id == Event.id)
    if event_id:
        participants_query = participants_query.filter(Event.id == event_id)
    participants_query = participants_query.group_by(
        Athlete.id, Athlete.first_name, Athlete.last_name, Athlete.full_name_xml,
        Category.name, Category.gender, Category.normalized_name
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
                best_points_value = round(float(row.best_points), 2)
            except (TypeError, ValueError):
                best_points_value = 0
        # Используем property full_name из модели для правильного отображения без дублирования
        athlete_obj = Athlete.query.get(row.athlete_id)
        athlete_name = athlete_obj.full_name if athlete_obj else (row.full_name_xml or f"{row.last_name or ''} {row.first_name or ''}".strip())
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
    for rank_entry in rank_catalog.values():
        rank_entry['athletes'].sort(
            key=lambda athlete: (
                athlete['best_place'] if athlete['best_place'] is not None else 999,
                -athlete['best_points']
            )
        )
        rank_entry['max_points'] = round(rank_entry['max_points'], 2) if rank_entry['max_points'] else 0
    rank_groups = sorted(rank_catalog.values(), key=lambda item: (item['weight'], item['display_name'].lower()))
    return rank_groups

def build_best_results(rank_name=None):
    rank_catalog = get_rank_catalog()
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
    ).join(Participant, Athlete.id == Participant.athlete_id).join(
        Category, Participant.category_id == Category.id
    ).join(
        Event, Category.event_id == Event.id
    ).outerjoin(
        Club, Athlete.club_id == Club.id
    ).filter(Category.normalized_name.isnot(None), Participant.total_place.isnot(None))
    if rank_name:
        best_results_query = best_results_query.filter(Category.normalized_name == rank_name)
    results = best_results_query.all()
    athlete_ids = {row.athlete_id for row in results}
    participations_counts = {}
    if athlete_ids:
        counts = db.session.query(
            Participant.athlete_id,
            db.func.count(Participant.id).label('cnt')
        ).filter(
            Participant.athlete_id.in_(athlete_ids)
        ).group_by(Participant.athlete_id).all()
        participations_counts = {row.athlete_id: row.cnt for row in counts}
    rank_athletes = {}
    for row in results:
        rank_name_val = row.rank_name or normalize_category_name('', row.category_gender)
        gender_code = (row.category_gender or 'U').upper()
        if rank_name_val not in rank_catalog:
            rank_catalog[rank_name_val] = _create_rank_entry(rank_name_val, gender_code, rank_name_val.split(',')[0].strip())
        key = (rank_name_val, row.athlete_id)
        points_value = 0
        if row.points is not None:
            try:
                points_float = float(row.points)
                points_value = round(points_float, 2)
            except (TypeError, ValueError):
                points_value = 0
        # Используем property full_name из модели для правильного отображения без дублирования
        athlete_obj = Athlete.query.get(row.athlete_id)
        athlete_name = athlete_obj.full_name if athlete_obj else (row.full_name_xml or f"{row.last_name or ''} {row.first_name or ''}".strip())
        event_date_iso = None
        event_date_display = 'Дата не указана'
        if row.event_date:
            event_date_iso = row.event_date.isoformat()
            event_date_display = row.event_date.strftime('%d.%m.%Y')
        athlete_result = {
            'id': row.athlete_id,
            'name': athlete_name,
            'best_place': row.place,
            'best_points': points_value,
            'event_id': row.event_id,
            'event_name': row.event_name,
            'event_date_iso': event_date_iso,
            'event_date_display': event_date_display,
            'event_place': row.event_place,
            'club_id': row.club_id,
            'club_name': row.club_name or 'Не указан',
            'participations_count': participations_counts.get(row.athlete_id, 0)
        }
        if key not in rank_athletes or athlete_result['best_points'] > rank_athletes[key]['best_points']:
            rank_athletes[key] = athlete_result
    for (rank_name_val, _), athlete_result in rank_athletes.items():
        rank_entry = rank_catalog[rank_name_val]
        rank_entry['athletes'].append(athlete_result)
        rank_entry['athlete_count'] += 1
        rank_entry['has_data'] = True
    for rank_entry in rank_catalog.values():
        rank_entry['athletes'].sort(key=lambda athlete: (-athlete['best_points'], athlete['best_place'] or 999))
    rank_groups = sorted(
        [r for r in rank_catalog.values() if r['has_data']],
        key=lambda item: (item['weight'], item['display_name'].lower())
    )
    return rank_groups
