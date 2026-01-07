#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Функции для сохранения данных в базу данных
ВАЖНО: Эта логика должна быть сохранена полностью!
"""

import json
import logging
from utils.parsing import parse_date, parse_time, parse_datetime
from utils.category_normalization import normalize_category_name
from models import db, Event, Category, Segment, Club, Athlete, Participant, Performance
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, OperationalError

logger = logging.getLogger(__name__)

def save_to_database(parser):
    """Сохраняет данные из парсера в базу данных
    
    ВАЖНО: Эта функция содержит критическую логику парсинга и сохранения.
    Не изменяйте логику без крайней необходимости!
    """
    
    # Сохраняем событие (проверяем на существование)
    event_data = parser.events[0] if parser.events else {}
    event_begin_date = parse_date(event_data.get('begin_date'))
    event_name = event_data.get('name')
    
    # Проверяем на дублирование по названию + дате (основная проверка)
    existing_event = Event.query.filter_by(
        name=event_name,
        begin_date=event_begin_date
    ).first()
    
    if existing_event:
        raise ValueError(f"Турнир '{event_name}' с датой {event_begin_date.strftime('%d.%m.%Y') if event_begin_date else 'неизвестной'} уже существует в системе")
    
    # Создаем новый турнир (external_id больше не используется для поиска существующих)
    event = None
    if not event:
        event = Event(
            external_id=event_data.get('external_id'),
            name=event_data.get('name'),
            long_name=event_data.get('long_name'),
            place=event_data.get('place'),
            begin_date=parse_date(event_data.get('begin_date')),
            end_date=parse_date(event_data.get('end_date')),
            venue=event_data.get('venue'),
            language=event_data.get('language'),
            event_type=event_data.get('type'),
            competition_type=event_data.get('competition_type'),
            status=event_data.get('status'),
            calculation_time=parse_datetime(event_data.get('calculation_time'))
        )
        db.session.add(event)
        db.session.flush()  # Получаем ID события
    
    # Сохраняем клубы (проверяем на существование)
    club_mapping = {}
    for club_data in parser.clubs:
        # Сначала проверяем по external_id, потом по имени
        club = Club.query.filter_by(external_id=club_data.get('external_id')).first()
        
        if not club:
            # Если не найден по external_id, проверяем по имени
            club = Club.query.filter_by(name=club_data.get('name')).first()
        
        if not club:
            club = Club(
                external_id=club_data.get('external_id'),
                name=club_data.get('name'),
                short_name=club_data.get('short_name'),
                country=club_data.get('country'),
                city=club_data.get('city')
            )
            db.session.add(club)
            db.session.flush()
        
        club_mapping[club_data['id']] = club.id
    
    # Сохраняем категории
    category_mapping = {}
    for category_data in parser.categories:
        # Нормализуем название категории
        normalized_name = category_data.get('normalized_name')
        if not normalized_name:
            normalized_name = normalize_category_name(
                category_data.get('name'), 
                category_data.get('gender')
            )
        
        category = Category(
            external_id=category_data.get('external_id'),
            event_id=event.id,
            name=category_data.get('name'),
            tv_name=category_data.get('short_name'),
            normalized_name=normalized_name,
            num_entries=int(category_data.get('num_entries', 0)) if category_data.get('num_entries') else None,
            num_participants=int(category_data.get('num_participants', 0)) if category_data.get('num_participants') else None,
            level=category_data.get('level'),
            gender=category_data.get('gender'),
            category_type=category_data.get('type'),
            status=category_data.get('status')
        )
        db.session.add(category)
        db.session.flush()
        category_mapping[category_data['id']] = category.id
    
    # Сохраняем сегменты
    segment_mapping = {}
    for segment_data in parser.segments:
        segment = Segment(
            category_id=category_mapping.get(segment_data.get('category_id')),
            name=segment_data.get('name'),
            tv_name=segment_data.get('short_name'),
            short_name=segment_data.get('short_name'),
            segment_type=segment_data.get('type'),
            factor=float(segment_data.get('factor', 0)) if segment_data.get('factor') else None,
            status=segment_data.get('status')
        )
        db.session.add(segment)
        db.session.flush()
        segment_mapping[segment_data['id']] = segment.id
    
    # Сохраняем спортсменов и участников
    for participant_data in parser.participants:
        person_data = next((p for p in parser.persons if p['id'] == participant_data['person_id']), None)
        if not person_data:
            continue
        
        # Ищем существующего спортсмена по имени + дате рождения + полу (для предотвращения дубликатов)
        first_name = person_data.get('first_name_cyrillic') or person_data.get('first_name')
        last_name = person_data.get('last_name_cyrillic') or person_data.get('last_name')
        birth_date = parse_date(person_data.get('birth_date'))
        gender = person_data.get('gender')
        
        existing_athlete = Athlete.query.filter_by(
            first_name=first_name,
            last_name=last_name,
            birth_date=birth_date,
            gender=gender
        ).first()
        
        if existing_athlete:
            # Обновляем клуб если он отсутствует
            if not existing_athlete.club_id and club_mapping.get(person_data.get('club_id')):
                existing_athlete.club_id = club_mapping.get(person_data.get('club_id'))
            athlete = existing_athlete
        else:
            # Создаем нового спортсмена (без external_id)
            athlete = Athlete(
                first_name=first_name,
                last_name=last_name,
                patronymic=person_data.get('patronymic_cyrillic') or person_data.get('patronymic'),
                full_name_xml=person_data.get('full_name'),  # Полное ФИО из XML
                birth_date=birth_date,
                gender=gender,
                country=person_data.get('nationality'),
                club_id=club_mapping.get(person_data.get('club_id'))
            )
            db.session.add(athlete)
            db.session.flush()
        
        # Создаем участника
        participant = Participant(
            external_id=participant_data.get('id'),
            event_id=event.id,
            category_id=category_mapping.get(participant_data.get('category_id')),
            athlete_id=athlete.id,
            bib_number=int(participant_data.get('bib_number', 0)) if participant_data.get('bib_number') else None,
            total_points=float(participant_data.get('total_points', 0)) if participant_data.get('total_points') else None,
            total_place=int(participant_data.get('rank', 0)) if participant_data.get('rank') else None,
            status=participant_data.get('status'),
            pct_ppname=participant_data.get('pct_ppname')  # Сохраняем поле для отслеживания бесплатных выступлений
        )
        db.session.add(participant)
        db.session.flush()
        
        # Сохраняем выступления
        for performance_data in parser.performances:
            if performance_data.get('participant_id') == participant_data['id']:
                performance = Performance(
                    participant_id=participant.id,
                    segment_id=segment_mapping.get(performance_data.get('segment_id')),
                    index=int(performance_data.get('starting_number', 0)) if performance_data.get('starting_number') else None,
                    status=performance_data.get('status'),
                    qualification=performance_data.get('qualification'),
                    start_time=parse_time(performance_data.get('start_time')),
                    duration=parse_time(performance_data.get('duration')),
                    judge_time=parse_time(performance_data.get('judge_time')),
                    place=int(performance_data.get('rank', 0)) if performance_data.get('rank') else None,
                    points=float(performance_data.get('points', 0)) if performance_data.get('points') else None,
                    total_1=float(performance_data.get('total_1', 0)) if performance_data.get('total_1') else None,
                    result_1=float(performance_data.get('result_1', 0)) if performance_data.get('result_1') else None,
                    total_2=float(performance_data.get('total_2', 0)) if performance_data.get('total_2') else None,
                    result_2=float(performance_data.get('result_2', 0)) if performance_data.get('result_2') else None,
                    judge_scores=json.dumps(performance_data.get('judge_scores', {}))
                )
                db.session.add(performance)
    
    # Коммитим транзакцию с обработкой ошибок
    try:
        db.session.commit()
        logger.info(f"Successfully saved event '{event_name}' to database")
    except IntegrityError as e:
        db.session.rollback()
        logger.error(f"Integrity error while saving event '{event_name}': {str(e)}")
        raise ValueError(f"Ошибка целостности данных при сохранении турнира '{event_name}': {str(e)}")
    except OperationalError as e:
        db.session.rollback()
        logger.error(f"Database operational error while saving event '{event_name}': {str(e)}")
        raise ValueError(f"Ошибка подключения к базе данных при сохранении турнира '{event_name}'. Проверьте подключение к БД.")
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error while saving event '{event_name}': {str(e)}")
        raise ValueError(f"Ошибка базы данных при сохранении турнира '{event_name}': {str(e)}")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Unexpected error while saving event '{event_name}': {str(e)}")
        raise

