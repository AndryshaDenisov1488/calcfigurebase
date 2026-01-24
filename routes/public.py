#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Public HTML routes."""
import json
import logging
from flask import Blueprint, render_template, request

from extensions import db
from models import Event, Category, Athlete, Participant, Club, Coach, CoachAssignment
from season_utils import get_all_seasons_from_events
from services.rank_service import build_rank_groups, build_best_results

logger = logging.getLogger(__name__)

public_bp = Blueprint('public', __name__)

@public_bp.route('/')
def index():
    """Главная страница"""
    events = Event.query.order_by(Event.begin_date.desc()).limit(10).all()
    return render_template('index.html', events=events)

@public_bp.route('/athletes')
def athletes():
    """Страница со списком спортсменов"""
    search = request.args.get('search', '').strip()
    available_ranks = db.session.query(Category.normalized_name).distinct().filter(
        Category.normalized_name.isnot(None),
        ~Category.normalized_name.like('Другой%')
    ).order_by(Category.normalized_name).all()
    available_ranks = [rank[0] for rank in available_ranks]
    return render_template('athletes.html', search=search, available_ranks=available_ranks)

@public_bp.route('/athlete/<int:athlete_id>')
def athlete_detail(athlete_id):
    """Детальная страница спортсмена"""
    athlete = Athlete.query.get_or_404(athlete_id)
    participations = db.session.query(Event, Category, Participant).join(
        Category, Participant.category_id == Category.id
    ).join(
        Event, Category.event_id == Event.id
    ).filter(
        Participant.athlete_id == athlete_id
    ).order_by(Event.begin_date.desc()).all()
    
    # Получаем тренера из последнего участия (или любого, где есть тренер)
    coach_name = None
    coach_id = None
    for event, category, participant in participations:
        if participant.coach:
            coach_name = participant.coach
            # Ищем тренера в базе для создания ссылки
            from services.coach_registry import CoachRegistry
            coach_registry = CoachRegistry()
            coach_obj = coach_registry.get_or_create(participant.coach)
            if coach_obj:
                coach_id = coach_obj.id
            break
    
    return render_template('athlete_detail.html', athlete=athlete, participations=participations, coach=coach_name, coach_id=coach_id)

@public_bp.route('/events')
def events():
    """Страница со списком турниров"""
    sort_by = request.args.get('sort', 'alphabetical')
    rank_filter = request.args.get('rank', '')
    month_filter = request.args.get('month', '')
    query = Event.query
    if rank_filter:
        query = query.join(Category, Event.id == Category.event_id).filter(
            Category.normalized_name == rank_filter
        ).distinct()
    if month_filter:
        try:
            year, month = map(int, month_filter.split('-'))
            query = query.filter(
                db.extract('year', Event.begin_date) == year,
                db.extract('month', Event.begin_date) == month
            )
        except (ValueError, AttributeError):
            pass
    if sort_by == 'alphabetical':
        events_list = query.order_by(Event.name.asc()).all()
    elif sort_by == 'date':
        events_list = query.order_by(Event.begin_date.desc()).all()
    elif sort_by == 'rank':
        events_list = query.join(Category, Event.id == Category.event_id).order_by(
            Category.normalized_name.asc()
        ).distinct().all()
    else:
        events_list = query.order_by(Event.name.asc()).all()
    seasons = get_all_seasons_from_events(events_list)
    all_ranks = db.session.query(Category.normalized_name).distinct().filter(
        Category.normalized_name.isnot(None),
        Category.normalized_name != '',
        ~Category.normalized_name.like('Другой%')
    ).order_by(Category.normalized_name.asc()).all()
    available_ranks = [rank[0] for rank in all_ranks]
    all_events_with_dates = Event.query.filter(Event.begin_date.isnot(None)).all()
    available_months = sorted(set(
        event.begin_date.strftime('%Y-%m')
        for event in all_events_with_dates
        if event.begin_date
    ), reverse=True)
    total_participants = 0
    if month_filter and events_list:
        event_ids = [event.id for event in events_list]
        if event_ids:
            total_participants = db.session.query(Participant.id).join(
                Category, Participant.category_id == Category.id
            ).filter(Category.event_id.in_(event_ids)).count()
    return render_template(
        'events.html',
        events=events_list,
        seasons=seasons,
        current_sort=sort_by,
        current_rank_filter=rank_filter,
        current_month_filter=month_filter,
        available_ranks=available_ranks,
        available_months=available_months,
        total_participants=total_participants
    )

