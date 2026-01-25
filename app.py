#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flask веб-приложение для управления турнирами по фигурному катанию
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from functools import wraps
import os
import json
import base64
import logging
import secrets
from collections import defaultdict
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from detailed_parser import ISUCalcFSParser
from season_utils import get_season_from_date, get_all_seasons_from_events
from models import db, Event, Category, Segment, Club, Athlete, Participant, Performance

# Загружаем переменные окружения
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)

# Добавляем функции в контекст Jinja2
@app.template_global()
def format_season(date_obj):
    """Форматирует дату в сезон YYYY/YY"""
    if not date_obj:
        return "Неизвестно"
    
    if date_obj.month >= 7:
        # Сезон начинается в этом году
        start_year = date_obj.year
        end_year = date_obj.year + 1
    else:
        # Сезон начался в прошлом году
        start_year = date_obj.year - 1
        end_year = date_obj.year
    
    return f"{start_year}/{str(end_year)[-2:]}"

@app.template_filter('format_month')
def format_month_filter(month_str):
    """Форматирует месяц из формата YYYY-MM в читаемый вид"""
    if not month_str:
        return ""
    
    months_ru = {
        '01': 'Январь', '02': 'Февраль', '03': 'Март', '04': 'Апрель',
        '05': 'Май', '06': 'Июнь', '07': 'Июль', '08': 'Август',
        '09': 'Сентябрь', '10': 'Октябрь', '11': 'Ноябрь', '12': 'Декабрь'
    }
    
    try:
        year, month = month_str.split('-')
        return f"{months_ru.get(month, month)} {year}"
    except (ValueError, AttributeError):
        return month_str

# Конфигурация из переменных окружения
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///figure_skating.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = int(os.environ.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(seconds=int(os.environ.get('SESSION_TIMEOUT', 3600)))

# Админские данные из переменных окружения
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

# Настройка логирования
log_level = os.environ.get('LOG_LEVEL', 'INFO')
log_file = os.environ.get('LOG_FILE', 'logs/app.log')

# Создаем папку для логов
os.makedirs(os.path.dirname(log_file), exist_ok=True)

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Создаем папку для загрузок
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Настройка rate limiting
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{os.environ.get('RATE_LIMIT_PER_MINUTE', 60)} per minute"]
)
limiter.init_app(app)

# Декоратор для проверки авторизации администратора
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Проверяем, является ли запрос AJAX (JSON запрос)
        is_ajax = request.is_json or request.headers.get('Content-Type', '').startswith('application/json') or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        if not session.get('admin_logged_in'):
            logger.warning(f"Unauthorized access attempt to {request.endpoint} from {request.remote_addr}")
            flash('Необходима авторизация администратора', 'error')
            
            # Для AJAX запросов возвращаем JSON
            if is_ajax:
                return jsonify({
                    'success': False,
                    'message': 'Необходима авторизация администратора',
                    'redirect': url_for('admin_login')
                }), 401
            
            return redirect(url_for('admin_login'))
        
        # Проверяем время сессии
        if 'last_activity' in session:
            last_activity = datetime.fromisoformat(session['last_activity'])
            if datetime.now() - last_activity > timedelta(seconds=app.config['PERMANENT_SESSION_LIFETIME'].total_seconds()):
                session.clear()
                logger.info(f"Session expired for admin from {request.remote_addr}")
                flash('Сессия истекла. Войдите заново.', 'warning')
                
                # Для AJAX запросов возвращаем JSON
                if is_ajax:
                    return jsonify({
                        'success': False,
                        'message': 'Сессия истекла. Войдите заново.',
                        'redirect': url_for('admin_login')
                    }), 401
                
                return redirect(url_for('admin_login'))
        
        # Обновляем время последней активности
        session['last_activity'] = datetime.now().isoformat()
        return f(*args, **kwargs)
    return decorated_function

migrate = Migrate(app, db)
CORS(app)

# Инициализация базы данных
db.init_app(app)

# Обработчики ошибок
@app.errorhandler(404)
def not_found_error(error):
    logger.warning(f"404 error: {request.url} from {request.remote_addr}")
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"500 error: {error} from {request.remote_addr}")
    db.session.rollback()
    return render_template('500.html'), 500

@app.errorhandler(413)
def too_large(error):
    logger.warning(f"File too large from {request.remote_addr}")
    flash('Файл слишком большой. Максимальный размер: 16MB', 'error')
    return redirect(url_for('upload_file'))

# Маршруты
@app.route('/')
def index():
    """Главная страница"""
    events = Event.query.order_by(Event.begin_date.desc()).limit(10).all()
    return render_template('index.html', events=events)

@app.route('/upload', methods=['GET', 'POST'])
@admin_required
@limiter.limit("5 per minute")
def upload_file():
    """Загрузка и парсинг XML файла"""
    if request.method == 'POST':
        logger.info(f"File upload attempt from {request.remote_addr}")
        
        if 'file' not in request.files:
            logger.warning(f"No file in request from {request.remote_addr}")
            return jsonify({'error': 'Файл не выбран'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'Файл не выбран'}), 400
        
        # Проверяем расширение файла (поддерживаем .xml и .XML)
        if not file.filename.lower().endswith('.xml'):
            return jsonify({'error': f'Неверный формат файла. Ожидается .xml, получен: {file.filename}'}), 400
        
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        try:
            file.save(filepath)
            
            # Проверяем, что файл действительно XML
            try:
                import xml.etree.ElementTree as ET
                ET.parse(filepath)
            except ET.ParseError as e:
                os.remove(filepath)
                return jsonify({'error': f'Файл не является корректным XML: {str(e)}'}), 400
            
            # Сохраняем файл для последующей нормализации
            session['uploaded_file'] = {
                'filepath': filepath,
                'filename': filename
            }
            
            return jsonify({
                'success': True,
                'message': 'Файл загружен. Используйте кнопку "Обработать XML" для анализа и нормализации категорий.',
                'requires_normalization': True
            })
            
        except ValueError as e:
            # Ошибка дублирования турнира
            if os.path.exists(filepath):
                os.remove(filepath)
            return jsonify({'error': str(e)}), 400
            
        except Exception as e:
            # Удаляем временный файл в случае ошибки
            if os.path.exists(filepath):
                os.remove(filepath)
            return jsonify({'error': f'Ошибка обработки файла: {str(e)}'}), 500
    
    return render_template('upload.html')

