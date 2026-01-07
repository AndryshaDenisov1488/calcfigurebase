#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Основные маршруты приложения
"""

from flask import Blueprint, render_template, request
from models import db, Event, Category, Athlete, Participant, Club
from season_utils import get_all_seasons_from_events
from utils.data_builders import build_rank_groups, build_best_results
import json

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Главная страница"""
    # Пагинация для главной страницы
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    events_pagination = Event.query.order_by(Event.begin_date.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('index.html', 
                         events=events_pagination.items,
                         pagination=events_pagination)

@main_bp.route('/athletes')
def athletes():
    """Страница со списком спортсменов"""
    search = request.args.get('search', '').strip()
    
    # Получаем все доступные разряды для фильтра (исключаем "Другой")
    available_ranks = db.session.query(Category.normalized_name).distinct().filter(
        Category.normalized_name.isnot(None),
        ~Category.normalized_name.like('Другой%')  # Исключаем категории с "Другой"
    ).order_by(Category.normalized_name).all()
    available_ranks = [rank[0] for rank in available_ranks]
    
    return render_template('athletes.html', search=search, available_ranks=available_ranks)

@main_bp.route('/athlete/<int:athlete_id>')
def athlete_detail(athlete_id):
    """Детальная страница спортсмена"""
    athlete = Athlete.query.get_or_404(athlete_id)
    
    # Получаем все участия спортсмена
    participations = db.session.query(Event, Category, Participant).join(
        Category, Participant.category_id == Category.id
    ).join(
        Event, Category.event_id == Event.id
    ).filter(
        Participant.athlete_id == athlete_id
    ).order_by(Event.begin_date.desc()).all()
    
    return render_template('athlete_detail.html', 
                         athlete=athlete, 
                         participations=participations)

@main_bp.route('/events')
def events():
    """Страница со списком турниров"""
    # Получаем параметры сортировки и фильтрации
    sort_by = request.args.get('sort', 'alphabetical')  # alphabetical, date, rank
    rank_filter = request.args.get('rank', '')  # фильтр по разряду
    month_filter = request.args.get('month', '')  # фильтр по месяцу (формат: YYYY-MM)
    
    # Базовый запрос
    query = Event.query
    
    # Применяем фильтр по разряду, если указан
    if rank_filter:
        query = query.join(Category, Event.id == Category.event_id).filter(
            Category.normalized_name == rank_filter
        ).distinct()
    
    # Применяем фильтр по месяцу, если указан
    if month_filter:
        try:
            year, month = map(int, month_filter.split('-'))
            # Фильтруем турниры, которые начинаются в выбранном месяце
            query = query.filter(
                db.extract('year', Event.begin_date) == year,
                db.extract('month', Event.begin_date) == month
            )
        except (ValueError, AttributeError):
            pass  # Если формат неверный, игнорируем фильтр
    
    # Применяем сортировку
    if sort_by == 'alphabetical':
        query = query.order_by(Event.name.asc())
    elif sort_by == 'date':
        query = query.order_by(Event.begin_date.desc())
    elif sort_by == 'rank':
        # Сортируем по разряду (используем вес разряда)
        query = query.join(Category, Event.id == Category.event_id).order_by(
            Category.normalized_name.asc()
        ).distinct()
    else:
        query = query.order_by(Event.name.asc())
    
    # Пагинация
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    events_pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    events = events_pagination.items
    
    seasons = get_all_seasons_from_events(events)
    
    # Получаем список всех доступных разрядов для фильтра
    all_ranks = db.session.query(Category.normalized_name).distinct().filter(
        Category.normalized_name.isnot(None),
        Category.normalized_name != '',
        ~Category.normalized_name.like('Другой%')  # Исключаем категории с "Другой"
    ).order_by(Category.normalized_name.asc()).all()
    
    available_ranks = [rank[0] for rank in all_ranks]
    
    # Получаем список всех доступных месяцев из турниров
    all_events_with_dates = Event.query.filter(Event.begin_date.isnot(None)).all()
    available_months = sorted(set(
        event.begin_date.strftime('%Y-%m') 
        for event in all_events_with_dates 
        if event.begin_date
    ), reverse=True)
    
    # Подсчет общего количества участников для выбранного месяца
    total_participants = 0
    if month_filter and events:
        # Получаем все категории для турниров в выбранном месяце
        event_ids = [event.id for event in events]
        if event_ids:
            # Подсчитываем уникальных участников через таблицу Participant
            total_participants = db.session.query(Participant.id).join(
                Category, Participant.category_id == Category.id
            ).filter(
                Category.event_id.in_(event_ids)
            ).count()
    
    return render_template('events.html', 
                         events=events,
                         pagination=events_pagination,
                         seasons=seasons,
                         current_sort=sort_by,
                         current_rank_filter=rank_filter,
                         current_month_filter=month_filter,
                         available_ranks=available_ranks,
                         available_months=available_months,
                         total_participants=total_participants)

@main_bp.route('/categories')
def categories():
    """Страница с группировкой по разрядам и спортсменам"""
    event_id = request.args.get('event', type=int)
    
    events = Event.query.order_by(Event.begin_date.desc()).all()
    rank_groups = build_rank_groups(event_id=event_id)
    selected_event_obj = next((event for event in events if event.id == event_id), None)
    
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
        events=events,
        selected_event=event_id,
        rank_groups=rank_groups,
        rank_groups_json=rank_groups_json,
        rank_summary=rank_summary,
        selected_event_obj=selected_event_obj
    )