@public_bp.route('/categories')
def categories():
    """Страница с группировкой по разрядам и спортсменам"""
    event_id = request.args.get('event', type=int)
    events_list = Event.query.order_by(Event.begin_date.desc()).all()
    rank_groups = build_rank_groups(event_id=event_id)
    selected_event_obj = next((event for event in events_list if event.id == event_id), None)
    unique_athlete_ids = set()
    for group in rank_groups:
        for athlete in group.get('athletes', []):
            athlete_id = athlete.get('id')
            if athlete_id is not None:
                unique_athlete_ids.add(athlete_id)
    rank_summary = {
        'total_ranks': len(rank_groups),
        'ranks_with_data': sum(1 for group in rank_groups if group['athletes']),
        'total_athletes': len(unique_athlete_ids),
        'total_free_participations': sum(group.get('total_free_participations', 0) for group in rank_groups)
    }
    rank_groups_json = json.dumps(rank_groups, ensure_ascii=False)
    return render_template(
        'categories.html',
        events=events_list,
        selected_event=event_id,
        rank_groups=rank_groups,
        rank_groups_json=rank_groups_json,
        rank_summary=rank_summary,
        selected_event_obj=selected_event_obj
    )

@public_bp.route('/best_results')
def best_results():
    """Страница лучших результатов по разрядам"""
    rank_name = request.args.get('rank', '').strip()
    rank_groups = build_best_results(rank_name=rank_name or None)
    selected_rank_obj = next((rank for rank in rank_groups if rank['display_name'] == rank_name), None)
    rank_summary = {
        'total_ranks': len(rank_groups),
        'total_athletes': sum(len(group.get('athletes', [])) for group in rank_groups)
    }
    rank_groups_json = json.dumps(rank_groups, ensure_ascii=False)
    return render_template(
        'best_results.html',
        rank_groups=rank_groups,
        rank_groups_json=rank_groups_json,
        rank_summary=rank_summary,
        selected_rank=rank_name,
        selected_rank_obj=selected_rank_obj
    )

def get_judge_role_name(role_code, panel_group, order_num):
    """Преобразует код роли судьи в читаемое название"""
    role_code = (role_code or '').upper().strip()
    panel_group = (panel_group or '').upper().strip()
    order_num = order_num if order_num else None
    
    # Определение ролей по номеру судьи (стандарт ISUCalcFS)
    if order_num:
        if order_num == 7:
            return 'Технический контролер'
        elif order_num == 8:
            return 'Технический специалист'
        elif order_num == 9:
            return 'Технический специалист'
        elif order_num == 10:
            return 'Оператор ввода данных'
    
    # Маппинг кодов ролей на названия
    role_mapping = {
        'REF': 'Рефери (Старший судья)',
        'R': 'Рефери (Старший судья)',
        'REFEREE': 'Рефери (Старший судья)',
        'TC': 'Технический контролер',
        'TEC': 'Технический контролер',
        'TECHNICAL_CONTROLLER': 'Технический контролер',
        'TS': 'Технический специалист',
        'TSP': 'Технический специалист',
        'TECHNICAL_SPECIALIST': 'Технический специалист',
        'ATS': 'Технический специалист',  # Помощник тоже специалист
        'ATSP': 'Технический специалист',
        'ASSISTANT_TECHNICAL_SPECIALIST': 'Технический специалист',
        'JDG': 'Судья',
        'J': 'Судья',
        'JUDGE': 'Судья',
        'DO': 'Оператор ввода данных',
        'DATA': 'Оператор ввода данных',
        'DATA_OPERATOR': 'Оператор ввода данных',
        'VRO': 'Оператор видеоповтора',
        'VIDEO': 'Оператор видеоповтора',
        'VROPER': 'Оператор видеоповтора',
        'VIDEO_REPLAY_OPERATOR': 'Оператор видеоповтора',
    }
    
    # Проверяем точное совпадение
    if role_code in role_mapping:
        role_name = role_mapping[role_code]
        # Если это судья и есть номер порядка, добавляем его
        if role_code in ['JDG', 'J', 'JUDGE'] and order_num and order_num not in [7, 8, 9, 10]:
            return f"{role_name} №{order_num}"
        return role_name
    
    # Если код начинается с известных префиксов
    if role_code.startswith('REF') or role_code.startswith('R'):
        return 'Рефери (Старший судья)'
    elif role_code.startswith('TC') or role_code.startswith('TEC'):
        return 'Технический контролер'
    elif role_code.startswith('TS') or role_code.startswith('TSP') or role_code.startswith('ATS') or role_code.startswith('ATSP'):
        return 'Технический специалист'
    elif role_code.startswith('DO') or role_code.startswith('DATA'):
        return 'Оператор ввода данных'
    elif role_code.startswith('VRO') or role_code.startswith('VIDEO'):
        return 'Оператор видеоповтора'
    elif role_code.startswith('JDG') or role_code.startswith('J'):
        if order_num and order_num not in [7, 8, 9, 10]:
            return f"Судья №{order_num}"
        elif order_num in [7, 8, 9, 10]:
            # Уже обработано выше
            pass
        return 'Судья'
    
    # Если нет кода роли, но есть номер порядка
    if not role_code and order_num:
        if order_num == 7:
            return 'Технический контролер'
        elif order_num == 8:
            return 'Технический специалист'
        elif order_num == 9:
            return 'Технический специалист'
        elif order_num == 10:
            return 'Оператор ввода данных'
        else:
            return f"Судья №{order_num}"
    elif not role_code:
        return "Судья"
    
    # Если ничего не подошло, возвращаем код с номером если есть
    if order_num:
        return f"{role_code} (№{order_num})"
    return role_code