@app.route('/analyze-xml', methods=['POST'])
@admin_required
@limiter.limit("10 per minute")
def analyze_xml():
    """Анализ XML файла без сохранения в базу"""
    if 'file' not in request.files:
        return jsonify({'error': 'Файл не выбран'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Файл не выбран'}), 400
    
    if not file.filename.lower().endswith('.xml'):
        return jsonify({'error': f'Неверный формат файла. Ожидается .xml, получен: {file.filename}'}), 400
    
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    try:
        file.save(filepath)
        
        # Проверяем, что файл действительно XML
        try:
            import xml.etree.ElementTree as ET
            ET.parse(filepath)
        except ET.ParseError as e:
            os.remove(filepath)
            return jsonify({'error': f'Файл не является корректным XML: {str(e)}'}), 400
        
        # Парсим XML файл
        parser = ISUCalcFSParser(filepath)
        parser.parse()
        
        # Анализируем категории
        categories_analysis = analyze_categories_from_xml(parser)
        
        # Сохраняем данные парсера в сессии для последующей загрузки
        session['parser_data'] = {
            'filepath': filepath,
            'categories_analysis': categories_analysis,
            'parser_summary': {
                'events': len(parser.events),
                'categories': len(parser.categories),
                'segments': len(parser.segments),
                'persons': len(parser.persons),
                'clubs': len(parser.clubs),
                'participants': len(parser.participants),
                'performances': len(parser.performances)
            }
        }
        
        return jsonify({
            'success': True,
            'categories_analysis': categories_analysis,
            'parser_summary': session['parser_data']['parser_summary'],
            'message': f'Файл проанализирован. Найдено {len(categories_analysis)} категорий'
        })
        
    except Exception as e:
        logger.error(f"Ошибка анализа файла: {str(e)}")
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({'error': f'Ошибка анализа файла: {str(e)}'}), 500

@app.route('/normalize-categories', methods=['GET', 'POST'])
@admin_required
def normalize_categories():
    """Страница для ручной нормализации категорий"""
    if 'parser_data' not in session:
        flash('Нет данных для нормализации', 'error')
        return redirect(url_for('upload_file'))
    
    parser_data = session['parser_data']
    categories_analysis = parser_data['categories_analysis']
    
    if request.method == 'POST':
        # Получаем нормализации от пользователя
        normalizations = {}
        for key, value in request.form.items():
            if key.startswith('normalize_'):
                category_index = int(key.replace('normalize_', ''))
                normalizations[category_index] = value
        
        # Применяем нормализации
        for index, normalized_name in normalizations.items():
            if index < len(categories_analysis):
                categories_analysis[index]['normalized'] = normalized_name
                categories_analysis[index]['needs_manual'] = False
        
        # Сохраняем обновленные данные
        session['parser_data']['categories_analysis'] = categories_analysis
        
        # Загружаем парсер и сохраняем в базу
        try:
            parser = ISUCalcFSParser(parser_data['filepath'])
            parser.parse()
            
            # Применяем нормализации к парсеру
            for i, category in enumerate(parser.categories):
                if i < len(categories_analysis):
                    category['normalized_name'] = categories_analysis[i]['normalized']
            
            save_to_database(parser)
            
            # Удаляем временный файл и очищаем сессию
            os.remove(parser_data['filepath'])
            session.pop('parser_data', None)
            
            flash('Файл успешно загружен и обработан с нормализацией категорий!', 'success')
            return redirect(url_for('index'))
            
        except Exception as e:
            logger.error(f"Ошибка при сохранении нормализованных данных: {str(e)}")
            flash(f'Ошибка при сохранении данных: {str(e)}', 'error')
    
    # Получаем список всех возможных нормализованных названий (только с полом)
    all_ranks = []
    for rank_data in RANK_DICTIONARY.values():
        for gender, name in rank_data['genders'].items():
            all_ranks.append(name)
    
    return render_template('normalize_categories.html', 
                         categories_analysis=categories_analysis,
                         all_ranks=sorted(set(all_ranks)),
                         parser_summary=parser_data['parser_summary'])

@app.route('/upload-to-database', methods=['POST'])
@admin_required
def upload_to_database():
    """Финальная загрузка данных в базу после нормализации"""
    if 'parser_data' not in session:
        return jsonify({'error': 'Нет данных для загрузки'}), 400
    
    parser_data = session['parser_data']
    
    try:
        # Загружаем парсер
        parser = ISUCalcFSParser(parser_data['filepath'])
        parser.parse()
        
        # Применяем нормализации к парсеру
        categories_analysis = parser_data['categories_analysis']
        for i, category in enumerate(parser.categories):
            if i < len(categories_analysis):
                category['normalized_name'] = categories_analysis[i]['normalized']
        
        # Сохраняем в базу
        save_to_database(parser)
        
        # Удаляем временный файл и очищаем сессию
        os.remove(parser_data['filepath'])
        session.pop('parser_data', None)
        
        return jsonify({
            'success': True,
            'message': f'Файл успешно загружен в базу данных! Добавлено {len(parser.get_athletes_with_results())} спортсменов.'
        })
        
    except Exception as e:
        logger.error(f"Ошибка при загрузке в базу: {str(e)}")
        return jsonify({'error': f'Ошибка при загрузке в базу: {str(e)}'}), 500

@app.route('/athletes')
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

@app.route('/athlete/<int:athlete_id>')
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

@app.route('/api/athlete/<int:athlete_id>/results-chart')
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

@app.route('/events')
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
        events = query.order_by(Event.name.asc()).all()
    elif sort_by == 'date':
        events = query.order_by(Event.begin_date.desc()).all()
    elif sort_by == 'rank':
        # Сортируем по разряду (используем вес разряда)
        events = query.join(Category, Event.id == Category.event_id).order_by(
            Category.normalized_name.asc()
        ).distinct().all()
    else:
        events = query.order_by(Event.name.asc()).all()
    
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
                         seasons=seasons,
                         current_sort=sort_by,
                         current_rank_filter=rank_filter,
                         current_month_filter=month_filter,
                         available_ranks=available_ranks,
                         available_months=available_months,
                         total_participants=total_participants)

@app.route('/categories')
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

@app.route('/best_results')
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

@app.route('/event/<int:event_id>')
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

@app.route('/api/events', methods=['GET'])
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
    
    return jsonify({
        'total': len(events_payload),
        'events': events_payload
    })


@app.route('/api/event/<int:event_id>/export')
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
    from flask import Response
    response = Response(
        csv_content,
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename=results_{event.name.replace(" ", "_")}_{event.begin_date.strftime("%Y%m%d") if event.begin_date else "unknown"}.csv'
        }
    )
    
    return response

@app.route('/analytics')
def analytics():
    """Страница аналитики"""
    return render_template('analytics.html')