@main_bp.route('/best_results')
def best_results():
    """Страница с лучшими результатами по разрядам"""
    rank_name = request.args.get('rank', type=str)
    
    rank_groups = build_best_results(rank_name=rank_name)
    selected_rank_obj = next((rank for rank in rank_groups if rank['display_name'] == rank_name), None)
    
    rank_groups_json = json.dumps(rank_groups, ensure_ascii=False)
    
    rank_summary = {
        'total_ranks': len(rank_groups),
        'total_athletes': sum(len(group.get('athletes', [])) for group in rank_groups)
    }
    
    return render_template(
        'best_results.html',
        rank_groups=rank_groups,
        rank_groups_json=rank_groups_json,
        rank_summary=rank_summary,
        selected_rank=rank_name,
        selected_rank_obj=selected_rank_obj
    )

@main_bp.route('/event/<int:event_id>')
def event_detail(event_id):
    """Детальная страница турнира"""
    event = Event.query.get_or_404(event_id)
    categories = Category.query.filter_by(event_id=event_id).all()
    
    # Собираем данные по категориям с участниками
    category_groups = []
    total_participants = 0
    
    for category in categories:
        # Получаем участников для категории с информацией о спортсменах
        participants_data = db.session.query(
            Participant, Athlete, Club
        ).join(
            Athlete, Participant.athlete_id == Athlete.id
        ).outerjoin(
            Club, Athlete.club_id == Club.id
        ).filter(
            Participant.category_id == category.id
        ).order_by(
            Participant.total_place.asc().nullslast(),
            Athlete.last_name,
            Athlete.first_name
        ).all()
        
        participants = []
        free_participations = 0
        
        for participant, athlete, club in participants_data:
            is_free = participant.pct_ppname == 'БЕСП'
            
            # Форматируем баллы (в БД они хранятся умноженными на 100)
            points_value = None
            if participant.total_points is not None:
                try:
                    points_value = round(float(participant.total_points) / 100, 2)
                except (TypeError, ValueError):
                    points_value = None
            
            participants.append({
                'id': participant.id,
                'athlete': {
                    'id': athlete.id,
                    'first_name': athlete.first_name,
                    'last_name': athlete.last_name,
                    'patronymic': athlete.patronymic
                },
                'club': {
                    'id': club.id,
                    'name': club.name
                } if club else None,
                'place': participant.total_place,
                'points': points_value,
                'free': is_free
            })
            if is_free:
                free_participations += 1
        
        category_groups.append({
            'id': category.id,
            'name': category.name,
            'gender': category.gender,
            'category_type': category.category_type,
            'num_participants': len(participants),
            'participants': participants,
            'free_participations': free_participations
        })
        
        total_participants += len(participants)
    
    # Сортируем категории по количеству участников (по убыванию)
    category_groups.sort(key=lambda x: x['num_participants'], reverse=True)
    
    # Данные для передачи в шаблон в JSON формате
    category_groups_json = json.dumps(category_groups, ensure_ascii=False)
    
    return render_template('event_detail.html', 
                         event=event, 
                         category_groups=category_groups,
                         category_groups_json=category_groups_json,
                         total_participants=total_participants)

@main_bp.route('/analytics')
def analytics():
    """Страница аналитики"""
    return render_template('analytics.html')

@main_bp.route('/free-participation')
def free_participation():
    """Страница спортсменов с бесплатным участием"""
    return render_template('free_participation.html')

@main_bp.route('/club-free-analysis')
def club_free_analysis():
    """Страница анализа бесплатного участия по школам"""
    return render_template('club_free_analysis.html')

@main_bp.route('/clubs')
def clubs():
    """Страница со списком всех клубов/школ"""
    return render_template('clubs.html')

@main_bp.route('/club/<int:club_id>')
def club_detail(club_id):
    """Страница с детальной информацией о клубе"""
    club = Club.query.get_or_404(club_id)
    
    # Получаем всех спортсменов этого клуба с их участиями
    athletes_with_participations = db.session.query(
        Athlete, Event, Category, Participant
    ).join(Participant, Athlete.id == Participant.athlete_id).join(
        Category, Participant.category_id == Category.id
    ).join(Event, Category.event_id == Event.id).filter(
        Athlete.club_id == club_id
    ).order_by(Event.begin_date.desc(), Athlete.last_name, Athlete.first_name).all()
    
    # Группируем по спортсменам
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
    
    return render_template('club_detail.html', 
                         club=club, 
                         athletes_data=list(athletes_data.values()))

@main_bp.route('/free-participation-analysis')
def free_participation_analysis():
    """Страница анализа бесплатного участия с фильтрацией"""
    return render_template('free_participation_analysis.html')