@public_bp.route('/event/<int:event_id>')
def event_detail(event_id):
    """Детальная страница турнира"""
    import json
    from models import Judge, JudgePanel, Segment
    
    event = Event.query.get_or_404(event_id)
    categories_list = Category.query.filter_by(event_id=event_id).all()
    
    # Получаем судей для события с их ролями
    judges_data = {}
    segments = Segment.query.join(Category).filter(Category.event_id == event_id).all()
    for segment in segments:
        judge_panels = JudgePanel.query.filter_by(segment_id=segment.id).all()
        for panel in judge_panels:
            judge = Judge.query.get(panel.judge_id)
            if not judge:
                continue
                
            if panel.judge_id not in judges_data:
                judges_data[panel.judge_id] = {
                    'id': judge.id,
                    'name': judge.full_name_xml or f"{judge.last_name} {judge.first_name}",
                    'country': judge.country or '',
                    'qualification': judge.qualification or '',
                    'roles': []  # Список ролей для этого судьи
                }
            
            # Добавляем роль, если её еще нет в списке
            role_name = get_judge_role_name(panel.role_code, panel.panel_group, panel.order_num)
            if role_name not in judges_data[panel.judge_id]['roles']:
                judges_data[panel.judge_id]['roles'].append(role_name)
    
    # Сортируем судей по важности ролей
    def get_role_priority(roles):
        """Возвращает приоритет для сортировки (меньше = важнее)"""
        if not roles:
            return 999
        role_priorities = {
            'Технический контролер': 1,
            'Технический специалист': 2,
            'Оператор ввода данных': 3,
            'Оператор видеоповтора': 4,
            'Рефери (Старший судья)': 5,
        }
        # Ищем самую важную роль
        for role in roles:
            for key, priority in role_priorities.items():
                if key in role:
                    return priority
        # Если это судья (начинается с "Судья" и не специальная роль)
        if any('Судья' in role and 'Технический' not in role and 'Оператор' not in role for role in roles):
            return 6
        # Остальные в конце
        return 7
    
    # Преобразуем в список и сортируем
    judges_list = list(judges_data.values())
    judges_list.sort(key=lambda j: (get_role_priority(j.get('roles', [])), j['name']))
    
    # Формируем данные категорий с участниками
    category_groups = []
    total_participants = 0
    
    for category in categories_list:
        participants = db.session.query(
            Participant, Athlete, Club
        ).join(
            Athlete, Participant.athlete_id == Athlete.id
        ).outerjoin(
            Club, Athlete.club_id == Club.id
        ).filter(
            Participant.category_id == category.id
        ).order_by(
            Participant.total_place.asc().nullslast(),
            Participant.total_points.desc().nullslast()
        ).all()
        
        participants_data = []
        free_participations = 0
        
        for p, a, c in participants:
            total_participants += 1
            if p.pct_ppname == 'БЕСП':
                free_participations += 1
            
            participants_data.append({
                'place': p.total_place,
                'points': p.total_points,
                'free': p.pct_ppname == 'БЕСП',
                'status': p.status or None,
                'athlete': {
                    'id': a.id,
                    'first_name': a.first_name or '',
                    'last_name': a.last_name or '',
                    'patronymic': a.patronymic or '',
                    'full_name': a.full_name or f"{a.last_name} {a.first_name}"
                },
                'club': {
                    'id': c.id,
                    'name': c.name
                } if c else None,
                'coach': p.coach or None
            })
        
        category_groups.append({
            'id': category.id,
            'name': category.name,
            'gender': category.gender,
            'category_type': category.category_type,
            'num_participants': len(participants_data),
            'free_participations': free_participations,
            'participants': participants_data
        })
    
    category_groups_json = json.dumps(category_groups, ensure_ascii=False, default=str)
    
    return render_template(
        'event_detail.html',
        event=event,
        categories=categories_list,
        category_groups=category_groups,
        category_groups_json=category_groups_json,
        total_participants=total_participants,
        judges=judges_list
    )

