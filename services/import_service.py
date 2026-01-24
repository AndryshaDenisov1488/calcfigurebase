#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""XML import service."""
import json
import logging

from extensions import db
from models import Event, Category, Segment, Club, Athlete, Participant, Performance, Element, ComponentScore, Judge, JudgePanel, Coach, CoachAssignment
from services.club_registry import ClubRegistry
from services.athlete_registry import AthleteRegistry
from services.coach_registry import CoachRegistry
from services.rank_service import normalize_category_name
from utils.date_parsing import parse_date, parse_time, parse_datetime
from utils.normalizers import remove_duplication

logger = logging.getLogger(__name__)

def _parse_score(raw_value):
    if raw_value is None or raw_value == '':
        return None
    try:
        return int(raw_value) / 100
    except (ValueError, TypeError):
        return None

def save_to_database(parser):
    """Сохраняет данные из парсера в базу данных."""
    event_data = parser.events[0] if parser.events else {}
    event_begin_date = parse_date(event_data.get('begin_date'))
    event_name = event_data.get('name')

    existing_event = Event.query.filter_by(
        name=event_name,
        begin_date=event_begin_date
    ).first()
    if existing_event:
        raise ValueError(
            f"Турнир '{event_name}' с датой {event_begin_date.strftime('%d.%m.%Y') if event_begin_date else 'неизвестной'} уже существует в системе"
        )

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
    db.session.flush()

    club_mapping = {}
    club_registry = ClubRegistry()
    for club_data in parser.clubs:
        club = club_registry.register(club_data)
        if club:
            db.session.flush()
            club_mapping[club_data['id']] = club.id
    
    # После регистрации всех клубов автоматически объединяем дубликаты
    merged_count = club_registry.merge_all_duplicates()
    if merged_count > 0:
        db.session.commit()
        logger.info(f"Автоматически объединено {merged_count} дубликатов клубов при импорте")

    # Инициализируем реестр тренеров
    coach_registry = CoachRegistry()

    category_mapping = {}
    for category_data in parser.categories:
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

    segment_mapping = {}
    for segment_data in parser.segments:
        segment = Segment(
            category_id=category_mapping.get(segment_data.get('category_id')),
            name=segment_data.get('name'),
            tv_name=segment_data.get('tv_name'),
            short_name=segment_data.get('short_name'),
            segment_type=segment_data.get('type'),
            factor=float(segment_data.get('factor', 0)) if segment_data.get('factor') else None,
            status=segment_data.get('status')
        )
        db.session.add(segment)
        db.session.flush()
        segment_mapping[segment_data['id']] = segment.id

    judge_mapping = {}
    for judge_data in parser.judges:
        judge = Judge.query.filter_by(
            first_name=judge_data.get('first_name'),
            last_name=judge_data.get('last_name'),
            full_name_xml=judge_data.get('full_name_xml')
        ).first()
        if not judge:
            judge = Judge(
                first_name=judge_data.get('first_name') or None,
                last_name=judge_data.get('last_name') or None,
                full_name_xml=judge_data.get('full_name_xml') or None,
                short_name=judge_data.get('short_name') or None,
                gender=judge_data.get('gender') or None,
                country=judge_data.get('country') or None,
                city=judge_data.get('city') or None,
                qualification=judge_data.get('qualification') or None,
            )
            db.session.add(judge)
            db.session.flush()
        judge_mapping[judge_data.get('id')] = judge.id

    for panel in parser.judge_panels:
        segment_id = segment_mapping.get(panel.get('segment_id'))
        category_id = category_mapping.get(panel.get('category_id'))
        judge_id = judge_mapping.get(panel.get('judge_id'))
        if not segment_id or not judge_id:
            continue
        existing_panel = JudgePanel.query.filter_by(segment_id=segment_id, judge_id=judge_id).first()
        if existing_panel:
            continue
        db.session.add(JudgePanel(
            segment_id=segment_id,
            category_id=category_id,
            judge_id=judge_id,
            role_code=panel.get('role_code'),
            panel_group=panel.get('panel_group'),
            order_num=panel.get('order_num'),
        ))

    athlete_registry = AthleteRegistry()
    category_gender_map = {
        c['id']: c.get('gender') for c in parser.categories
    }
    for participant_data in parser.participants:
        person_data = next((p for p in parser.persons if p['id'] == participant_data['person_id']), None)
        if not person_data:
            continue

        gender = person_data.get('gender')
        if person_data.get('type') == 'PER':
            gender = category_gender_map.get(participant_data.get('category_id')) or gender

        club_id = club_mapping.get(person_data.get('club_id')) or club_mapping.get(participant_data.get('club_id'))
        # Очищаем имена от дублирования перед сохранением
        first_name_raw = person_data.get('first_name_cyrillic') or person_data.get('first_name')
        last_name_raw = person_data.get('last_name_cyrillic') or person_data.get('last_name')
        patronymic_raw = person_data.get('patronymic_cyrillic') or person_data.get('patronymic')
        
        # Приоритет для full_name_xml: PCT_PLNAME (имя для протоколов) > PCT_CNAME (полное имя)
        full_name_xml = person_data.get('full_name') or person_data.get('full_name_xml')
        
        athlete_payload = {
            'external_id': person_data.get('external_id'),
            'first_name': remove_duplication(first_name_raw) if first_name_raw else None,
            'last_name': remove_duplication(last_name_raw) if last_name_raw else None,
            'patronymic': remove_duplication(patronymic_raw) if patronymic_raw else None,
            'full_name_xml': full_name_xml,  # PCT_PLNAME (приоритет) или PCT_CNAME - имя без дублирования
            'birth_date': parse_date(person_data.get('birth_date')),
            'gender': gender,
            'country': person_data.get('nationality'),
            'club_id': club_id,
        }
        athlete = athlete_registry.get_or_create(athlete_payload)
        db.session.flush()

        category_id = category_mapping.get(participant_data.get('category_id'))
        participant = Participant.query.filter_by(
            event_id=event.id,
            category_id=category_id,
            athlete_id=athlete.id
        ).first()
        if not participant:
            participant = Participant(
                external_id=participant_data.get('id'),
                event_id=event.id,
                category_id=category_id,
                athlete_id=athlete.id,
                bib_number=int(participant_data.get('bib_number', 0)) if participant_data.get('bib_number') else None,
                total_points=_parse_score(participant_data.get('total_points')),
                total_place=int(participant_data.get('rank', 0)) if participant_data.get('rank') else None,
                status=participant_data.get('status'),
                status_segment1=participant_data.get('status_segment1'),
                status_segment2=participant_data.get('status_segment2'),
                status_segment3=participant_data.get('status_segment3'),
                status_segment4=participant_data.get('status_segment4'),
                status_segment5=participant_data.get('status_segment5'),
                status_segment6=participant_data.get('status_segment6'),
                pct_ppname=participant_data.get('pct_ppname'),
                coach=person_data.get('coach')
            )
            db.session.add(participant)
            db.session.flush()
        else:
            participant.bib_number = participant.bib_number or (int(participant_data.get('bib_number', 0)) if participant_data.get('bib_number') else None)
            participant.total_points = participant.total_points or _parse_score(participant_data.get('total_points'))
            participant.total_place = participant.total_place or (int(participant_data.get('rank', 0)) if participant_data.get('rank') else None)
            participant.status = participant.status or participant_data.get('status')
            participant.status_segment1 = participant.status_segment1 or participant_data.get('status_segment1')
            participant.status_segment2 = participant.status_segment2 or participant_data.get('status_segment2')
            participant.status_segment3 = participant.status_segment3 or participant_data.get('status_segment3')
            participant.status_segment4 = participant.status_segment4 or participant_data.get('status_segment4')
            participant.status_segment5 = participant.status_segment5 or participant_data.get('status_segment5')
            participant.status_segment6 = participant.status_segment6 or participant_data.get('status_segment6')
            participant.pct_ppname = participant.pct_ppname or participant_data.get('pct_ppname')
            # Обновляем тренера если он изменился
            new_coach_name = person_data.get('coach')
            if new_coach_name and new_coach_name != participant.coach:
                participant.coach = new_coach_name
        
        # Обрабатываем тренера и отслеживаем переходы
        coach_name = person_data.get('coach')
        if coach_name and coach_name.strip():
            coach = coach_registry.get_or_create(coach_name)
            if coach:
                db.session.flush()
                
                # Получаем дату события для отслеживания переходов
                event_date = event.begin_date or event.end_date
                if event_date:
                    # Проверяем, есть ли уже назначение для этого спортсмена с этим тренером на эту дату
                    existing_assignment = CoachAssignment.query.filter_by(
                        athlete_id=athlete.id,
                        coach_id=coach.id,
                        event_id=event.id
                    ).first()
                    
                    if not existing_assignment:
                        # Проверяем, есть ли текущий тренер у спортсмена
                        current_assignment = CoachAssignment.query.filter_by(
                            athlete_id=athlete.id,
                            is_current=True
                        ).first()
                        
                        if current_assignment:
                            # Если текущий тренер отличается от нового - это переход
                            if current_assignment.coach_id != coach.id:
                                # Закрываем предыдущее назначение
                                current_assignment.end_date = event_date
                                current_assignment.is_current = False
                                
                                # Создаем новое назначение
                                new_assignment = CoachAssignment(
                                    coach_id=coach.id,
                                    athlete_id=athlete.id,
                                    participant_id=participant.id,
                                    event_id=event.id,
                                    start_date=event_date,
                                    is_current=True
                                )
                                db.session.add(new_assignment)
                                logger.info(
                                    f"Переход спортсмена {athlete.id} от тренера {current_assignment.coach_id} "
                                    f"к тренеру {coach.id} на дату {event_date}"
                                )
                        else:
                            # Первое назначение тренера
                            new_assignment = CoachAssignment(
                                coach_id=coach.id,
                                athlete_id=athlete.id,
                                participant_id=participant.id,
                                event_id=event.id,
                                start_date=event_date,
                                is_current=True
                            )
                            db.session.add(new_assignment)

        for performance_data in parser.performances:
            if performance_data.get('participant_id') == participant_data['id']:
                segment_id = segment_mapping.get(performance_data.get('segment_id'))
                performance = Performance.query.filter_by(
                    participant_id=participant.id,
                    segment_id=segment_id
                ).first()
                is_new_performance = False
                if not performance:
                    performance = Performance(
                        participant_id=participant.id,
                        segment_id=segment_id,
                        index=int(performance_data.get('starting_number', 0)) if performance_data.get('starting_number') else None,
                        status=performance_data.get('status'),
                        qualification=performance_data.get('qualification'),
                        start_time=parse_time(performance_data.get('start_time')),
                        duration=parse_time(performance_data.get('duration')),
                        judge_time=parse_time(performance_data.get('judge_time')),
                        place=int(performance_data.get('rank', 0)) if performance_data.get('rank') else None,
                        points=_parse_score(performance_data.get('points')),
                        total_1=_parse_score(performance_data.get('total_1')),
                        result_1=_parse_score(performance_data.get('result_1')),
                        total_2=_parse_score(performance_data.get('total_2')),
                        result_2=_parse_score(performance_data.get('result_2')),
                        tes_total=performance_data.get('tes_sum') or performance_data.get('tes_result'),
                        pcs_total=performance_data.get('pcs_sum') or performance_data.get('pcs_result'),
                        deductions=performance_data.get('deductions'),
                        bonus=performance_data.get('bonus'),
                        judge_scores=json.dumps({
                            'elements': performance_data.get('elements', []),
                            'components': performance_data.get('components', []),
                            'meta': {
                                'start_group': performance_data.get('start_group'),
                                'performance_index': performance_data.get('performance_index'),
                                'locked': performance_data.get('locked'),
                                'tes_sum': performance_data.get('tes_sum'),
                                'tes_result': performance_data.get('tes_result'),
                                'pcs_sum': performance_data.get('pcs_sum'),
                                'pcs_result': performance_data.get('pcs_result'),
                                'tech_target': performance_data.get('tech_target'),
                                'points_needed_1': performance_data.get('points_needed_1'),
                                'points_needed_2': performance_data.get('points_needed_2'),
                                'points_needed_3': performance_data.get('points_needed_3')
                            }
                        })
                    )
                    db.session.add(performance)
                    db.session.flush()  # Получаем performance.id перед созданием элементов
                    is_new_performance = True
                else:
                    performance.status = performance.status or performance_data.get('status')
                    performance.qualification = performance.qualification or performance_data.get('qualification')
                    performance.place = performance.place or (int(performance_data.get('rank', 0)) if performance_data.get('rank') else None)
                    performance.points = performance.points or _parse_score(performance_data.get('points'))

                if not is_new_performance:
                    continue

                for elem in performance_data.get('elements', []):
                    judge_scores = elem.get('judge_scores') or {}
                    if elem.get('planned_norm'):
                        judge_scores['planned_norm'] = elem.get('planned_norm')
                    if elem.get('confirmed') is not None:
                        judge_scores['confirmed'] = elem.get('confirmed')
                    if elem.get('time_code') is not None:
                        judge_scores['time_code'] = elem.get('time_code')
                    element = Element(
                        performance_id=performance.id,
                        order_num=elem.get('order_num'),
                        planned_code=elem.get('planned_code'),
                        executed_code=elem.get('executed_code'),
                        info_code=elem.get('info_code'),
                        base_value=int(elem['base_value']) if elem.get('base_value') else None,
                        goe_result=int(elem['goe_result']) if elem.get('goe_result') else None,
                        penalty=int(elem['penalty']) if elem.get('penalty') else None,
                        result=int(elem['result']) if elem.get('result') else None,
                        judge_scores=judge_scores,
                    )
                    db.session.add(element)

                for comp in performance_data.get('components', []):
                    component = ComponentScore(
                        performance_id=performance.id,
                        component_type=comp.get('component_type'),
                        factor=comp.get('factor'),
                        judge_scores=comp.get('judge_scores'),
                        penalty=int(comp['penalty']) if comp.get('penalty') else None,
                        result=int(comp['result']) if comp.get('result') else None,
                    )
                    db.session.add(component)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