@app.route('/free-participation')
def free_participation():
    """Страница спортсменов с бесплатным участием"""
    return render_template('free_participation.html')

@app.route('/club-free-analysis')
def club_free_analysis():
    """Страница анализа бесплатного участия по школам"""
    return render_template('club_free_analysis.html')

@app.route('/api/statistics')
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

def get_rank_weight(rank_name):
    """Возвращает вес разряда для ранжирования (меньше = лучше)"""
    # Базовые веса разрядов (без учета пола)
    base_weights = {
        'МС': 1,
        'КМС': 2,
        '1 Спортивный': 3,
        '2 Спортивный': 4,
        '3 Спортивный': 5,
        '1 Юношеский': 6,
        '2 Юношеский': 7,
        '3 Юношеский': 8,
        'Юный Фигурист': 9,
        'Дебют': 10,
        'Новичок': 11,
        'Другой': 12
    }
    
    # Убираем пол из названия для определения базового веса
    base_rank = rank_name.split(',')[0].strip()
    return base_weights.get(base_rank, 12)

@app.route('/api/analytics/top-athletes')
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

@app.route('/api/analytics/club-statistics')
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

# Полный словарь разрядов
RANK_DICTIONARY = {
    # Мастерские разряды
    'мс': {
        'name': 'МС',
        'genders': {
            'F': 'МС, Женщины',
            'M': 'МС, Мужчины'
        },
        'keywords': ['мс', 'мастер спорта', 'мастер спорта россии']
    },
    'кмс': {
        'name': 'КМС', 
        'genders': {
            'F': 'КМС, Девушки',
            'M': 'КМС, Юноши'
        },
        'keywords': ['кмс', 'кандидат в мастера спорта', 'кандидат в мастера спорта россии', 'кандидат в мастера', 'кандидат мастера спорта', 'кандидат в мастера спорта, юниоры', 'кандидат в мастера спорта, юниорки']
    },
    
    # Спортивные разряды
    '1 спортивный': {
        'name': '1 Спортивный',
        'genders': {
            'F': '1 Спортивный, Девочки',
            'M': '1 Спортивный, Мальчики'
        },
        'keywords': ['1 спортивный', 'первый спортивный', '1 спорт', '1 спортивный разряд', 'первый спортивный разряд']
    },
    '2 спортивный': {
        'name': '2 Спортивный',
        'genders': {
            'F': '2 Спортивный, Девочки', 
            'M': '2 Спортивный, Мальчики'
        },
        'keywords': ['2 спортивный', 'второй спортивный', '2 спорт', '2 спортивный разряд', 'второй спортивный разряд']
    },
    '3 спортивный': {
        'name': '3 Спортивный',
        'genders': {
            'F': '3 Спортивный, Девочки',
            'M': '3 Спортивный, Мальчики'
        },
        'keywords': ['3 спортивный', 'третий спортивный', '3 спорт', '3 спортивный разряд', 'третий спортивный разряд']
    },
    
    # Юношеские разряды
    '1 юношеский': {
        'name': '1 Юношеский',
        'genders': {
            'F': '1 Юношеский, Девочки',
            'M': '1 Юношеский, Мальчики'
        },
        'keywords': ['1 юношеский', 'первый юношеский', '1 юн']
    },
    '2 юношеский': {
        'name': '2 Юношеский',
        'genders': {
            'F': '2 Юношеский, Девочки',
            'M': '2 Юношеский, Мальчики'
        },
        'keywords': ['2 юношеский', 'второй юношеский', '2 юн']
    },
    '3 юношеский': {
        'name': '3 Юношеский',
        'genders': {
            'F': '3 Юношеский, Девочки',
            'M': '3 Юношеский, Мальчики'
        },
        'keywords': ['3 юношеский', 'третий юношеский', '3 юн']
    },
    
    # Начальные разряды
    'юный фигурист': {
        'name': 'Юный Фигурист',
        'genders': {
            'F': 'Юный Фигурист, Девочки',
            'M': 'Юный Фигурист, Мальчики'
        },
        'keywords': ['юный фигурист', 'юный', 'юф']
    },
    'дебют': {
        'name': 'Дебют',
        'genders': {
            'F': 'Дебют, Девочки',
            'M': 'Дебют, Мальчики'
        },
        'keywords': ['дебют', 'дебютный']
    },
    'новичок': {
        'name': 'Новичок',
        'genders': {
            'F': 'Новичок, Девочки',
            'M': 'Новичок, Мальчики'
        },
        'keywords': ['новичок', 'начинающий']
    },
    
    # Специальные разряды для парного катания и танцев
    'пары_1 спортивный': {
        'name': '1 Спортивный, Пары',
        'genders': {
            'F': '1 Спортивный, Пары',
            'M': '1 Спортивный, Пары'
        },
        'keywords': ['парное катание, 1 спортивный', 'пары, 1 спортивный', 'парное, 1 спортивный', 'парное катание, 1 спортивный разряд']
    },
    'пары_2 спортивный': {
        'name': '2 Спортивный, Пары',
        'genders': {
            'F': '2 Спортивный, Пары',
            'M': '2 Спортивный, Пары'
        },
        'keywords': ['парное катание, 2 спортивный', 'пары, 2 спортивный', 'парное, 2 спортивный']
    },
    'пары_3 спортивный': {
        'name': '3 Спортивный, Пары',
        'genders': {
            'F': '3 Спортивный, Пары',
            'M': '3 Спортивный, Пары'
        },
        'keywords': ['парное катание, 3 спортивный', 'пары, 3 спортивный', 'парное, 3 спортивный']
    },
    'пары_кмс': {
        'name': 'КМС, Пары',
        'genders': {
            'F': 'КМС, Пары',
            'M': 'КМС, Пары'
        },
        'keywords': ['парное катание, кандидат в мастера спорта', 'пары, кандидат в мастера спорта', 'парное, кандидат в мастера спорта', 'парное катание, кмс', 'пары, кмс', 'парное катание, кандидат в мастера спорта']
    },
    'пары_мс': {
        'name': 'МС, Пары',
        'genders': {
            'F': 'МС, Пары',
            'M': 'МС, Пары'
        },
        'keywords': ['парное катание, мастер спорта', 'пары, мастер спорта', 'парное, мастер спорта', 'парное катание, мс', 'пары, мс']
    },
    
    'танцы_1 спортивный': {
        'name': '1 Спортивный, Танцы',
        'genders': {
            'F': '1 Спортивный, Танцы',
            'M': '1 Спортивный, Танцы'
        },
        'keywords': ['танцы на льду, 1 спортивный', 'танцы, 1 спортивный', 'ледяные танцы, 1 спортивный', 'танцы на льду, 1 спортивный разряд']
    },
    'танцы_2 спортивный': {
        'name': '2 Спортивный, Танцы',
        'genders': {
            'F': '2 Спортивный, Танцы',
            'M': '2 Спортивный, Танцы'
        },
        'keywords': ['танцы на льду, 2 спортивный', 'танцы, 2 спортивный', 'ледяные танцы, 2 спортивный']
    },
    'танцы_3 спортивный': {
        'name': '3 Спортивный, Танцы',
        'genders': {
            'F': '3 Спортивный, Танцы',
            'M': '3 Спортивный, Танцы'
        },
        'keywords': ['танцы на льду, 3 спортивный', 'танцы, 3 спортивный', 'ледяные танцы, 3 спортивный']
    },
    'танцы_кмс': {
        'name': 'КМС, Танцы',
        'genders': {
            'F': 'КМС, Танцы',
            'M': 'КМС, Танцы'
        },
        'keywords': ['танцы на льду, кандидат в мастера спорта', 'танцы, кандидат в мастера спорта', 'ледяные танцы, кандидат в мастера спорта', 'танцы на льду, кмс', 'танцы, кмс', 'танцы на льду, кандидат в мастера спорта']
    },
    'танцы_мс': {
        'name': 'МС, Танцы',
        'genders': {
            'F': 'МС, Танцы',
            'M': 'МС, Танцы'
        },
        'keywords': ['танцы на льду, мастер спорта', 'танцы, мастер спорта', 'ледяные танцы, мастер спорта', 'танцы на льду, мс', 'танцы, мс']
    }
}


