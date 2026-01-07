#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API endpoints приложения
"""

from flask import Blueprint, jsonify, request, Response
from models import db, Event, Category, Athlete, Participant, Club, Performance
from season_utils import get_season_from_date
from utils.category_normalization import normalize_category_name, get_rank_weight, get_rank_catalog, _create_rank_entry
from collections import defaultdict
from datetime import datetime
import logging

api_bp = Blueprint('api', __name__, url_prefix='/api')
logger = logging.getLogger(__name__)

@api_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint для мониторинга состояния приложения"""
    try:
        # Проверяем подключение к БД
        db.session.execute(db.text('SELECT 1'))
        db_status = 'connected'
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        db_status = f'error: {str(e)}'
        return jsonify({
            'status': 'unhealthy',
            'database': db_status,
            'timestamp': datetime.now().isoformat()
        }), 503
    
    return jsonify({
        'status': 'healthy',
        'database': db_status,
        'timestamp': datetime.now().isoformat()
    }), 200

@api_bp.route('/athlete/<int:athlete_id>/results-chart')
def api_athlete_results_chart(athlete_id):
    """API для получения данных графика результатов спортсмена"""
    athlete = Athlete.query.get_or_404(athlete_id)
    
    # Получаем все участия спортсмена с данными о турнирах
    participations = db.session.query(
        Event, Category, Participant
    ).join(
        Category, Participant.category_id == Category.id
    ).join(
        Event, Category.event_id == Event.id
    ).filter(
        Participant.athlete_id == athlete_id
    ).order_by(Event.begin_date.asc()).all()
    
    # Формируем данные для графика
    chart_data = {
        'labels': [],  # Даты турниров
        'places': [],  # Места
        'points': [],  # Баллы
        'tournaments': [],  # Названия турниров
        'categories': [],  # Категории
        'seasons': []  # Сезоны
    }
    
    for event, category, participant in participations:
        if event.begin_date:
            # Форматируем дату для отображения
            date_str = event.begin_date.strftime('%d.%m.%Y')
            chart_data['labels'].append(date_str)
            chart_data['places'].append(participant.total_place or 0)
            chart_data['points'].append(round(participant.total_points / 100, 2) if participant.total_points else 0)
            chart_data['tournaments'].append(event.name)
            chart_data['categories'].append(category.name)
            chart_data['seasons'].append(get_season_from_date(event.begin_date))
    
    return jsonify(chart_data)

@api_bp.route('/events', methods=['GET'])
def api_events():
    """Возвращает список турниров для интеграций"""
    # Пагинация для API
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    events_pagination = Event.query.order_by(Event.begin_date.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    events = events_pagination.items
    
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
    
    return jsonify({
        'total': events_pagination.total,
        'page': events_pagination.page,
        'per_page': events_pagination.per_page,
        'pages': events_pagination.pages,
        'has_next': events_pagination.has_next,
        'has_prev': events_pagination.has_prev,
        'events': events_payload
    })

@api_bp.route('/event/<int:event_id>/export')
def export_event_results(event_id):
    """Экспорт результатов турнира в CSV"""
    event = Event.query.get_or_404(event_id)
    
    # Получаем все результаты турнира
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
    
    # Создаем CSV содержимое
    csv_content = "Фамилия,Имя,Отчество,Клуб,Категория,Пол,Тип,Место,Баллы,Турнир,Дата\n"
    
    for result in results:
        csv_content += f'"{result.last_name or ""}","{result.first_name or ""}","{result.patronymic or ""}","{result.club_name or ""}","{result.category_name or ""}","{result.gender or ""}","{result.category_type or ""}","{result.total_place or ""}","{round(result.total_points / 100, 2) if result.total_points else ""}","{result.event_name or ""}","{result.begin_date.strftime("%d.%m.%Y") if result.begin_date else ""}"\n'
    
    # Создаем ответ с CSV файлом
    response = Response(
        csv_content,
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename=results_{event.name.replace(" ", "_")}_{event.begin_date.strftime("%Y%m%d") if event.begin_date else "unknown"}.csv'
        }
    )
    
    return response

