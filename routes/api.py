#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""API routes."""
import json
import logging
from datetime import datetime
from flask import Blueprint, jsonify, request, Response

from extensions import db
from models import Event, Category, Athlete, Participant, Club, Segment, Performance, Coach, CoachAssignment, Element, ComponentScore
from season_utils import get_season_from_date
from services.rank_service import normalize_category_name, get_rank_weight
from utils.search_utils import normalize_search_term, create_multi_field_search_filter
from utils.normalizers import normalize_string

logger = logging.getLogger(__name__)
api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/athlete/<int:athlete_id>/results-chart')
def api_athlete_results_chart(athlete_id):
    """API для получения данных графика результатов спортсмена"""
    athlete = Athlete.query.get_or_404(athlete_id)
    participations = db.session.query(Event, Category, Participant).join(
        Category, Participant.category_id == Category.id
    ).join(
        Event, Category.event_id == Event.id
    ).filter(
        Participant.athlete_id == athlete_id
    ).order_by(Event.begin_date.asc()).all()
    chart_data = {
        'labels': [],
        'places': [],
        'points': [],
        'tournaments': [],
        'categories': [],
        'seasons': []
    }
    for event, category, participant in participations:
        if event.begin_date:
            date_str = event.begin_date.strftime('%d.%m.%Y')
            chart_data['labels'].append(date_str)
            chart_data['places'].append(participant.total_place or 0)
            chart_data['points'].append(round(participant.total_points, 2) if participant.total_points else 0)
            chart_data['tournaments'].append(event.name)
            chart_data['categories'].append(category.name)
            chart_data['seasons'].append(get_season_from_date(event.begin_date))
    return jsonify(chart_data)

@api_bp.route('/events', methods=['GET'])
def api_events():
    """Возвращает список турниров для интеграций"""
    events = Event.query.order_by(Event.begin_date.desc()).all()
    def serialize_date(value):
        return value.isoformat() if value else None
    events_payload = [
        {
            'id': event.id,
            'name': event.name,
            'begin_date': serialize_date(event.begin_date),
            'end_date': serialize_date(event.end_date),
            'place': event.place,
            'venue': event.venue
        }
        for event in events
    ]
    return jsonify({'total': len(events_payload), 'events': events_payload})

@api_bp.route('/event/<int:event_id>/export')
def export_event_results(event_id):
    """Экспорт результатов турнира в CSV"""
    event = Event.query.get_or_404(event_id)
    results = db.session.query(
        Athlete.first_name,
        Athlete.last_name,
        Athlete.patronymic,
        Club.name.label('club_name'),
        Category.name.label('category_name'),
        Category.gender,
        Category.category_type,
        Participant.total_place,
        Participant.total_points,
        Event.name.label('event_name'),
        Event.begin_date
    ).join(
        Participant, Athlete.id == Participant.athlete_id
    ).join(
        Category, Participant.category_id == Category.id
    ).join(
        Event, Category.event_id == Event.id
    ).outerjoin(
        Club, Athlete.club_id == Club.id
    ).filter(
        Event.id == event_id
    ).order_by(
        Category.name, Participant.total_place
    ).all()
    csv_content = "Фамилия,Имя,Отчество,Клуб,Категория,Пол,Тип,Место,Баллы,Турнир,Дата\n"
    for result in results:
        csv_content += f'"{result.last_name or ""}","{result.first_name or ""}","{result.patronymic or ""}","{result.club_name or ""}","{result.category_name or ""}","{result.gender or ""}","{result.category_type or ""}","{result.total_place or ""}","{round(result.total_points, 2) if result.total_points else ""}","{result.event_name or ""}","{result.begin_date.strftime("%d.%m.%Y") if result.begin_date else ""}"\n'
    safe_event_name = (event.name or 'event').replace(' ', '_')
    date_part = event.begin_date.strftime('%Y%m%d') if event.begin_date else 'unknown'
    response = Response(
        csv_content,
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename=results_{safe_event_name}_{date_part}.csv'
        }
    )
    return response

@api_bp.route('/statistics')
def api_statistics():
    """API для получения статистики
    ВАЖНО: Исключает МС и КМС из подсчета. Считаются только разряды с 1 сп до 3 юношеского.
    """
    from models import Category
    
    # Разряды, которые нужно исключить из отчета (МС и КМС)
    excluded_ranks = {
        'МС, Женщины',
        'МС, Мужчины',
        'МС, Пары',
        'МС, Танцы',
        'КМС, Девушки',
        'КМС, Юноши',
        'КМС, Пары',
        'КМС, Танцы'
    }
    
    # Подсчет спортсменов, которые участвовали в разрядах без МС и КМС
    total_athletes = db.session.query(db.func.count(db.distinct(Participant.athlete_id))).join(
        Category, Participant.category_id == Category.id
    ).filter(
        db.or_(
            Category.normalized_name.is_(None),
            Category.normalized_name.notin_(excluded_ranks)
        )
    ).scalar()
    
    total_events = Event.query.count()
    
    # Подсчет участий без МС и КМС
    total_participations = db.session.query(Participant).join(
        Category, Participant.category_id == Category.id
    ).filter(
        db.or_(
            Category.normalized_name.is_(None),
            Category.normalized_name.notin_(excluded_ranks)
        )
    ).count()
    
    club_stats = db.session.query(
        Club.name,
        db.func.count(Athlete.id).label('athlete_count')
    ).join(Athlete).group_by(Club.id).order_by(
        db.func.count(Athlete.id).desc()
    ).limit(10).all()
    return jsonify({
        'total_athletes': total_athletes,
        'total_events': total_events,
        'total_participations': total_participations,
        'top_clubs': [{'name': name, 'count': count} for name, count in club_stats]
    })