GENDER_LABELS = {
    'F': 'Женский',
    'M': 'Мужской',
    'X': 'Смешанный',
    'U': 'Не указан'
}


def _create_rank_entry(display_name, gender_code='U', base_name=None):
    """Создает заготовку для отображения разряда"""
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
    """Возвращает словарь всех разрядов из словаря с базовой информацией"""
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

def normalize_category_name(category_name, gender=None):
    """Нормализует название категории для группировки по разрядам с учетом пола"""
    if not category_name:
        return "Неизвестно"
    
    name_lower = category_name.lower()
    
    # Исправляем известные опечатки (латинские символы на кириллические)
    name_lower = name_lower.replace('девочки', 'девочки')  # исправляем "девочки" -> "девочки" (латинская o -> кириллическая о)
    name_lower = name_lower.replace('спортивный', 'спортивный')  # исправляем "спортивный" -> "спортивный" (латинская c -> кириллическая с)
    
    # Ищем совпадения в словаре разрядов
    for rank_key, rank_data in RANK_DICTIONARY.items():
        for keyword in rank_data['keywords']:
            if keyword in name_lower:
                # Определяем пол
                if gender and gender.upper() in rank_data['genders']:
                    return rank_data['genders'][gender.upper()]
                else:
                    # Если пол не указан, возвращаем базовое название
                    return rank_data['name']
    
    # Если не найдено совпадений
    gender_suffix = ""
    if gender:
        if gender.upper() == 'F':
            gender_suffix = ", Девочки"
        elif gender.upper() == 'M':
            gender_suffix = ", Мальчики"
    
    return f"Другой{gender_suffix}"

@app.route('/api/analytics/category-statistics')
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

@app.route('/api/analytics/free-participation')
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

@app.route('/api/analytics/club-free-participation')
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

@app.route('/api/athletes')
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

@app.route('/api/category/<int:category_id>')
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

def save_to_database(parser):
    """Сохраняет данные из парсера в базу данных"""
    
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
    
    db.session.commit()

def parse_date(date_str):
    """Парсит дату из строки формата YYYYMMDD или возвращает объект date"""
    if not date_str:
        return None
    
    # Если это уже объект date, возвращаем его
    if hasattr(date_str, 'year') and hasattr(date_str, 'month') and hasattr(date_str, 'day'):
        return date_str
    
    # Если это строка, парсим её
    if isinstance(date_str, str):
        if len(date_str) != 8:
            return None
        try:
            return datetime.strptime(date_str, '%Y%m%d').date()
        except ValueError:
            return None
    
    return None

def parse_time(time_str):
    """Парсит время из строки формата HH:MM:SS"""
    if not time_str:
        return None
    try:
        return datetime.strptime(time_str, '%H:%M:%S').time()
    except ValueError:
        return None

def parse_datetime(datetime_str):
    """Парсит дату и время из строки"""
    if not datetime_str:
        return None
    try:
        # Пробуем разные форматы
        for fmt in ['%Y%m%d%H%M%S', '%Y-%m-%d %H:%M:%S', '%Y%m%d']:
            try:
                return datetime.strptime(datetime_str, fmt)
            except ValueError:
                continue
        return None
    except ValueError:
        return None

@app.route('/clubs')
def clubs():
    """Страница со списком всех клубов/школ"""
    return render_template('clubs.html')

@app.route('/api/clubs')
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

@app.route('/club/<int:club_id>')
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

# ==================== АДМИНСКИЕ МАРШРУТЫ ====================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Страница входа для администратора"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            flash('Успешный вход в систему', 'success')
            return redirect(url_for('index'))
        else:
            flash('Неверное имя пользователя или пароль', 'error')
    
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    """Выход из системы"""
    session.pop('admin_logged_in', None)
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('index'))

@app.route('/free-participation-analysis')
def free_participation_analysis():
    """Страница анализа бесплатного участия с фильтрацией"""
    return render_template('free_participation_analysis.html')

@app.route('/api/analytics/free-participation-analysis')
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

@app.route('/admin/export-google-sheets', methods=['GET', 'POST'])
@admin_required
def admin_export_google_sheets():
    """Страница экспорта в Google Sheets"""
    import os
    from google_sheets_sync import export_to_google_sheets, DEFAULT_SPREADSHEET_ID
    
    # Проверяем наличие credentials
    credentials_path = os.path.join(os.path.dirname(__file__), 'google_credentials.json')
    credentials_exists = os.path.exists(credentials_path)
    
    if request.method == 'POST':
        try:
            # Выполняем экспорт (ID таблицы вшит в код)
            result = export_to_google_sheets(DEFAULT_SPREADSHEET_ID)
            
            if result['success']:
                return jsonify({
                    'success': True,
                    'message': result['message'],
                    'url': result['url']
                })
            else:
                return jsonify({
                    'success': False,
                    'message': result.get('error', 'Неизвестная ошибка')
                }), 500
        except Exception as e:
            logger.error(f"Ошибка экспорта в Google Sheets: {e}")
            return jsonify({
                'success': False,
                'message': f'Ошибка: {str(e)}'
            }), 500
    
    # GET запрос - показываем страницу
    return render_template('admin_export_google_sheets.html',
                         credentials_exists=credentials_exists,
                         spreadsheet_id=DEFAULT_SPREADSHEET_ID)