@api_bp.route('/statistics')
def api_statistics():
    """API для получения статистики"""
    total_athletes = Athlete.query.count()
    total_events = Event.query.count()
    total_participations = Participant.query.count()
    
    # Статистика по клубам
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
        # Получаем всех спортсменов с их результатами по разрядам
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
        ).select_from(Athlete).join(Participant, Athlete.id == Participant.athlete_id).join(Category, Participant.category_id == Category.id).group_by(
            Athlete.id, Category.name, Category.gender, Category.normalized_name
        ).all()
        
        def get_athlete_name(athlete):
            """Получает имя спортсмена"""
            if athlete['full_name_xml']:
                return athlete['full_name_xml']
            return f"{athlete['last_name']} {athlete['first_name']}"
        
        # Группируем по разрядам
        ranks_data = {}
        total_participations = {}
        
        for row in athletes_query:
            # Используем normalized_name из БД, а не пересчитываем
            rank = row.normalized_name or normalize_category_name(row.category_name, row.category_gender)
            rank_weight = get_rank_weight(rank)
            
            if rank not in ranks_data:
                ranks_data[rank] = {
                    'name': rank,
                    'weight': rank_weight,
                    'athletes': []
                }
            
            athlete_data = {
                'id': row.id,
                'name': get_athlete_name({
                    'first_name': row.first_name,
                    'last_name': row.last_name,
                    'full_name_xml': row.full_name_xml
                }),
                'participations': row.participations,
                'best_place': row.best_place,
                'best_points': round(row.best_points / 100, 2) if row.best_points else 0
            }
            
            ranks_data[rank]['athletes'].append(athlete_data)
            
            # Считаем общее количество участий для спортсмена
            athlete_id = row.id
            if athlete_id not in total_participations:
                total_participations[athlete_id] = 0
            total_participations[athlete_id] += row.participations
        
        # Сортируем спортсменов внутри каждого разряда по лучшим результатам
        for rank in ranks_data:
            ranks_data[rank]['athletes'].sort(
                key=lambda x: (x['best_place'] or 999, -x['best_points'])
            )
        
        # Сортируем разряды по весу (лучшие разряды первыми)
        sorted_ranks = sorted(ranks_data.values(), key=lambda x: x['weight'])
        
        # Топ по участиям (все спортсмены, отсортированные по общему количеству участий)
        all_athletes = []
        for row in athletes_query:
            athlete_id = row.id
            # Используем normalized_name из БД, а не пересчитываем
            rank = row.normalized_name or normalize_category_name(row.category_name, row.category_gender)
            
            # Проверяем, не добавлен ли уже этот спортсмен
            if not any(a['id'] == athlete_id for a in all_athletes):
                all_athletes.append({
                    'id': athlete_id,
                    'name': get_athlete_name({
                        'first_name': row.first_name,
                        'last_name': row.last_name,
                        'full_name_xml': row.full_name_xml
                    }),
                    'participations': total_participations.get(athlete_id, 0),
                    'best_place': row.best_place,
                    'best_points': round(row.best_points / 100, 2) if row.best_points else 0,
                    'rank': rank
                })
        
        top_by_participations = sorted(
            all_athletes, 
            key=lambda x: x['participations'], 
            reverse=True
        )[:10]
        
        return jsonify({
            'by_ranks': sorted_ranks,
            'by_participations': top_by_participations
        })
    except Exception as e:
        logger.error(f"Ошибка в api_top_athletes: {e}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/analytics/club-statistics')
def api_club_statistics():
    """API для получения статистики по клубам"""
    # Получаем статистику по клубам с количеством спортсменов
    club_athlete_stats = db.session.query(
        Club.id,
        Club.name,
        db.func.count(Athlete.id).label('athlete_count')
    ).outerjoin(Athlete, Club.id == Athlete.club_id).group_by(
        Club.id, Club.name
    ).all()
    
    # Получаем статистику по участиям для каждого клуба
    club_participation_stats = db.session.query(
        Club.id,
        db.func.count(Participant.id).label('participation_count'),
        db.func.min(Participant.total_place).label('best_place')
    ).join(Athlete, Club.id == Athlete.club_id).outerjoin(
        Participant, Athlete.id == Participant.athlete_id
    ).group_by(Club.id).all()
    
    # Объединяем данные
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
    
    # Сортируем по количеству спортсменов
    result.sort(key=lambda x: x['athlete_count'], reverse=True)
    
    return jsonify(result)

@api_bp.route('/analytics/category-statistics')
def api_category_statistics():
    """API для получения статистики по категориям (группировка по разрядам)"""
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
    
    # Группируем по разрядам
    rank_stats = {}
    for stat in category_stats:
        # Используем normalized_name из БД, а не пересчитываем
        rank = stat.normalized_name or normalize_category_name(stat.name, stat.gender)
        gender = stat.gender or 'U'  # U = Unknown
        
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
    
    # Вычисляем средние баллы
    for rank in rank_stats:
        total_points = 0
        total_count = 0
        for stat in category_stats:
            if (stat.normalized_name or normalize_category_name(stat.name)) == rank and stat.avg_points:
                total_points += stat.avg_points * stat.participant_count
                total_count += stat.participant_count
        
        if total_count > 0:
            rank_stats[rank]['avg_points'] = round(total_points / total_count / 100, 2)
    
    # Сортируем по количеству участников
    result = sorted(rank_stats.values(), key=lambda x: x['total_participants'], reverse=True)
    
    return jsonify(result)

@api_bp.route('/analytics/free-participation')
def api_free_participation():
    """API для получения спортсменов с бесплатным участием"""
    try:
        # Получаем всех спортсменов с бесплатным участием
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
            Event, Participant.event_id == Event.id
        ).join(
            Category, Participant.category_id == Category.id
        ).filter(
            Participant.pct_ppname == 'БЕСП'
        ).order_by(
            Event.begin_date.desc(), Athlete.last_name, Athlete.first_name
        ).all()

        def get_athlete_name(athlete):
            """Получает имя спортсмена"""
            if athlete['full_name_xml']:
                return athlete['full_name_xml']
            return f"{athlete['last_name']} {athlete['first_name']}"

        # Группируем по спортсменам
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
                    'free_participations': 0,
                    'events': [],
                    'rank_counts': defaultdict(int),
                    'events_by_rank': defaultdict(list),
                    'last_event': None
                }

            # Используем normalized_name из БД, а не пересчитываем
            rank = row.normalized_name or normalize_category_name(row.category_name, row.category_gender)

            athletes_data[athlete_id]['free_participations'] += 1
            # Форматируем баллы
            points_display = None
            if row.total_points is not None:
                try:
                    points_value = float(row.total_points)
                    # Если значение больше 1000, делим на 100 (например, 12284 -> 122.84)
                    if points_value > 1000:
                        points_value = points_value / 100
                    
                    # Проверяем, что это разумное значение баллов
                    if 0 <= points_value <= 1000:
                        points_display = f"{points_value:.2f}".rstrip('0').rstrip('.')
                    else:
                        points_display = None
                except (ValueError, TypeError):
                    points_display = None

            event_date_display = row.event_date.strftime('%d.%m.%Y') if row.event_date else 'Дата не указана'
            event_date_iso = row.event_date.isoformat() if row.event_date else None

            event_info = {
                'event_name': row.event_name,
                'event_date': event_date_display,
                'event_date_iso': event_date_iso,
                'category_name': row.category_name,
                'rank': rank,
                'gender': row.category_gender,
                'place': row.total_place,
                'points': points_display
            }

            athletes_data[athlete_id]['events'].append(event_info)
            athletes_data[athlete_id]['events_by_rank'][rank].append(event_info)
            athletes_data[athlete_id]['rank_counts'][rank] += 1

            if row.event_date and (athletes_data[athlete_id]['last_event'] is None or row.event_date > athletes_data[athlete_id]['last_event']):
                athletes_data[athlete_id]['last_event'] = row.event_date

        # Подготавливаем данные спортсменов
        result = []
        for athlete in athletes_data.values():
            rank_counts = athlete.pop('rank_counts', {})
            events_by_rank = athlete.get('events_by_rank', {})
            last_event = athlete.pop('last_event', None)

            athlete['last_event_date'] = last_event.isoformat() if last_event else None
            athlete['last_event_display'] = last_event.strftime('%d.%m.%Y') if last_event else None

            ranks_list = sorted(
                [{'name': rank_name, 'count': count} for rank_name, count in rank_counts.items()],
                key=lambda x: x['count'],
                reverse=True
            )
            athlete['ranks'] = ranks_list
            athlete['dominant_rank'] = ranks_list[0]['name'] if ranks_list else None
            athlete['unique_ranks_count'] = len(ranks_list)
            athlete['events_by_rank'] = {rank_name: list(events) for rank_name, events in events_by_rank.items()}

            result.append(athlete)

        # Сортируем по количеству бесплатных участий
        result.sort(key=lambda x: x['free_participations'], reverse=True)

        # Формируем данные по разрядам
        rank_catalog = get_rank_catalog()
        rank_athletes_map = {}

        for athlete in result:
            events_by_rank = athlete.get('events_by_rank', {})
            for rank_entry in athlete['ranks']:
                rank_name = rank_entry['name']
                rank_events = list(events_by_rank.get(rank_name, []))

                if rank_name not in rank_catalog:
                    base_name = rank_name.split(',')[0].strip()
                    rank_catalog[rank_name] = _create_rank_entry(rank_name, 'U', base_name)

                key = (rank_name, athlete['id'])
                if key not in rank_athletes_map:
                    rank_athletes_map[key] = {
                        'id': athlete['id'],
                        'name': athlete['name'],
                        'free_participations': rank_entry['count'],
                        'events': rank_events,
                        'last_event': None,
                        'last_event_display': None
                    }
                else:
                    rank_athletes_map[key]['free_participations'] += rank_entry['count']
                    rank_athletes_map[key]['events'].extend(rank_events)

                # Обновляем дату последнего старта для спортсмена внутри разряда
                for event in rank_events:
                    event_iso = event.get('event_date_iso')
                    if not event_iso:
                        continue
                    try:
                        event_date = datetime.strptime(event_iso, '%Y-%m-%d')
                    except ValueError:
                        continue

                    if (rank_athletes_map[key]['last_event'] is None) or (event_date > rank_athletes_map[key]['last_event']):
                        rank_athletes_map[key]['last_event'] = event_date
                        rank_athletes_map[key]['last_event_display'] = event.get('event_date')

        # Заполняем данные по разрядам
        for (rank_name, athlete_id), data in rank_athletes_map.items():
            rank_entry = rank_catalog[rank_name]
            rank_entry['has_data'] = True
            rank_entry['athlete_count'] += 1
            rank_entry['total_participations'] += len(data['events'])
            rank_entry['max_free_participations'] = max(rank_entry['max_free_participations'], data['free_participations'])

            rank_entry['athletes'].append({
                'id': data['id'],
                'name': data['name'],
                'free_participations': data['free_participations'],
                'events_count': len(data['events']),
                'last_event_date': data['last_event'].strftime('%Y-%m-%d') if data['last_event'] else None,
                'last_event_display': data['last_event_display'],
                'events': data['events']
            })

        # Сортируем спортсменов внутри разряда
        for entry in rank_catalog.values():
            entry['athletes'].sort(
                key=lambda athlete: (
                    athlete['free_participations'] or 0,
                    athlete['last_event_date'] or '',
                    athlete['name']
                ),
                reverse=True
            )

        rank_groups = []
        for entry in sorted(rank_catalog.values(), key=lambda item: (item['weight'], item['display_name'].lower())):
            rank_groups.append({
                'display_name': entry['display_name'],
                'base_name': entry['base_name'],
                'gender': entry['gender'],
                'gender_label': entry['gender_label'],
                'weight': entry['weight'],
                'anchor': entry['anchor'],
                'athletes': entry['athletes'],
                'athlete_count': entry['athlete_count'],
                'total_participations': entry['total_participations'],
                'total_free_participations': entry['total_free_participations'],
                'max_free_participations': entry['max_free_participations'],
                'has_data': entry['has_data']
            })

        ranks_with_data = [group for group in rank_groups if group['athletes']]
        unique_rank_athlete_ids = set()
        for group in rank_groups:
            for athlete in group.get('athletes', []):
                athlete_id = athlete.get('id')
                if athlete_id is not None:
                    unique_rank_athlete_ids.add(athlete_id)
        rank_summary = {
            'total_ranks': len(rank_groups),
            'ranks_with_data': len(ranks_with_data),
            'total_athletes': len(unique_rank_athlete_ids),
            'total_free_participations': sum(group['total_free_participations'] for group in ranks_with_data)
        }

        # Удаляем временные данные перед возвратом ответа
        for athlete in result:
            if 'events_by_rank' in athlete:
                del athlete['events_by_rank']

        return jsonify({
            'athletes': result,
            'total_athletes': len(result),
            'total_free_participations': sum(a['free_participations'] for a in result),
            'rank_groups': rank_groups,
            'rank_summary': rank_summary
        })

    except Exception as e:
        logger.error(f"Error in api_free_participation: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/analytics/club-free-participation')
def api_club_free_participation():
    """API для получения статистики бесплатного участия по школам/клубам"""
    try:
        # Получаем статистику по клубам с бесплатным участием
        club_stats = db.session.query(
            Club.id,
            Club.name,
            Club.short_name,
            Club.country,
            Club.city,
            db.func.count(db.distinct(Athlete.id)).label('total_athletes'),
            db.func.count(db.distinct(db.case((Participant.pct_ppname == 'БЕСП', Athlete.id), else_=None))).label('athletes_with_free_participation'),
            db.func.count(Participant.id).label('total_participations'),
            db.func.count(db.case((Participant.pct_ppname == 'БЕСП', 1), else_=None)).label('free_participations')
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
        logger.error(f"Error in api_club_free_participation: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/athletes')
def api_athletes():
    """API для получения списка спортсменов с поиском и сортировкой"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    search = request.args.get('search', '').strip()
    rank_filter = request.args.get('rank', '').strip()
    
    # Параметры сортировки
    sort_by = request.args.get('sort_by', 'best_place')
    sort_order = request.args.get('sort_order', 'asc')

    # Базовый запрос с JOIN для клубов
    athletes_query = db.session.query(
        Athlete, Club
    ).outerjoin(Club, Athlete.club_id == Club.id)
    
    # Добавляем поиск по имени или фамилии (нечувствительный к регистру)
    if search:
        # Создаем фильтры для поиска в разных регистрах
        search_lower = search.strip().lower()
        search_upper = search.strip().upper()
        search_title = search.strip().title()
        
        # Создаем фильтры для всех вариантов регистра
        filters = []
        
        # Поиск в нижнем регистре
        filters.extend([
            Athlete.first_name.like(f"%{search_lower}%"),
            Athlete.last_name.like(f"%{search_lower}%"),
            Athlete.full_name_xml.like(f"%{search_lower}%")
        ])
        
        # Поиск в верхнем регистре
        filters.extend([
            Athlete.first_name.like(f"%{search_upper}%"),
            Athlete.last_name.like(f"%{search_upper}%"),
            Athlete.full_name_xml.like(f"%{search_upper}%")
        ])
        
        # Поиск с заглавной буквы
        filters.extend([
            Athlete.first_name.like(f"%{search_title}%"),
            Athlete.last_name.like(f"%{search_title}%"),
            Athlete.full_name_xml.like(f"%{search_title}%")
        ])
        
        # Поиск в исходном регистре
        filters.extend([
            Athlete.first_name.like(f"%{search}%"),
            Athlete.last_name.like(f"%{search}%"),
            Athlete.full_name_xml.like(f"%{search}%")
        ])
        
        athletes_query = athletes_query.filter(db.or_(*filters))
    
    # Добавляем JOIN с Participant и Category для сортировки по разрядам
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
    if sort_by in ['participations', 'best_place'] or sort_by == 'rank' or rank_filter:
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
        # Сортировка по разрядам через JOIN с категориями
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
    
    # Получаем данные участников для всех спортсменов одним запросом
    athlete_ids = [athlete.id for athlete, club in athletes.items]
    
    # Загружаем все участия для этих спортсменов
    participations_data = db.session.query(
        Participant.athlete_id,
        Participant.total_place,
        Participant.total_points,
        Participant.pct_ppname,
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
                'has_free_participation': False
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
    
    # Находим последнюю категорию для каждого спортсмена
    for athlete_id, stats in athletes_stats.items():
        if stats['participations']:
            # Сортируем по дате и берем последнюю
            # Используем begin_date, если есть, иначе end_date
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
            'has_free_participation': False
        })
        
        athletes_data.append({
            'id': athlete.id,
            'full_name': athlete.full_name or f"{athlete.last_name} {athlete.first_name}",
            'short_name': f"{athlete.last_name} {athlete.first_name[0]}." if athlete.first_name else athlete.last_name,
            'birth_date': athlete.birth_date.strftime('%d.%m.%Y') if athlete.birth_date else None,
            'gender': athlete.gender,
            'gender_display': 'Женский' if athlete.gender == 'F' else 'Мужской' if athlete.gender == 'M' else 'Пара' if athlete.gender == 'P' else '-',
            'category_name': stats['latest_category'],
            'club_name': club.name if club else None,
            'club_id': club.id if club else None,
            'participations_count': len(stats['participations']),
            'best_place': stats['best_place'],
            'best_points': round(stats['best_points'] / 100, 2) if stats['best_points'] else 0,
            'has_free_participation': stats['has_free_participation']
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
    """API для получения деталей категории"""
    category = Category.query.get_or_404(category_id)
    
    # Получаем участников с их результатами
    participants = db.session.query(Participant, Athlete, Club).join(
        Athlete, Participant.athlete_id == Athlete.id
    ).outerjoin(
        Club, Athlete.club_id == Club.id
    ).filter(
        Participant.category_id == category_id
    ).order_by(Participant.total_place.asc().nullslast()).all()
    
    # Получаем сегменты с их результатами
    segments_data = []
    for segment in category.segments:
        segment_participants = db.session.query(Participant, Athlete, Club, Performance).join(
            Athlete, Participant.athlete_id == Athlete.id
        ).outerjoin(
            Club, Athlete.club_id == Club.id
        ).outerjoin(
            Performance, (Performance.participant_id == Participant.id) & (Performance.segment_id == segment.id)
        ).filter(
            Participant.category_id == category_id
        ).order_by(Performance.place.asc().nullslast()).all()
        
        segments_data.append({
            'id': segment.id,
            'name': segment.name,
            'participants': [
                {
                    'place': perf.place if perf else None,
                    'athlete_id': a.id,
                    'athlete_name': a.full_name or f"{a.last_name} {a.first_name}",
                    'club_name': c.name if c else 'Не указан',
                    'points': perf.points if perf else None
                }
                for p, a, c, perf in segment_participants
            ]
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
    """API для получения списка клубов с количеством участников и сортировкой"""
    # Параметры сортировки
    sort_by = request.args.get('sort_by', 'athlete_count')
    sort_order = request.args.get('sort_order', 'desc')
    
    clubs_data = db.session.query(
        Club.id,
        Club.name,
        db.func.count(Athlete.id).label('athlete_count'),
        db.func.count(Participant.id).label('participation_count')
    ).outerjoin(Athlete, Club.id == Athlete.club_id).outerjoin(
        Participant, Athlete.id == Participant.athlete_id
    ).group_by(Club.id, Club.name)
    
    # Сортировка
    if sort_by == 'name':
        order_column = Club.name
    elif sort_by == 'participation_count':
        order_column = db.func.count(Participant.id)
    else:  # athlete_count
        order_column = db.func.count(Athlete.id)
    
    if sort_order == 'asc':
        clubs_data = clubs_data.order_by(order_column.asc())
    else:
        clubs_data = clubs_data.order_by(order_column.desc())
    
    clubs_data = clubs_data.all()
    
    result = []
    for club in clubs_data:
        result.append({
            'id': club.id,
            'name': club.name,
            'athlete_count': club.athlete_count,
            'participation_count': club.participation_count
        })
    
    return jsonify(result)

@api_bp.route('/analytics/free-participation-analysis')
def api_free_participation_analysis():
    """API для анализа бесплатного участия с фильтрацией по количеству участий"""
    try:
        # Получаем параметры фильтрации
        min_participations = request.args.get('min_participations', 1, type=int)
        max_participations = request.args.get('max_participations', 999, type=int)
        season_filter = request.args.get('season', '')
        
        # Базовый запрос для получения спортсменов с бесплатным участием
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
            Event, Participant.event_id == Event.id
        ).join(
            Category, Participant.category_id == Category.id
        ).filter(
            Participant.pct_ppname == 'БЕСП'
        )
        
        # Применяем фильтр по сезону
        if season_filter:
            if season_filter == 'current':
                # Текущий сезон (с июля текущего года)
                current_year = datetime.now().year
                if datetime.now().month >= 7:
                    start_date = datetime(current_year, 7, 1)
                    end_date = datetime(current_year + 1, 6, 30)
                else:
                    start_date = datetime(current_year - 1, 7, 1)
                    end_date = datetime(current_year, 6, 30)
            else:
                # Конкретный сезон (формат: 2024/25)
                try:
                    start_year = int(season_filter.split('/')[0])
                    start_date = datetime(start_year, 7, 1)
                    end_date = datetime(start_year + 1, 6, 30)
                except (ValueError, IndexError):
                    start_date = None
                    end_date = None
            
            if start_date and end_date:
                query = query.filter(
                    Event.begin_date >= start_date,
                    Event.begin_date <= end_date
                )
        
        # Выполняем запрос
        free_participants = query.order_by(
            Event.begin_date.desc(), Athlete.last_name, Athlete.first_name
        ).all()
        
        def get_athlete_name(athlete):
            """Получает имя спортсмена"""
            if athlete['full_name_xml']:
                return athlete['full_name_xml']
            return f"{athlete['last_name']} {athlete['first_name']}"
        
        def get_season_from_date(date_obj):
            """Определяет сезон по дате"""
            if not date_obj:
                return "Неизвестно"
            
            if date_obj.month >= 7:
                start_year = date_obj.year
                end_year = date_obj.year + 1
            else:
                start_year = date_obj.year - 1
                end_year = date_obj.year
            
            return f"{start_year}/{str(end_year)[-2:]}"
        
        # Группируем по спортсменам
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
            
            # Используем normalized_name из БД, а не пересчитываем
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
        
        # Преобразуем seasons в список и сортируем
        for athlete in athletes_data.values():
            athlete['seasons'] = sorted(list(athlete['seasons']))
        
        # Фильтруем по количеству участий
        filtered_athletes = [
            athlete for athlete in athletes_data.values()
            if min_participations <= athlete['free_participations'] <= max_participations
        ]
        
        # Сортируем по количеству бесплатных участий (по убыванию)
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
        logger.error(f"Error in api_free_participation_analysis: {str(e)}")
        return jsonify({'error': str(e)}), 500