@public_bp.route('/coaches')
def coaches():
    """Страница со списком тренеров"""
    return render_template('coaches.html')

@public_bp.route('/coach/<int:coach_id>')
def coach_detail(coach_id):
    """Детальная страница тренера"""
    coach = Coach.query.get_or_404(coach_id)
    
    # Получаем текущих спортсменов тренера (группированные по разрядам)
    current_assignments = CoachAssignment.query.filter_by(
        coach_id=coach_id,
        is_current=True
    ).all()
    
    # Группируем спортсменов по разрядам
    athletes_by_rank = {}
    for assignment in current_assignments:
        athlete = assignment.athlete
        # Получаем разряд спортсмена из последнего участия
        last_participation = Participant.query.filter_by(
            athlete_id=athlete.id
        ).join(Category).order_by(
            Participant.id.desc()
        ).first()
        
        rank = 'Не указан'
        if last_participation and last_participation.category:
            rank = last_participation.category.normalized_name or last_participation.category.name or 'Не указан'
        
        if rank not in athletes_by_rank:
            athletes_by_rank[rank] = []
        
        athletes_by_rank[rank].append({
            'athlete': athlete,
            'assignment': assignment,
            'start_date': assignment.start_date
        })
    
    # Получаем историю переходов
    all_assignments = CoachAssignment.query.filter_by(
        coach_id=coach_id
    ).order_by(CoachAssignment.start_date.desc()).all()
    
    # Статистика
    total_athletes = len(current_assignments)
    total_assignments = len(all_assignments)
    
    return render_template(
        'coach_detail.html',
        coach=coach,
        athletes_by_rank=athletes_by_rank,
        all_assignments=all_assignments,
        total_athletes=total_athletes,
        total_assignments=total_assignments
    )

@public_bp.route('/clubs')
def clubs():
    """Страница со списком клубов"""
    clubs_list = Club.query.order_by(Club.name.asc()).all()
    return render_template('clubs.html', clubs=clubs_list)

@public_bp.route('/club/<int:club_id>')
def club_detail(club_id):
    """Страница с детальной информацией о клубе"""
    club = Club.query.get_or_404(club_id)
    athletes_with_participations = db.session.query(
        Athlete, Event, Category, Participant
    ).join(Participant, Athlete.id == Participant.athlete_id).join(
        Category, Participant.category_id == Category.id
    ).join(Event, Category.event_id == Event.id).filter(
        Athlete.club_id == club_id
    ).order_by(Event.begin_date.desc(), Athlete.last_name, Athlete.first_name).all()
    athletes_data = {}
    for athlete, event, category, participant in athletes_with_participations:
        if athlete.id not in athletes_data:
            athletes_data[athlete.id] = {
                'athlete': athlete,
                'participations': []
            }
        athletes_data[athlete.id]['participations'].append({
            'event': event,
            'category': category,
            'participant': participant
        })
    return render_template('club_detail.html', club=club, athletes_data=list(athletes_data.values()))