@app.route('/admin/free-participation', methods=['GET', 'POST'])
@admin_required
def admin_free_participation():
    """Управление бесплатным участием спортсменов"""
    if request.method == 'POST':
        action = request.form.get('action')
        event_id = request.form.get('event_id')
        
        if action == 'set_free':
            # Устанавливаем бесплатное участие для всех участников события
            participants = Participant.query.filter_by(event_id=event_id).all()
            updated_count = 0
            
            for participant in participants:
                if participant.pct_ppname != 'БЕСП':
                    participant.pct_ppname = 'БЕСП'
                    updated_count += 1
            
            try:
                db.session.commit()
                event = Event.query.get(event_id)
                flash(f'Успешно установлено бесплатное участие для {updated_count} спортсменов в турнире "{event.name}"', 'success')
                logger.info(f'Admin set free participation for {updated_count} participants in event {event_id}')
            except Exception as e:
                db.session.rollback()
                flash(f'Ошибка при обновлении данных: {str(e)}', 'error')
                logger.error(f'Error setting free participation: {str(e)}')
                
        elif action == 'remove_free':
            # Убираем бесплатное участие для всех участников события
            participants = Participant.query.filter_by(event_id=event_id, pct_ppname='БЕСП').all()
            updated_count = 0
            
            for participant in participants:
                participant.pct_ppname = None
                updated_count += 1
            
            try:
                db.session.commit()
                event = Event.query.get(event_id)
                flash(f'Успешно убрано бесплатное участие для {updated_count} спортсменов в турнире "{event.name}"', 'success')
                logger.info(f'Admin removed free participation for {updated_count} participants in event {event_id}')
            except Exception as e:
                db.session.rollback()
                flash(f'Ошибка при обновлении данных: {str(e)}', 'error')
                logger.error(f'Error removing free participation: {str(e)}')
        
        return redirect(url_for('admin_free_participation'))
    
    # GET запрос - показываем форму
    events = Event.query.order_by(Event.begin_date.desc()).all()
    
    # Добавляем статистику для каждого события
    events_data = []
    for event in events:
        total_participants = Participant.query.filter_by(event_id=event.id).count()
        free_participants = Participant.query.filter_by(event_id=event.id, pct_ppname='БЕСП').count()
        
        events_data.append({
            'event': event,
            'total_participants': total_participants,
            'free_participants': free_participants,
            'paid_participants': total_participants - free_participants
        })
    
    return render_template('admin_free_participation.html', events_data=events_data)

# Определение всех доступных скриптов
SCRIPT_DEFINITIONS = {
    # Скрипты проверки
    'check_duplicates_smart': {
        'name': 'Проверка дубликатов спортсменов (умный поиск)',
        'description': 'Находит спортсменов с одинаковой датой рождения и фамилией',
        'category': 'check',
        'requires_confirmation': False
    },
    'check_participants_zero_points': {
        'name': 'Проверка участников с нулевыми баллами',
        'description': 'Находит участников с NULL или нулевыми баллами',
        'category': 'check',
        'requires_confirmation': False
    },
    'check_clubs_zero_athletes': {
        'name': 'Проверка клубов без спортсменов',
        'description': 'Находит клубы, у которых нет ни одного спортсмена',
        'category': 'check',
        'requires_confirmation': False
    },
    'check_missing_clubs': {
        'name': 'Проверка отсутствующих клубов',
        'description': 'Находит спортсменов, у которых указан несуществующий клуб',
        'category': 'check',
        'requires_confirmation': False
    },
    'check_athletes_without_starts': {
        'name': 'Проверка спортсменов без стартов',
        'description': 'Находит спортсменов, которые никогда не участвовали в турнирах',
        'category': 'check',
        'requires_confirmation': False
    },
    'check_similar_club_names': {
        'name': 'Проверка схожих названий клубов',
        'description': 'Находит клубы с похожими названиями, которые могут быть дубликатами',
        'category': 'check',
        'requires_confirmation': False
    },
    'check_remaining_pairs': {
        'name': 'Проверка дубликатов пар',
        'description': 'Находит дубликаты парных спортсменов',
        'category': 'check',
        'requires_confirmation': False
    },
    'check_mafkk_schools': {
        'name': 'Проверка школ МАФКК',
        'description': 'Проверяет наличие и объединение школ МАФКК',
        'category': 'check',
        'requires_confirmation': False
    },
    'check_pair_results': {
        'name': 'Проверка результатов пар',
        'description': 'Проверяет результаты парных выступлений',
        'category': 'check',
        'requires_confirmation': False
    },
    # Скрипты удаления
    'delete_clubs_zero_athletes': {
        'name': 'Удаление клубов без спортсменов',
        'description': 'Безопасно удаляет клубы где 0 спортсменов',
        'category': 'delete',
        'requires_confirmation': True,
        'creates_backup': True
    },
    'delete_participants_null_points': {
        'name': 'Удаление участий с NULL баллами',
        'description': 'Удаляет участия спортсменов с NULL баллами (снятые с турнира)',
        'category': 'delete',
        'requires_confirmation': True,
        'creates_backup': True
    },
    # Скрипты объединения
    'merge_two_athletes': {
        'name': 'Объединение двух спортсменов',
        'description': 'Принудительное объединение двух спортсменов по ID',
        'category': 'merge',
        'requires_confirmation': True,
        'creates_backup': True,
        'requires_params': ['keep_athlete_id', 'remove_athlete_id']
    },
    'merge_two_clubs': {
        'name': 'Объединение двух клубов',
        'description': 'Принудительное объединение двух клубов по ID',
        'category': 'merge',
        'requires_confirmation': True,
        'creates_backup': True,
        'requires_params': ['keep_club_id', 'remove_club_id']
    },
    'merge_similar_clubs': {
        'name': 'Объединение схожих клубов',
        'description': 'Интерактивное объединение клубов со схожими названиями',
        'category': 'merge',
        'requires_confirmation': True,
        'creates_backup': True
    },
    'merge_only_true_duplicates': {
        'name': 'Объединение только истинных дубликатов',
        'description': 'Объединяет только точно совпадающих спортсменов',
        'category': 'merge',
        'requires_confirmation': True,
        'creates_backup': True
    },
    'merge_pairs_duplicates': {
        'name': 'Объединение дубликатов пар',
        'description': 'Объединяет дубликаты парных спортсменов',
        'category': 'merge',
        'requires_confirmation': True,
        'creates_backup': True
    },
    # Скрипты обновления
    'update_pairs_gender': {
        'name': 'Обновление пола пар',
        'description': 'Обновляет пол для парных выступлений',
        'category': 'update',
        'requires_confirmation': True,
        'creates_backup': True
    },
    'unify_mafkk_schools': {
        'name': 'Унификация школ МАФКК',
        'description': 'Унифицирует названия школ МАФКК',
        'category': 'update',
        'requires_confirmation': True,
        'creates_backup': True
    },
    'assign_default_club': {
        'name': 'Назначение клуба по умолчанию',
        'description': 'Назначает клуб по умолчанию спортсменам без клуба',
        'category': 'update',
        'requires_confirmation': True,
        'creates_backup': True
    },
    # Скрипты импорта/экспорта
    'reimport_event_from_xml': {
        'name': 'Переимпорт турнира из XML',
        'description': 'Переимпортирует турнир из XML файла',
        'category': 'import',
        'requires_confirmation': True,
        'creates_backup': True,
        'requires_params': ['event_name']
    },
    'backup_database': {
        'name': 'Создание резервной копии БД',
        'description': 'Создает резервную копию базы данных',
        'category': 'backup',
        'requires_confirmation': False,
        'creates_backup': False
    },
    # Скрипты списков
    'list_duplicates_smart': {
        'name': 'Список дубликатов (умный поиск)',
        'description': 'Выводит список найденных дубликатов спортсменов',
        'category': 'list',
        'requires_confirmation': False
    },
    'show_duplicates': {
        'name': 'Показать дубликаты',
        'description': 'Показывает найденные дубликаты',
        'category': 'list',
        'requires_confirmation': False
    }
}