@api_bp.route('/analytics/top-athletes')
def api_top_athletes():
    """API для получения топ спортсменов, сгруппированных по разрядам"""
    try:
        athletes_query = db.session.query(
            Athlete.id,
            Athlete.first_name,
            Athlete.last_name,
            Athlete.full_name_xml,
            Category.name.label('category_name'),
            Category.gender.label('category_gender'),
            Category.normalized_name.label('normalized_name'),
            db.func.count(Participant.id).label('participations'),
            db.func.min(Participant.total_place).label('best_place'),
            db.func.max(Participant.total_points).label('best_points')
        ).select_from(Athlete).join(
            Participant, Athlete.id == Participant.athlete_id
        ).join(Category, Participant.category_id == Category.id).group_by(
            Athlete.id, Category.name, Category.gender, Category.normalized_name
        ).all()

        def get_athlete_name(athlete):
            if athlete['full_name_xml']:
                return athlete['full_name_xml']
            return f"{athlete['last_name']} {athlete['first_name']}"

        ranks_data = {}
        total_participations = {}
        for row in athletes_query:
            rank = row.normalized_name or normalize_category_name(row.category_name, row.category_gender)
            rank_weight = get_rank_weight(rank)
            if rank not in ranks_data:
                ranks_data[rank] = {'name': rank, 'weight': rank_weight, 'athletes': []}
            athlete_data = {
                'id': row.id,
                'name': get_athlete_name({
                    'first_name': row.first_name,
                    'last_name': row.last_name,
                    'full_name_xml': row.full_name_xml
                }),
                'participations': row.participations,
                'best_place': row.best_place,
                'best_points': round(row.best_points, 2) if row.best_points else 0
            }
            ranks_data[rank]['athletes'].append(athlete_data)
            athlete_id = row.id
            if athlete_id not in total_participations:
                total_participations[athlete_id] = 0
            total_participations[athlete_id] += row.participations
        for rank in ranks_data:
            ranks_data[rank]['athletes'].sort(
                key=lambda x: (x['best_place'] or 999, -x['best_points'])
            )
        sorted_ranks = sorted(ranks_data.values(), key=lambda x: x['weight'])
        all_athletes = []
        for row in athletes_query:
            athlete_id = row.id
            rank = row.normalized_name or normalize_category_name(row.category_name, row.category_gender)
            if not any(a['id'] == athlete_id for a in all_athletes):
                all_athletes.append({
                    'id': athlete_id,
                    'name': get_athlete_name({
                        'first_name': row.first_name,
                        'last_name': row.last_name,
                        'full_name_xml': row.full_name_xml
                    }),
                    'participations': total_participations[athlete_id],
                    'rank': rank
                })
        all_athletes.sort(key=lambda x: x['participations'], reverse=True)
        top_participants = all_athletes[:10]
        
        # Формируем список топ спортсменов по участиям с разрядами
        by_participations = []
        for athlete in top_participants:
            # Находим лучшее место для этого спортсмена
            best_place_row = db.session.query(
                db.func.min(Participant.total_place)
            ).filter(
                Participant.athlete_id == athlete['id'],
                Participant.total_place.isnot(None)
            ).scalar()
            
            by_participations.append({
                'id': athlete['id'],
                'name': athlete['name'],
                'participations': athlete['participations'],
                'rank': athlete['rank'],
                'best_place': best_place_row
            })
        
        return jsonify({
            'by_ranks': sorted_ranks,
            'by_participations': by_participations,
            'ranks': sorted_ranks,  # Для обратной совместимости
            'top_participants': top_participants  # Для обратной совместимости
        })
    except Exception as e:
        logger.error(f"Ошибка в api_top_athletes: {e}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/analytics/club-statistics')
def api_club_statistics():
    """API для получения статистики по клубам"""
    club_athlete_stats = db.session.query(
        Club.id,
        Club.name,
        db.func.count(Athlete.id).label('athlete_count')
    ).outerjoin(Athlete, Club.id == Athlete.club_id).group_by(
        Club.id, Club.name
    ).all()
    club_participation_stats = db.session.query(
        Club.id,
        db.func.count(Participant.id).label('participation_count'),
        db.func.min(Participant.total_place).label('best_place')
    ).join(Athlete, Club.id == Athlete.club_id).outerjoin(
        Participant, Athlete.id == Participant.athlete_id
    ).group_by(Club.id).all()
    participation_dict = {c.id: {'count': c.participation_count, 'best': c.best_place} for c in club_participation_stats}
    result = []
    for club in club_athlete_stats:
        participation_data = participation_dict.get(club.id, {'count': 0, 'best': None})
        result.append({
            'id': club.id,
            'name': club.name,
            'athlete_count': club.athlete_count,
            'participation_count': participation_data['count'],
            'best_place': participation_data['best']
        })
    result.sort(key=lambda x: x['athlete_count'], reverse=True)
    return jsonify(result)

@api_bp.route('/analytics/category-statistics')
def api_category_statistics():
    """API для получения статистики по категориям"""
    category_stats = db.session.query(
        Category.name,
        Category.gender,
        Category.category_type,
        Category.normalized_name,
        db.func.count(Participant.id).label('participant_count'),
        db.func.avg(Participant.total_points).label('avg_points')
    ).outerjoin(Participant).group_by(
        Category.name, Category.gender, Category.category_type, Category.normalized_name
    ).order_by(db.func.count(Participant.id).desc()).all()
    rank_stats = {}
    for stat in category_stats:
        rank = stat.normalized_name or normalize_category_name(stat.name, stat.gender)
        gender = stat.gender or 'U'
        if rank not in rank_stats:
            rank_stats[rank] = {
                'name': rank,
                'total_participants': 0,
                'genders': {'F': 0, 'M': 0, 'T': 0, 'U': 0},
                'avg_points': 0,
                'categories': []
            }
        rank_stats[rank]['total_participants'] += stat.participant_count
        rank_stats[rank]['genders'][gender] += stat.participant_count
        rank_stats[rank]['categories'].append({
            'name': stat.name,
            'gender': stat.gender,
            'type': stat.category_type,
            'participant_count': stat.participant_count
        })
    for rank in rank_stats:
        total_points = 0
        total_count = 0
        for stat in category_stats:
            if (stat.normalized_name or normalize_category_name(stat.name)) == rank and stat.avg_points:
                total_points += stat.avg_points * stat.participant_count
                total_count += stat.participant_count
        if total_count > 0:
            rank_stats[rank]['avg_points'] = round(total_points / total_count, 2)
    result = sorted(rank_stats.values(), key=lambda x: x['total_participants'], reverse=True)
    return jsonify(result)

@api_bp.route('/analytics/free-participation')
def api_free_participation():
    """API для получения спортсменов с бесплатным участием"""
    try:
        from services.rank_service import build_rank_groups
        
        # Получаем данные о бесплатных участиях
        free_participants = db.session.query(
            Athlete.id,
            Athlete.first_name,
            Athlete.last_name,
            Athlete.full_name_xml,
            Event.name.label('event_name'),
            Event.begin_date.label('event_date'),
            Category.name.label('category_name'),
            Category.gender.label('category_gender'),
            Category.normalized_name.label('normalized_name'),
            Participant.pct_ppname,
            Participant.total_place,
            Participant.total_points
        ).select_from(Athlete).join(
            Participant, Athlete.id == Participant.athlete_id
        ).join(
            Category, Participant.category_id == Category.id
        ).join(
            Event, Category.event_id == Event.id
        ).filter(
            Participant.pct_ppname == 'БЕСП'
        ).order_by(
            Event.begin_date.desc(), Athlete.last_name, Athlete.first_name
        ).all()

        # Группируем по спортсменам
        athletes_data = {}
        for row in free_participants:
            athlete_id = row.id
            if athlete_id not in athletes_data:
                athlete = Athlete.query.get(athlete_id)
                athletes_data[athlete_id] = {
                    'id': athlete_id,
                    'name': athlete.full_name if athlete else (row.full_name_xml or f"{row.last_name} {row.first_name}"),
                    'free_participations': 0,
                    'participations': 0,
                    'events': [],
                    'ranks': [],
                    'dominant_rank': None
                }
            rank = row.normalized_name or normalize_category_name(row.category_name, row.category_gender)
            athletes_data[athlete_id]['free_participations'] += 1
            athletes_data[athlete_id]['participations'] += 1
            points_display = None
            if row.total_points is not None:
                try:
                    points_value = float(row.total_points)
                    points_display = f"{points_value:.2f}".rstrip('0').rstrip('.')
                except (ValueError, TypeError):
                    points_display = None
            athletes_data[athlete_id]['events'].append({
                'event_name': row.event_name,
                'event_date': row.event_date.strftime('%d.%m.%Y') if row.event_date else 'Дата не указана',
                'category_name': row.category_name,
                'rank': rank,
                'place': row.total_place,
                'points': points_display
            })
            
            # Собираем разряды
            rank_found = False
            for rank_info in athletes_data[athlete_id]['ranks']:
                if rank_info['name'] == rank:
                    rank_info['count'] += 1
                    rank_found = True
                    break
            if not rank_found:
                athletes_data[athlete_id]['ranks'].append({'name': rank, 'count': 1})
        
        # Определяем доминирующий разряд для каждого спортсмена
        for athlete_data in athletes_data.values():
            if athlete_data['ranks']:
                athlete_data['ranks'].sort(key=lambda x: x['count'], reverse=True)
                athlete_data['dominant_rank'] = athlete_data['ranks'][0]['name']
        
        athletes_list = sorted(athletes_data.values(), key=lambda x: x['free_participations'], reverse=True)
        
        # Получаем данные по разрядам (только для спортсменов с бесплатным участием)
        rank_groups_data = build_rank_groups(event_id=None)
        # Фильтруем только разряды с бесплатными участиями
        filtered_rank_groups = []
        for group in rank_groups_data:
            # Оставляем только спортсменов с бесплатным участием
            free_athletes = [a for a in group.get('athletes', []) if a.get('has_free_participation', False)]
            if free_athletes:
                # Добавляем информацию о турнирах для каждого спортсмена из уже загруженных данных
                for athlete in free_athletes:
                    athlete_id = athlete.get('id')
                    if athlete_id and athlete_id in athletes_data:
                        # Добавляем поле events из athletes_data (только бесплатные участия)
                        athlete['events'] = athletes_data[athlete_id].get('events', [])
                        # Добавляем last_event_display для отображения (форматированная дата последнего турнира)
                        if athlete['events']:
                            # События уже отсортированы по дате desc, первое - самое последнее
                            last_event = athlete['events'][0]
                            athlete['last_event_display'] = last_event.get('event_date', '—')
                        else:
                            athlete['last_event_display'] = '—'
                        # Убеждаемся, что events_count соответствует количеству уникальных турниров
                        if athlete['events']:
                            unique_events = set()
                            for event in athlete['events']:
                                unique_events.add(event.get('event_name', ''))
                            athlete['events_count'] = len(unique_events)
                
                group_copy = group.copy()
                group_copy['athletes'] = free_athletes
                group_copy['athlete_count'] = len(free_athletes)
                group_copy['total_free_participations'] = sum(a.get('free_participations', 0) for a in free_athletes)
                filtered_rank_groups.append(group_copy)
        
        # Формируем сводку
        ranks_with_data = [g for g in filtered_rank_groups if g.get('athletes')]
        unique_athlete_ids = set()
        for group in filtered_rank_groups:
            for athlete in group.get('athletes', []):
                if athlete.get('id'):
                    unique_athlete_ids.add(athlete['id'])
        
        rank_summary = {
            'total_ranks': len(filtered_rank_groups),
            'ranks_with_data': len(ranks_with_data),
            'total_athletes': len(unique_athlete_ids),
            'total_free_participations': sum(g.get('total_free_participations', 0) for g in ranks_with_data)
        }
        
        total_athletes = len(athletes_list)
        total_free_participations = sum(a['free_participations'] for a in athletes_list)
        
        return jsonify({
            'athletes': athletes_list,
            'total_athletes': total_athletes,
            'total_free_participations': total_free_participations,
            'rank_groups': filtered_rank_groups,
            'rank_summary': rank_summary
        })
    except Exception as e:
        logger.error(f"Ошибка в api_free_participation: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@api_bp.route('/analytics/club-free-participation')
def api_club_free_participation():
    """API для получения статистики бесплатного участия по школам/клубам"""
    try:
        from sqlalchemy import case
        
        # Получаем статистику по клубам с бесплатным участием
        club_stats = db.session.query(
            Club.id,
            Club.name,
            Club.short_name,
            Club.country,
            Club.city,
            db.func.count(db.distinct(Athlete.id)).label('total_athletes'),
            db.func.count(db.distinct(case((Participant.pct_ppname == 'БЕСП', Athlete.id), else_=None))).label('athletes_with_free_participation'),
            db.func.count(Participant.id).label('total_participations'),
            db.func.count(case((Participant.pct_ppname == 'БЕСП', 1), else_=None)).label('free_participations')
        ).select_from(Club).outerjoin(
            Athlete, Club.id == Athlete.club_id
        ).outerjoin(
            Participant, Athlete.id == Participant.athlete_id
        ).group_by(
            Club.id, Club.name, Club.short_name, Club.country, Club.city
        ).having(
            db.func.count(db.distinct(Athlete.id)) > 0  # Только клубы с спортсменами
        ).order_by(
            db.func.count(db.distinct(Athlete.id)).desc()
        ).all()
        
        result = []
        for stat in club_stats:
            athletes_with_free = stat.athletes_with_free_participation or 0
            athletes_without_free = stat.total_athletes - athletes_with_free
            free_participations = stat.free_participations or 0
            
            club_data = {
                'id': stat.id,
                'name': stat.name,
                'short_name': stat.short_name,
                'country': stat.country,
                'city': stat.city,
                'total_athletes': stat.total_athletes,
                'athletes_with_free_participation': athletes_with_free,
                'total_participations': stat.total_athletes,  # Показываем общее количество спортсменов
                'free_participations': free_participations,
                'athletes_without_free_participation': athletes_without_free,
                'free_participation_percentage': round(athletes_with_free / stat.total_athletes * 100, 1) if stat.total_athletes > 0 else 0
            }
            result.append(club_data)
        
        return jsonify({
            'clubs': result,
            'total_clubs': len(result),
            'total_athletes': sum(c['total_athletes'] for c in result),
            'total_athletes_with_free_participation': sum(c['athletes_with_free_participation'] for c in result),
            'total_free_participations': sum(c['free_participations'] for c in result)
        })
        
    except Exception as e:
        logger.error(f"Ошибка в api_club_free_participation: {e}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/athletes')
def api_athletes():
    """API для получения списка спортсменов с поиском и сортировкой"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    # Ограничиваем per_page разумными значениями
    if per_page not in [10, 20, 50, 100]:
        per_page = 20
    search = request.args.get('search', '').strip()
    rank_filter = request.args.get('rank', '').strip()
    
    # Параметры сортировки
    sort_by = request.args.get('sort_by', 'best_place')
    sort_order = request.args.get('sort_order', 'asc')

    # Универсальный поиск по имени, фамилии, отчеству и полному имени (нечувствительный к регистру)
    # Создаем фильтр ДО построения основного запроса
    search_filter = None
    if search and search.strip():
        normalized = normalize_search_term(search)
        logger.info(f"Поиск: '{search}' -> нормализовано: '{normalized}' (длина: {len(normalized)}, байты: {normalized.encode('utf-8')})")
        # Проверяем, что нормализация не изменила строку неправильно
        if search != normalized:
            logger.info(f"  Исходная строка: '{search}' (байты: {search.encode('utf-8')})")
            logger.info(f"  Нормализованная: '{normalized}' (байты: {normalized.encode('utf-8')})")
        
        search_filter = create_multi_field_search_filter(
            search,
            Athlete.first_name,
            Athlete.last_name,
            Athlete.full_name_xml,
            Athlete.patronymic
        )
        
        if search_filter is not None:
            logger.info(f"Фильтр поиска создан для '{search}'")
            logger.info(f"Тип фильтра: {type(search_filter)}")
            logger.debug(f"Фильтр: {search_filter}")
            
            # Для отладки - проверяем, есть ли вообще спортсмены с таким именем
            try:
                # Логируем сгенерированный SQL запрос
                query = db.session.query(Athlete).filter(search_filter)
                try:
                    compiled = query.statement.compile(compile_kwargs={'literal_binds': True})
                    logger.info(f"SQL запрос для поиска '{search}': {str(compiled)}")
                except Exception as compile_error:
                    logger.warning(f"Не удалось скомпилировать SQL запрос: {compile_error}")
                    logger.info(f"SQL запрос (без literal_binds): {str(query.statement)}")
                
                # Простой запрос без JOIN'ов для проверки
                simple_count = query.count()
                logger.info(f"Проверка: найдено {simple_count} спортсменов с '{search}' БЕЗ JOIN'ов")
                
                # Прямой SQL запрос для проверки (без LOWER/UPPER, так как в SQLite они могут работать некорректно с кириллицей)
                try:
                    from sqlalchemy import text
                    # Пробуем прямой SQL запрос с разными вариантами регистра
                    search_lower = normalized.lower()
                    search_upper = normalized.upper()
                    search_title = normalized.capitalize()
                    
                    direct_sql = text("""
                        SELECT COUNT(*) FROM athlete 
                        WHERE first_name LIKE :search_lower
                           OR first_name LIKE :search_upper
                           OR first_name LIKE :search_title
                           OR first_name LIKE :search_orig
                    """)
                    result = db.session.execute(direct_sql, {
                        'search_lower': f'%{search_lower}%',
                        'search_upper': f'%{search_upper}%',
                        'search_title': f'%{search_title}%',
                        'search_orig': f'%{normalized}%'
                    }).scalar()
                    logger.info(f"Прямой SQL запрос (first_name, LIKE с разными регистрами): найдено {result} спортсменов")
                    
                    # Также проверяем, есть ли вообще "Иван" в базе (с заглавной буквы)
                    ivan_check = text("SELECT COUNT(*) FROM athlete WHERE first_name LIKE '%Иван%'")
                    ivan_count = db.session.execute(ivan_check).scalar()
                    logger.info(f"Проверка наличия 'Иван' в базе (прямой LIKE '%Иван%'): найдено {ivan_count} записей")
                    
                    # Также проверяем с маленькой буквы
                    ivan_lower_check = text("SELECT COUNT(*) FROM athlete WHERE first_name LIKE '%иван%'")
                    ivan_lower_count = db.session.execute(ivan_lower_check).scalar()
                    logger.info(f"Проверка наличия 'иван' в базе (прямой LIKE '%иван%'): найдено {ivan_lower_count} записей")
                    
                    # Показываем примеры
                    if ivan_count > 0 or ivan_lower_count > 0:
                        sample_sql = text("SELECT id, first_name, last_name FROM athlete WHERE first_name LIKE '%Иван%' OR first_name LIKE '%иван%' LIMIT 5")
                        samples = db.session.execute(sample_sql).fetchall()
                        for row in samples:
                            logger.info(f"  Пример из БД: ID={row[0]}, first_name='{row[1]}', last_name='{row[2]}'")
                except Exception as sql_error:
                    logger.warning(f"Ошибка при прямом SQL запросе: {sql_error}", exc_info=True)
                
                # Если есть спортсмены без JOIN'ов, но нет с JOIN'ами - проблема в запросе
                if simple_count > 0:
                    logger.warning(f"ВНИМАНИЕ: Найдено {simple_count} спортсменов БЕЗ JOIN'ов, но 0 С JOIN'ами. Возможна проблема с применением фильтра после JOIN.")
                    
                    # Показываем примеры найденных спортсменов для отладки
                    sample_athletes = db.session.query(Athlete).filter(search_filter).limit(3).all()
                    for athlete in sample_athletes:
                        logger.info(f"  Пример: ID={athlete.id}, first_name='{athlete.first_name}', last_name='{athlete.last_name}', full_name_xml='{athlete.full_name_xml}', patronymic='{athlete.patronymic}'")
                else:
                    # Если не найдено, проверяем альтернативные варианты поиска
                    logger.info(f"Не найдено спортсменов с '{search}'. Проверяю альтернативные варианты...")
                    # Проверяем поиск по каждому полю отдельно (используем поиск в разных регистрах для SQLite)
                    search_lower = normalized.lower()
                    search_upper = normalized.upper()
                    search_title = normalized.capitalize()
                    
                    first_name_filter = db.or_(
                        Athlete.first_name.like(f'%{search_lower}%'),
                        Athlete.first_name.like(f'%{search_upper}%'),
                        Athlete.first_name.like(f'%{search_title}%'),
                        Athlete.first_name.like(f'%{normalized}%')
                    )
                    first_name_count = db.session.query(Athlete).filter(first_name_filter).count()
                    
                    last_name_filter = db.or_(
                        Athlete.last_name.like(f'%{search_lower}%'),
                        Athlete.last_name.like(f'%{search_upper}%'),
                        Athlete.last_name.like(f'%{search_title}%'),
                        Athlete.last_name.like(f'%{normalized}%')
                    )
                    last_name_count = db.session.query(Athlete).filter(last_name_filter).count()
                    
                    full_name_filter = db.or_(
                        Athlete.full_name_xml.like(f'%{search_lower}%'),
                        Athlete.full_name_xml.like(f'%{search_upper}%'),
                        Athlete.full_name_xml.like(f'%{search_title}%'),
                        Athlete.full_name_xml.like(f'%{normalized}%')
                    )
                    full_name_count = db.session.query(Athlete).filter(full_name_filter).count() if Athlete.full_name_xml else 0
                    
                    patronymic_filter = db.or_(
                        Athlete.patronymic.like(f'%{search_lower}%'),
                        Athlete.patronymic.like(f'%{search_upper}%'),
                        Athlete.patronymic.like(f'%{search_title}%'),
                        Athlete.patronymic.like(f'%{normalized}%')
                    )
                    patronymic_count = db.session.query(Athlete).filter(patronymic_filter).count() if Athlete.patronymic else 0
                    
                    logger.info(f"  По first_name: {first_name_count}, last_name: {last_name_count}, full_name_xml: {full_name_count}, patronymic: {patronymic_count}")
            except Exception as e:
                logger.warning(f"Ошибка при проверке простого запроса: {e}")
        else:
            # Если фильтр не создан (например, слишком короткий запрос)
            logger.warning(f"Поисковый фильтр не создан для запроса: '{search}' (нормализовано: '{normalized}', длина: {len(normalized)})")
    
    # Базовый запрос с JOIN для клубов
    # Применяем фильтр поиска СРАЗУ после создания базового запроса
    athletes_query = db.session.query(
        Athlete, Club
    ).outerjoin(Club, Athlete.club_id == Club.id)
    
    # Применяем фильтр поиска ДО всех остальных JOIN'ов
    if search_filter is not None:
        athletes_query = athletes_query.filter(search_filter)
        logger.info(f"Фильтр поиска применен к базовому запросу для '{search}'")
    
    # Добавляем JOIN с Participant и Category для сортировки по разрядам (если нужно)
    # Делаем это ПОСЛЕ применения фильтра поиска
    if sort_by == 'rank' or rank_filter or sort_by in ['participations', 'best_place']:
        athletes_query = athletes_query.outerjoin(
            Participant, Athlete.id == Participant.athlete_id
        )
        if sort_by == 'rank' or rank_filter:
            athletes_query = athletes_query.outerjoin(
                Category, Participant.category_id == Category.id
            )
            if rank_filter:
                athletes_query = athletes_query.filter(Category.normalized_name == rank_filter)
    
    # Добавляем group_by для агрегатных функций
    # Делаем это ПОСЛЕ фильтра поиска, чтобы фильтр применялся к базовым записям
    # ВАЖНО: group_by применяется всегда, если sort_by = 'best_place' (по умолчанию)
    # Это означает, что JOIN с Participant всегда делается, и фильтр должен работать ДО этого
    needs_group_by = sort_by in ['participations', 'best_place'] or sort_by == 'rank' or rank_filter
    if needs_group_by:
        athletes_query = athletes_query.group_by(Athlete.id, Club.id)
    
    # Сортировка
    if sort_by == 'name':
        order_column = Athlete.first_name
    elif sort_by == 'club':
        order_column = Club.name
    elif sort_by == 'participations':
        order_column = db.func.count(Participant.id)
    elif sort_by == 'best_place':
        order_column = db.func.min(Participant.total_place)
    elif sort_by == 'rank':
        order_column = db.func.coalesce(Category.normalized_name, 'Без разряда')
    else:
        order_column = Athlete.first_name
    
    if sort_order == 'desc':
        if sort_by == 'best_place':
            athletes_query = athletes_query.order_by(order_column.desc().nullslast())
        else:
            athletes_query = athletes_query.order_by(order_column.desc())
    else:
        if sort_by == 'best_place':
            athletes_query = athletes_query.order_by(order_column.asc().nullslast())
        else:
            athletes_query = athletes_query.order_by(order_column.asc())
    
    athletes = athletes_query.paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Для отладки - логируем информацию о поиске
    if search and search.strip():
        try:
            normalized = normalize_search_term(search)
            logger.info(f"Поиск '{search}' (нормализовано: '{normalized}'): найдено {athletes.total} спортсменов на странице {page}")
            if athletes.total == 0:
                logger.warning(f"Поиск '{search}' не дал результатов. Проверьте фильтр и данные в БД.")
                # Дополнительная проверка - может быть проблема с JOIN'ами
                if needs_group_by:
                    logger.warning(f"ВНИМАНИЕ: group_by применен (sort_by='{sort_by}'). Возможно, фильтр не работает после JOIN с Participant.")
        except Exception as e:
            logger.warning(f"Ошибка при логировании поиска: {e}")
    
    # Получаем данные участников для всех спортсменов одним запросом
    athlete_ids = [athlete.id for athlete, club in athletes.items]
    
    # Загружаем все участия для этих спортсменов
    participations_data = db.session.query(
        Participant.athlete_id,
        Participant.total_place,
        Participant.total_points,
        Participant.pct_ppname,
        Participant.status,
        Category.normalized_name,
        Event.begin_date,
        Event.end_date
    ).outerjoin(Category, Participant.category_id == Category.id).outerjoin(
        Event, Category.event_id == Event.id
    ).filter(Participant.athlete_id.in_(athlete_ids)).all()
    
    # Группируем данные по спортсменам
    athletes_stats = {}
    for row in participations_data:
        athlete_id = row.athlete_id
        if athlete_id not in athletes_stats:
            athletes_stats[athlete_id] = {
                'participations': [],
            'best_place': None,
            'best_points': None,
            'latest_category': None,
            'has_free_participation': False,
            'has_withdrawn': False
        }
        
        # Добавляем участие
        athletes_stats[athlete_id]['participations'].append(row)
        
        # Проверяем лучший результат
        if row.total_place and (athletes_stats[athlete_id]['best_place'] is None or row.total_place < athletes_stats[athlete_id]['best_place']):
            athletes_stats[athlete_id]['best_place'] = row.total_place
            athletes_stats[athlete_id]['best_points'] = row.total_points
        
        # Проверяем бесплатное участие
        if row.pct_ppname == 'БЕСП':
            athletes_stats[athlete_id]['has_free_participation'] = True
        
        # Проверяем статус снятия
        if row.status and row.status in ('R', 'W'):
            athletes_stats[athlete_id]['has_withdrawn'] = True
    
    # Находим последнюю категорию для каждого спортсмена
    for athlete_id, stats in athletes_stats.items():
        if stats['participations']:
            participations_with_dates = []
            for p in stats['participations']:
                event_date = p.begin_date or p.end_date
                if event_date:
                    participations_with_dates.append((p, event_date))
            
            if participations_with_dates:
                latest_participation, _ = max(participations_with_dates, key=lambda x: x[1])
                stats['latest_category'] = latest_participation.normalized_name
    
    # Формируем данные для JSON ответа
    athletes_data = []
    for athlete, club in athletes.items:
        stats = athletes_stats.get(athlete.id, {
            'participations': [],
            'best_place': None,
            'best_points': None,
            'latest_category': None,
            'has_free_participation': False,
            'has_withdrawn': False
        })
        
        athletes_data.append({
            'id': athlete.id,
            'full_name': athlete.full_name or '',  # Использует full_name_xml (PCT_PLNAME) если есть, иначе составное без дублирования
            'short_name': athlete.short_name or '',  # Использует очищенные имена без дублирования
            'birth_date': athlete.birth_date.strftime('%d.%m.%Y') if athlete.birth_date else None,
            'gender': athlete.gender,
            'category_name': stats['latest_category'],
            'club_name': club.name if club else None,
            'club_id': club.id if club else None,
            'participations_count': len(stats['participations']),
            'best_place': stats['best_place'],
            'best_points': round(stats['best_points'], 2) if stats['best_points'] else 0,
            'has_free_participation': stats['has_free_participation'],
            'has_withdrawn': stats.get('has_withdrawn', False)
        })
    
    return jsonify({
        'athletes': athletes_data,
        'pagination': {
            'page': athletes.page,
            'pages': athletes.pages,
            'per_page': athletes.per_page,
            'total': athletes.total,
            'has_next': athletes.has_next,
            'has_prev': athletes.has_prev,
            'next_num': athletes.next_num,
            'prev_num': athletes.prev_num
        },
        'search': search
    })

@api_bp.route('/category/<int:category_id>')
def api_category_details(category_id):
    """API: детальная информация по категории"""
    category = Category.query.get_or_404(category_id)
    segments = Segment.query.filter_by(category_id=category_id).all()
    participants = db.session.query(
        Participant, Athlete, Club
    ).join(
        Athlete, Participant.athlete_id == Athlete.id
    ).outerjoin(
        Club, Athlete.club_id == Club.id
    ).filter(
        Participant.category_id == category_id
    ).order_by(Participant.total_place.asc()).all()
    segments_data = []
    for segment in segments:
        performances = Performance.query.filter_by(segment_id=segment.id).all()
        segments_data.append({
            'id': segment.id,
            'name': segment.name,
            'short_name': segment.short_name,
            'type': segment.segment_type,
            'performances_count': len(performances)
        })
    return jsonify({
        'name': category.name,
        'event_name': category.event.name,
        'level': category.level,
        'gender': category.gender,
        'participants_count': len(participants),
        'segments': segments_data,
        'participants': [
            {
                'place': p.total_place,
                'athlete_id': a.id,
                'athlete_name': a.full_name or f"{a.last_name} {a.first_name}",
                'club_name': c.name if c else 'Не указан',
                'points': p.total_points
            }
            for p, a, c in participants
        ]
    })

@api_bp.route('/clubs')
def api_clubs():
    """API: список клубов с количеством спортсменов и участий"""
    clubs_data = db.session.query(
        Club.id,
        Club.name,
        Club.country,
        Club.city,
        db.func.count(db.distinct(Athlete.id)).label('athlete_count'),
        db.func.count(Participant.id).label('participation_count')
    ).outerjoin(Athlete, Club.id == Athlete.club_id).outerjoin(
        Participant, Athlete.id == Participant.athlete_id
    ).group_by(Club.id, Club.name, Club.country, Club.city).having(
        db.func.count(db.distinct(Athlete.id)) > 0
    ).order_by(
        db.func.count(db.distinct(Athlete.id)).desc()
    ).all()
    
    return jsonify([
        {
            'id': club.id,
            'name': club.name,
            'country': club.country,
            'city': club.city,
            'athlete_count': club.athlete_count or 0,
            'participation_count': club.participation_count or 0
        }
        for club in clubs_data
    ])

@api_bp.route('/analytics/free-participation-analysis')
def api_free_participation_analysis():
    """API для анализа бесплатного участия с фильтрацией по количеству участий"""
    try:
        min_participations = request.args.get('min_participations', 1, type=int)
        max_participations = request.args.get('max_participations', 999, type=int)
        season_filter = request.args.get('season', '')
        query = db.session.query(
            Athlete.id,
            Athlete.first_name,
            Athlete.last_name,
            Athlete.full_name_xml,
            Athlete.birth_date,
            Athlete.gender,
            Club.name.label('club_name'),
            Club.id.label('club_id'),
            Event.name.label('event_name'),
            Event.begin_date.label('event_date'),
            Event.end_date.label('event_end_date'),
            Category.name.label('category_name'),
            Category.gender.label('category_gender'),
            Category.normalized_name.label('normalized_name'),
            Participant.pct_ppname,
            Participant.total_place,
            Participant.total_points
        ).select_from(Athlete).outerjoin(
            Club, Athlete.club_id == Club.id
        ).join(
            Participant, Athlete.id == Participant.athlete_id
        ).join(
            Category, Participant.category_id == Category.id
        ).join(
            Event, Category.event_id == Event.id
        ).filter(
            Participant.pct_ppname == 'БЕСП'
        )
        if season_filter:
            if season_filter == 'current':
                current_year = datetime.now().year
                if datetime.now().month >= 7:
                    start_date = datetime(current_year, 7, 1)
                    end_date = datetime(current_year + 1, 6, 30)
                else:
                    start_date = datetime(current_year - 1, 7, 1)
                    end_date = datetime(current_year, 6, 30)
            else:
                try:
                    start_year = int(season_filter.split('/')[0])
                    start_date = datetime(start_year, 7, 1)
                    end_date = datetime(start_year + 1, 6, 30)
                except (ValueError, IndexError):
                    start_date = None
                    end_date = None
            if start_date and end_date:
                query = query.filter(Event.begin_date >= start_date, Event.begin_date <= end_date)
        free_participants = query.order_by(
            Event.begin_date.desc(), Athlete.last_name, Athlete.first_name
        ).all()
        def get_athlete_name(athlete):
            if athlete['full_name_xml']:
                return athlete['full_name_xml']
            return f"{athlete['last_name']} {athlete['first_name']}"
        def get_season_from_date(date_obj):
            if not date_obj:
                return "Неизвестно"
            if date_obj.month >= 7:
                start_year = date_obj.year
                end_year = date_obj.year + 1
            else:
                start_year = date_obj.year - 1
                end_year = date_obj.year
            return f"{start_year}/{str(end_year)[-2:]}"
        athletes_data = {}
        for row in free_participants:
            athlete_id = row.id
            if athlete_id not in athletes_data:
                athletes_data[athlete_id] = {
                    'id': athlete_id,
                    'name': get_athlete_name({
                        'first_name': row.first_name,
                        'last_name': row.last_name,
                        'full_name_xml': row.full_name_xml
                    }),
                    'birth_date': row.birth_date.strftime('%d.%m.%Y') if row.birth_date else 'Не указана',
                    'gender': 'Женский' if row.gender == 'F' else 'Мужской' if row.gender == 'M' else 'Не указан',
                    'club_name': row.club_name or 'Не указан',
                    'club_id': row.club_id,
                    'free_participations': 0,
                    'seasons': set(),
                    'events': []
                }
            rank = row.normalized_name or normalize_category_name(row.category_name, row.category_gender)
            athletes_data[athlete_id]['free_participations'] += 1
            athletes_data[athlete_id]['seasons'].add(get_season_from_date(row.event_date))
            
            # Форматируем баллы
            points_display = None
            if row.total_points is not None:
                try:
                    points_value = float(row.total_points)
                    if points_value > 1000:
                        points_value = points_value / 100
                    
                    if 0 <= points_value <= 1000:
                        points_display = f"{points_value:.2f}".rstrip('0').rstrip('.')
                    else:
                        points_display = None
                except (ValueError, TypeError):
                    points_display = None
            
            athletes_data[athlete_id]['events'].append({
                'event_name': row.event_name,
                'event_date': row.event_date.strftime('%d.%m.%Y') if row.event_date else 'Дата не указана',
                'event_end_date': row.event_end_date.strftime('%d.%m.%Y') if row.event_end_date else None,
                'category_name': row.category_name,
                'rank': rank,
                'place': row.total_place,
                'points': points_display,
                'season': get_season_from_date(row.event_date)
            })
        for athlete in athletes_data.values():
            athlete['seasons'] = sorted(list(athlete['seasons']))
        filtered_athletes = [
            athlete for athlete in athletes_data.values()
            if min_participations <= athlete['free_participations'] <= max_participations
        ]
        result = sorted(filtered_athletes, key=lambda x: x['free_participations'], reverse=True)
        
        # Статистика
        total_athletes = len(result)
        total_participations = sum(a['free_participations'] for a in result)
        avg_participations = total_participations / total_athletes if total_athletes > 0 else 0
        
        # Группировка по количеству участий
        participation_groups = {}
        for athlete in result:
            count = athlete['free_participations']
            if count not in participation_groups:
                participation_groups[count] = 0
            participation_groups[count] += 1
        
        return jsonify({
            'athletes': result,
            'statistics': {
                'total_athletes': total_athletes,
                'total_participations': total_participations,
                'avg_participations': round(avg_participations, 1),
                'participation_groups': participation_groups
            },
            'filters': {
                'min_participations': min_participations,
                'max_participations': max_participations,
                'season': season_filter
            }
        })
    except Exception as e:
        logger.error(f"Ошибка в api_free_participation_analysis: {e}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/coaches')
def api_coaches():
    """API для получения списка тренеров"""
    try:
        search = request.args.get('search', '').strip()
        sort_by = request.args.get('sort_by', 'athletes')
        sort_order = request.args.get('sort_order', 'desc')
        
        query = db.session.query(
            Coach.id,
            Coach.name,
            db.func.count(CoachAssignment.id).label('athletes_count')
        ).outerjoin(
            CoachAssignment, 
            db.and_(
                Coach.id == CoachAssignment.coach_id,
                CoachAssignment.is_current == True
            )
        ).group_by(Coach.id, Coach.name)
        
        # Поиск с нормализацией
        if search:
            search_filter = create_multi_field_search_filter(search, Coach.name)
            if search_filter is not None:
                query = query.filter(search_filter)
        
        # Сортировка
        if sort_by == 'name':
            order_by = Coach.name.asc() if sort_order == 'asc' else Coach.name.desc()
        elif sort_by == 'athletes':
            order_by = db.func.count(CoachAssignment.id).asc() if sort_order == 'asc' else db.func.count(CoachAssignment.id).desc()
        else:
            order_by = db.func.count(CoachAssignment.id).desc()
        
        query = query.order_by(order_by)
        coaches_data = query.all()
        
        coaches = []
        for coach_id, coach_name, athletes_count in coaches_data:
            coaches.append({
                'id': coach_id,
                'name': coach_name,
                'athletes_count': athletes_count or 0
            })
        
        return jsonify({'coaches': coaches})
    except Exception as e:
        logger.error(f"Ошибка в api_coaches: {e}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/participant/<int:participant_id>/performance-details')
def api_participant_performance_details(participant_id):
    """API для получения детальной информации о выступлении участника (распечатка)"""
    try:
        participant = Participant.query.get_or_404(participant_id)
        
        # Получаем все выступления (performance) для этого участника
        performances = Performance.query.filter_by(participant_id=participant_id).order_by(Performance.index).all()
        
        # Получаем информацию о событии и категории
        event = Event.query.get(participant.event_id)
        category = Category.query.get(participant.category_id)
        athlete = Athlete.query.get(participant.athlete_id)
        club = Club.query.get(athlete.club_id) if athlete and athlete.club_id else None
        
        # Формируем данные для каждого выступления
        performances_data = []
        for perf in performances:
            segment = Segment.query.get(perf.segment_id)
            
            # Получаем элементы
            elements = Element.query.filter_by(performance_id=perf.id).order_by(Element.order_num).all()
            elements_data = []
            for elem in elements:
                judge_scores = elem.judge_scores or {}
                # Извлекаем оценки судей J1, J2, J3 и т.д.
                judge_scores_list = []
                for j in range(1, 16):  # Обычно до 9 судей, но на всякий случай до 15
                    key = f'J{j:02d}'
                    score = judge_scores.get(key)
                    if score is None:
                        # Пробуем без нуля впереди
                        key_alt = f'J{j}'
                        score = judge_scores.get(key_alt)
                    
                    if score is not None:
                        # Декодируем оценку судьи из кода XML в значение GOE
                        # Оценки судей могут храниться в БД как:
                        # 1. Коды (0-15) - новые данные, нужно декодировать
                        # 2. Декодированные значения (-5 до +3) - старые данные, нужно исправить +1
                        try:
                            from parsers.isu_calcfs_parser import ISUCalcFSParser
                            # Если это число (код или декодированное значение)
                            if isinstance(score, (int, str)):
                                score_num = int(score) if isinstance(score, str) else score
                                
                                # Если значение в диапазоне кодов (0-15), декодируем
                                if 0 <= score_num <= 15:
                                    decoded_score = ISUCalcFSParser._decode_judge_score_xml(score_num)
                                    judge_scores_list.append(decoded_score)
                                # Если значение в диапазоне старых декодированных значений (-5 до +3)
                                # Это старые данные, которые были декодированы с неправильной формулой
                                # Нужно исправить: добавляем +1
                                elif -5 <= score_num <= 3:
                                    corrected_score = score_num + 1
                                    judge_scores_list.append(corrected_score)
                                else:
                                    # Если значение вне известных диапазонов, используем как есть
                                    judge_scores_list.append(score_num)
                            else:
                                judge_scores_list.append(score)
                        except (ValueError, TypeError):
                            # Если не удалось преобразовать, оставляем как есть
                            judge_scores_list.append(score)
                    else:
                        break  # Если нет оценки, дальше тоже не будет
                
                # Форматируем базовую стоимость и GOE
                # В БД все значения хранятся ×100 (60 = 0.60, 5500 = 55.00)
                # Поэтому всегда делим на 100, но проверяем разумные границы
                base_value = None
                if elem.base_value is not None:
                    # Если значение > 10, значит оно в формате ×100 (например, 60 = 0.60, 110 = 1.10)
                    # Если значение <= 10, возможно уже правильное, но обычно это тоже ×100
                    # Для безопасности: если > 1, делим на 100
                    base_value = elem.base_value / 100.0 if abs(elem.base_value) > 1 else elem.base_value
                
                goe_result = None
                if elem.goe_result is not None:
                    # GOE может быть отрицательным, проверяем абсолютное значение
                    # Если > 1, значит ×100 (например, 55 = 0.55, -36 = -0.36)
                    goe_result = elem.goe_result / 100.0 if abs(elem.goe_result) > 1 else elem.goe_result
                
                element_score = None
                if elem.result is not None:
                    try:
                        result_num = float(elem.result) if isinstance(elem.result, str) else elem.result
                        # Если > 1, значит ×100 (например, 55 = 0.55, 64 = 0.64)
                        element_score = result_num / 100.0 if abs(result_num) > 1 else result_num
                    except (ValueError, TypeError):
                        element_score = elem.result
                elif base_value is not None and goe_result is not None:
                    element_score = base_value + goe_result
                
                elements_data.append({
                    'order_num': elem.order_num,
                    'executed_code': elem.executed_code or elem.planned_code or '',
                    'info_code': elem.info_code or '',
                    'base_value': round(base_value, 2) if base_value is not None else None,
                    'goe_result': round(goe_result, 2) if goe_result is not None else None,
                    'penalty': elem.penalty,
                    'result': round(element_score, 2) if element_score is not None else None,
                    'judge_scores': judge_scores_list[:3]  # Первые 3 судьи для отображения
                })
            
            # Получаем компоненты программы
            components = ComponentScore.query.filter_by(performance_id=perf.id).all()
            components_data = []
            for comp in components:
                judge_scores = comp.judge_scores or {}
                # Извлекаем оценки судей
                judge_scores_list = []
                for j in range(1, 16):
                    key = f'J{j:02d}'
                    score = judge_scores.get(key)
                    if score is not None:
                        # Преобразуем в число, если это строка
                        try:
                            score_num = float(score) if isinstance(score, str) else score
                            judge_scores_list.append(score_num / 100.0 if score_num > 10 else score_num)
                        except (ValueError, TypeError):
                            judge_scores_list.append(score)
                    else:
                        key_alt = f'J{j}'
                        score = judge_scores.get(key_alt)
                        if score is not None:
                            # Преобразуем в число, если это строка
                            try:
                                score_num = float(score) if isinstance(score, str) else score
                                judge_scores_list.append(score_num / 100.0 if score_num > 10 else score_num)
                            except (ValueError, TypeError):
                                judge_scores_list.append(score)
                        else:
                            break
                
                # Вычисляем итоговую оценку компонента
                # В БД все значения хранятся ×100
                component_result = None
                if comp.result is not None:
                    try:
                        result_num = float(comp.result) if isinstance(comp.result, str) else comp.result
                        # Если > 1, значит ×100 (например, 513 = 5.13, 500 = 5.00)
                        component_result = result_num / 100.0 if abs(result_num) > 1 else result_num
                    except (ValueError, TypeError):
                        component_result = comp.result
                elif judge_scores_list and comp.factor:
                    avg_score = sum(judge_scores_list) / len(judge_scores_list) if judge_scores_list else 0
                    component_result = avg_score * comp.factor
                
                # Определяем название компонента
                component_name_map = {
                    'SS': 'Мастерство катания',
                    'TR': 'Переходы',
                    'PE': 'Представление',
                    'CH': 'Композиция',
                    'IN': 'Интерпретация',
                    'CO': 'Композиция',
                    'PR': 'Представление',
                    'SK': 'Мастерство катания'
                }
                component_name = component_name_map.get(comp.component_type, comp.component_type or 'Компонент')
                
                components_data.append({
                    'type': comp.component_type,
                    'name': component_name,
                    'factor': comp.factor,
                    'judge_scores': judge_scores_list[:3] if len(judge_scores_list) >= 3 else judge_scores_list,
                    'result': round(component_result, 2) if component_result is not None else None
                })
            
            # Форматируем общие баллы
            # В БД все значения хранятся ×100
            tes_total = None
            if perf.tes_total is not None:
                # Если > 10, значит ×100 (например, 74500 = 745.00, 1810 = 18.10)
                tes_total = perf.tes_total / 100.0 if abs(perf.tes_total) > 10 else perf.tes_total
            
            pcs_total = None
            if perf.pcs_total is not None:
                # Если > 10, значит ×100 (например, 2013 = 20.13, 1013 = 10.13)
                pcs_total = perf.pcs_total / 100.0 if abs(perf.pcs_total) > 10 else perf.pcs_total
            
            deductions = None
            if perf.deductions is not None:
                # Если > 1, значит ×100 (например, 0 = 0.00, 100 = 1.00)
                deductions = abs(perf.deductions) / 100.0 if abs(perf.deductions) > 1 else abs(perf.deductions)
            
            # Нормализуем points (сумма за сегмент)
            # В БД points уже нормализован через _parse_score (делится на 100 при сохранении)
            # Но могут быть старые данные в формате ×100, поэтому проверяем
            segment_points = None
            if perf.points is not None:
                # Если значение > 100, значит оно в формате ×100 (например, 1758 = 17.58)
                # Если значение <= 100, значит уже нормализовано (например, 17.58)
                # Для фигурного катания сумма за программу редко превышает 100 баллов
                segment_points = perf.points / 100.0 if abs(perf.points) > 100 else perf.points
            
            performances_data.append({
                'id': perf.id,
                'segment_name': segment.name if segment else 'Неизвестный сегмент',
                'segment_type': segment.segment_type if segment else None,
                'place': perf.place,
                'points': round(segment_points, 2) if segment_points is not None else None,
                'tes_total': round(tes_total, 2) if tes_total is not None else None,
                'pcs_total': round(pcs_total, 2) if pcs_total is not None else None,
                'deductions': round(deductions, 2) if deductions is not None else 0.00,
                'elements': elements_data,
                'components': components_data
            })
        
        # Формируем итоговые данные
        # participant.total_points уже нормализован при сохранении через _parse_score
        # Но могут быть старые данные в формате ×100
        total_points_normalized = None
        if participant.total_points is not None:
            # Если значение > 100, значит оно в формате ×100 (например, 1758 = 17.58)
            # Если значение <= 100, значит уже нормализовано (например, 17.58)
            total_points_normalized = participant.total_points / 100.0 if abs(participant.total_points) > 100 else participant.total_points
        
        result = {
            'participant': {
                'id': participant.id,
                'bib_number': participant.bib_number,
                'total_place': participant.total_place,
                'total_points': round(total_points_normalized, 2) if total_points_normalized is not None else None,
                'status': participant.status,
                'coach': participant.coach
            },
            'event': {
                'id': event.id if event else None,
                'name': event.name if event else 'Неизвестный турнир',
                'begin_date': event.begin_date.strftime('%d.%m.%Y') if event and event.begin_date else None,
                'end_date': event.end_date.strftime('%d.%m.%Y') if event and event.end_date else None,
                'place': event.place if event else None
            },
            'category': {
                'id': category.id if category else None,
                'name': category.name if category else 'Неизвестная категория',
                'gender': category.gender if category else None,
                'category_type': category.category_type if category else None
            },
            'athlete': {
                'id': athlete.id if athlete else None,
                'full_name': athlete.full_name if athlete else 'Неизвестный спортсмен',
                'club_name': club.name if club else None
            },
            'performances': performances_data
        }
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Ошибка в api_participant_performance_details: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