@app.route('/admin/tools', methods=['GET', 'POST'])
@admin_required
def admin_tools():
    """Админская панель с инструментами для работы с БД"""
    if request.method == 'POST':
        action = request.form.get('action')
        
        # Обработка запуска скрипта
        if action == 'run_script':
            script_name = request.form.get('script_name')
            if script_name and script_name in SCRIPT_DEFINITIONS:
                script_def = SCRIPT_DEFINITIONS[script_name]
                
                # Проверка подтверждения для опасных операций
                if script_def.get('requires_confirmation'):
                    confirmed = request.form.get('confirmed', 'false') == 'true'
                    if not confirmed:
                        flash('Требуется подтверждение для выполнения этого скрипта', 'warning')
                        return redirect(url_for('admin_tools'))
                
                # Проверка параметров
                if script_def.get('requires_params'):
                    params = {}
                    for param_name in script_def['requires_params']:
                        param_value = request.form.get(param_name)
                        if not param_value:
                            flash(f'Не указан обязательный параметр: {param_name}', 'error')
                            return redirect(url_for('admin_tools'))
                        params[param_name] = param_value
                    return run_script_with_params(script_name, params)
                else:
                    return run_check_script(script_name)
            else:
                flash('Неизвестный скрипт', 'error')
        
        # Старые действия для обратной совместимости
        elif action == 'check_duplicates':
            return run_check_script('check_duplicates_smart')
        elif action == 'check_zero_points':
            return run_check_script('check_participants_zero_points')
        elif action == 'check_zero_athletes':
            return run_check_script('check_clubs_zero_athletes')
        elif action == 'check_missing_clubs':
            return run_check_script('check_missing_clubs')
        elif action == 'check_athletes_without_starts':
            return run_check_script('check_athletes_without_starts')
        elif action == 'check_similar_clubs':
            return run_check_script('check_similar_club_names')
        elif action == 'check_remaining_pairs':
            return run_check_script('check_remaining_pairs')
        elif action == 'check_mafkk_schools':
            return run_check_script('check_mafkk_schools')
        elif action == 'delete_event':
            event_id = request.form.get('event_id', type=int)
            if event_id:
                return delete_event_completely(event_id)
            else:
                flash('Не указан ID турнира', 'error')
        elif action == 'delete_participant':
            participant_id = request.form.get('participant_id', type=int)
            if participant_id:
                return delete_participant_completely(participant_id)
            else:
                flash('Не указан ID участия', 'error')
        elif action == 'delete_athlete':
            athlete_id = request.form.get('athlete_id', type=int)
            if athlete_id:
                return delete_athlete_completely(athlete_id)
            else:
                flash('Не указан ID спортсмена', 'error')
        elif action == 'clear_script_output':
            script_name = request.form.get('script_name')
            if script_name:
                # Удаляем из сессии
                output_file = session.pop(f'script_output_file_{script_name}', None)
                session.pop(f'script_output_time_{script_name}', None)
                session.pop(f'script_output_{script_name}', None)
                # Опционально удаляем файл
                if output_file and os.path.exists(output_file):
                    try:
                        os.remove(output_file)
                    except Exception as e:
                        logger.warning(f'Could not delete script output file: {str(e)}')
                flash('Результаты скрипта очищены', 'info')
            return redirect(url_for('admin_tools'))
        elif action == 'get_script_output':
            # API endpoint для получения вывода скрипта
            script_name = request.args.get('script_name')
            if script_name:
                output_file = session.get(f'script_output_file_{script_name}')
                if output_file and os.path.exists(output_file):
                    try:
                        with open(output_file, 'r', encoding='utf-8') as f:
                            content = f.read()
                        return jsonify({'success': True, 'output': content})
                    except Exception as e:
                        return jsonify({'success': False, 'error': str(e)})
                else:
                    # Пробуем получить из сессии (для старых результатов)
                    output = session.get(f'script_output_{script_name}')
                    if output:
                        return jsonify({'success': True, 'output': output})
            return jsonify({'success': False, 'error': 'Output not found'})
    
    # GET запрос - показываем страницу
    events = Event.query.order_by(Event.begin_date.desc()).limit(50).all()
    
    # Если есть параметры поиска участий
    search_athlete = request.args.get('search_athlete', '')
    search_event = request.args.get('search_event', type=int)
    participants = []
    
    # Поиск спортсменов без участий
    search_athlete_no_starts = request.args.get('search_athlete_no_starts', '')
    athletes_no_starts = []
    
    if search_athlete_no_starts:
        query = db.session.query(Athlete).outerjoin(
            Participant, Athlete.id == Participant.athlete_id
        ).filter(
            Participant.id.is_(None)
        )
        
        if search_athlete_no_starts:
            query = query.filter(
                db.or_(
                    Athlete.last_name.ilike(f'%{search_athlete_no_starts}%'),
                    Athlete.first_name.ilike(f'%{search_athlete_no_starts}%'),
                    Athlete.full_name_xml.ilike(f'%{search_athlete_no_starts}%')
                )
            )
        
        athletes_no_starts = query.order_by(Athlete.last_name).limit(20).all()
    
    if search_athlete or search_event:
        query = db.session.query(Participant, Athlete, Event, Category).join(
            Athlete, Participant.athlete_id == Athlete.id
        ).join(
            Event, Participant.event_id == Event.id
        ).join(
            Category, Participant.category_id == Category.id
        )
        
        if search_athlete:
            query = query.filter(
                db.or_(
                    Athlete.last_name.ilike(f'%{search_athlete}%'),
                    Athlete.first_name.ilike(f'%{search_athlete}%'),
                    Athlete.full_name_xml.ilike(f'%{search_athlete}%')
                )
            )
        
        if search_event:
            query = query.filter(Participant.event_id == search_event)
        
        participants = query.order_by(Event.begin_date.desc(), Athlete.last_name).limit(20).all()
    
    # Группируем скрипты по категориям
    scripts_by_category = {}
    for script_name, script_def in SCRIPT_DEFINITIONS.items():
        category = script_def.get('category', 'other')
        if category not in scripts_by_category:
            scripts_by_category[category] = []
        scripts_by_category[category].append({
            'name': script_name,
            'definition': script_def
        })
    
    return render_template('admin_tools.html', 
                          events=events, 
                          participants=participants, 
                          search_athlete=search_athlete, 
                          search_event=search_event,
                          athletes_no_starts=athletes_no_starts, 
                          search_athlete_no_starts=search_athlete_no_starts,
                          scripts_by_category=scripts_by_category,
                          script_definitions=SCRIPT_DEFINITIONS)

def run_check_script(script_name, params=None):
    """Запускает скрипт проверки и возвращает результат"""
    import subprocess
    import sys
    import os
    
    # Ищем скрипт в нескольких местах
    project_root = os.path.dirname(os.path.abspath(__file__))
    scripts_dir = os.path.join(project_root, 'scripts')
    
    # Проверяем в корне проекта (приоритет, так как многие скрипты там)
    script_path = os.path.join(project_root, f'{script_name}.py')
    
    # Если не найден в корне, проверяем в директории scripts/
    if not os.path.exists(script_path):
        script_path = os.path.join(scripts_dir, f'{script_name}.py')
    
    if not os.path.exists(script_path):
        flash(f'Скрипт {script_name}.py не найден ни в scripts/, ни в корне проекта', 'error')
        logger.error(f'Script {script_name}.py not found in {scripts_dir} or {project_root}')
        return redirect(url_for('admin_tools'))
    
    # Проверяем права доступа к файлу
    if not os.access(script_path, os.R_OK):
        flash(f'Нет прав на чтение скрипта {script_name}.py. Файл принадлежит другому пользователю. Обратитесь к администратору сервера.', 'error')
        logger.error(f'No read permission for script {script_path}. Owner: {os.stat(script_path).st_uid}, Permissions: {oct(os.stat(script_path).st_mode)}')
        return redirect(url_for('admin_tools'))
    
    # Проверяем права на выполнение
    if not os.access(script_path, os.X_OK):
        logger.warning(f'Script {script_path} is not executable, but will try to run with python interpreter')
    
    try:
        # Устанавливаем рабочую директорию и PYTHONPATH для корректного импорта модулей
        env = os.environ.copy()
        env['PYTHONPATH'] = project_root + os.pathsep + env.get('PYTHONPATH', '')
        
        # Подготавливаем аргументы командной строки для параметров
        cmd = [sys.executable, script_path]
        if params:
            for key, value in params.items():
                cmd.extend([f'--{key}', str(value)])
        
        # Запускаем скрипт и перехватываем вывод
        # Для интерактивных скриптов используем Popen с автоматическим подтверждением
        script_def = SCRIPT_DEFINITIONS.get(script_name, {})
        if script_def.get('requires_confirmation'):
            # Используем Popen для интерактивных скриптов
            import subprocess as sp
            process = sp.Popen(
                cmd,
                stdin=sp.PIPE,
                stdout=sp.PIPE,
                stderr=sp.STDOUT,
                text=True,
                cwd=project_root,
                env=env,
                bufsize=1
            )
            # Автоматически подтверждаем
            stdout, _ = process.communicate(input='yes\n', timeout=600)
            result = type('obj', (object,), {
                'returncode': process.returncode,
                'stdout': stdout,
                'stderr': ''
            })()
        else:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,  # 10 минут максимум для более сложных скриптов
                cwd=project_root,  # Устанавливаем рабочую директорию в корень проекта
                env=env  # Передаем переменные окружения с PYTHONPATH
            )
        
        output = result.stdout + result.stderr
        
        if result.returncode == 0:
            # Сохраняем полный вывод в сессию для отображения
            # Сохраняем вывод в файл вместо сессии (чтобы избежать проблем с размером cookie)
            output_dir = os.path.join(project_root, 'logs', 'script_outputs')
            os.makedirs(output_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = os.path.join(output_dir, f'{script_name}_{timestamp}.txt')
            
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(output)
                
                # Сохраняем только путь к файлу в сессии (небольшой размер)
                session[f'script_output_file_{script_name}'] = output_file
                session[f'script_output_time_{script_name}'] = timestamp
            except Exception as e:
                logger.error(f'Error saving script output to file: {str(e)}')
                # Если не удалось сохранить в файл, сохраняем только первые 1000 символов в сессии
                session[f'script_output_{script_name}'] = output[:1000] if len(output) > 1000 else output
            # Обрезаем вывод если он слишком длинный для flash сообщения
            output_preview = output[:500] if len(output) > 500 else output
            flash(f'Скрипт {script_name} выполнен успешно. Результаты сохранены.', 'success')
            logger.info(f'Admin ran script {script_name}:\n{output}')
        else:
            # Сохраняем ошибку в сессию
            # Сохраняем вывод в файл вместо сессии (чтобы избежать проблем с размером cookie)
            output_dir = os.path.join(project_root, 'logs', 'script_outputs')
            os.makedirs(output_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = os.path.join(output_dir, f'{script_name}_{timestamp}.txt')
            
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(output)
                
                # Сохраняем только путь к файлу в сессии (небольшой размер)
                session[f'script_output_file_{script_name}'] = output_file
                session[f'script_output_time_{script_name}'] = timestamp
            except Exception as e:
                logger.error(f'Error saving script output to file: {str(e)}')
                # Если не удалось сохранить в файл, сохраняем только первые 1000 символов в сессии
                session[f'script_output_{script_name}'] = output[:1000] if len(output) > 1000 else output
            # Показываем первые строки ошибки пользователю
            error_lines = output.split('\n')[:5]
            error_preview = '\n'.join(error_lines)
            flash(f'Скрипт {script_name} завершился с ошибкой. См. детали ниже.', 'error')
            logger.error(f'Script {script_name} failed:\n{output}')
            
    except subprocess.TimeoutExpired:
        flash(f'Скрипт {script_name} превысил время выполнения (10 минут)', 'error')
    except Exception as e:
        flash(f'Ошибка при запуске скрипта: {str(e)}', 'error')
        logger.error(f'Error running script {script_name}: {str(e)}')
    
    return redirect(url_for('admin_tools'))

def run_script_with_params(script_name, params):
    """Запускает скрипт с параметрами"""
    # Для скриптов с параметрами нужно передать их через командную строку
    # Но многие скрипты используют input() для интерактивного ввода
    # В этом случае нужно модифицировать скрипты или использовать другой подход
    
    # Пока что просто передаем параметры как переменные окружения
    import os
    env = os.environ.copy()
    for key, value in params.items():
        env[f'SCRIPT_{key.upper()}'] = str(value)
    
    return run_check_script(script_name, params)

def delete_event_completely(event_id):
    """Полностью удаляет турнир со всеми связями"""
    try:
        event = Event.query.get_or_404(event_id)
        
        # Подсчитываем что будет удалено
        categories = Category.query.filter_by(event_id=event_id).all()
        participants_count = Participant.query.filter_by(event_id=event_id).count()
        performances_count = 0
        
        for cat in categories:
            parts = Participant.query.filter_by(category_id=cat.id).all()
            for part in parts:
                performances_count += Performance.query.filter_by(participant_id=part.id).count()
        
        # Удаляем турнир (cascade удалит все связанные данные)
        event_name = event.name
        db.session.delete(event)
        db.session.commit()
        
        flash(f'Турнир "{event_name}" полностью удален. Удалено: {len(categories)} категорий, {participants_count} участников, {performances_count} выступлений', 'success')
        logger.info(f'Admin deleted event {event_id} ({event_name}) completely')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении турнира: {str(e)}', 'error')
        logger.error(f'Error deleting event {event_id}: {str(e)}')
    
    return redirect(url_for('admin_tools'))

def delete_participant_completely(participant_id):
    """Полностью удаляет участие спортсмена в турнире и спортсмена, если у него больше нет участий"""
    try:
        participant = Participant.query.get_or_404(participant_id)
        
        athlete = Athlete.query.get(participant.athlete_id)
        event = Event.query.get(participant.event_id)
        athlete_id = participant.athlete_id
        athlete_name = athlete.full_name if athlete else f'ID {athlete_id}'
        event_name = event.name if event else f'ID {participant.event_id}'
        
        # Подсчитываем выступления
        performances_count = Performance.query.filter_by(participant_id=participant_id).count()
        
        # Проверяем, сколько всего участий у спортсмена
        total_participations = Participant.query.filter_by(athlete_id=athlete_id).count()
        
        # Удаляем участие (cascade удалит все связанные Performance)
        db.session.delete(participant)
        
        # Если это было последнее участие спортсмена, удаляем и самого спортсмена
        athlete_deleted = False
        if total_participations == 1 and athlete:
            db.session.delete(athlete)
            athlete_deleted = True
        
        db.session.commit()
        
        if athlete_deleted:
            flash(f'Участие спортсмена "{athlete_name}" в турнире "{event_name}" полностью удалено. Удалено {performances_count} выступлений. Спортсмен также удален, так как у него больше не было других участий.', 'success')
            logger.info(f'Admin deleted participant {participant_id} and athlete {athlete_id} ({athlete_name} in {event_name}) completely - no other participations')
        else:
            flash(f'Участие спортсмена "{athlete_name}" в турнире "{event_name}" полностью удалено. Удалено {performances_count} выступлений', 'success')
            logger.info(f'Admin deleted participant {participant_id} ({athlete_name} in {event_name}) completely')
        
        # Сохраняем параметры поиска если они были
        search_athlete = request.form.get('search_athlete', '')
        search_event = request.form.get('search_event', '')
        redirect_url = url_for('admin_tools')
        if search_athlete or search_event:
            redirect_url += f'?search_athlete={search_athlete}&search_event={search_event}'
        return redirect(redirect_url)
        
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении участия: {str(e)}', 'error')
        logger.error(f'Error deleting participant {participant_id}: {str(e)}')
    
    return redirect(url_for('admin_tools'))

def delete_athlete_completely(athlete_id):
    """Полностью удаляет спортсмена из базы данных, если у него нет участий"""
    try:
        athlete = Athlete.query.get_or_404(athlete_id)
        athlete_name = athlete.full_name or f'{athlete.last_name} {athlete.first_name}'
        
        # Проверяем, есть ли у спортсмена участия
        participations_count = Participant.query.filter_by(athlete_id=athlete_id).count()
        
        if participations_count > 0:
            flash(f'Нельзя удалить спортсмена "{athlete_name}". У него есть {participations_count} участий. Сначала удалите все участия.', 'error')
            logger.warning(f'Admin tried to delete athlete {athlete_id} ({athlete_name}) with {participations_count} participations')
            return redirect(url_for('admin_tools'))
        
        # Удаляем спортсмена
        db.session.delete(athlete)
        db.session.commit()
        
        flash(f'Спортсмен "{athlete_name}" полностью удален из базы данных', 'success')
        logger.info(f'Admin deleted athlete {athlete_id} ({athlete_name}) completely')
        
        # Сохраняем параметры поиска если они были
        search_athlete_no_starts = request.form.get('search_athlete_no_starts', '')
        redirect_url = url_for('admin_tools')
        if search_athlete_no_starts:
            redirect_url += f'?search_athlete_no_starts={search_athlete_no_starts}'
        return redirect(redirect_url)
        
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении спортсмена: {str(e)}', 'error')
        logger.error(f'Error deleting athlete {athlete_id}: {str(e)}')
    
    return redirect(url_for('admin_tools'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='127.0.0.1', port=5001)

# Для продакшена на Beget
if __name__ != '__main__':
    with app.app_context():
        db.create_all()

