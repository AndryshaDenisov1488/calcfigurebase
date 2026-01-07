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
import logging
import secrets
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
        if not session.get('admin_logged_in'):
            logger.warning(f"Unauthorized access attempt to {request.endpoint} from {request.remote_addr}")
            flash('Необходима авторизация администратора', 'error')
            return redirect(url_for('admin_login'))
        
        # Проверяем время сессии
        if 'last_activity' in session:
            last_activity = datetime.fromisoformat(session['last_activity'])
            if datetime.now() - last_activity > timedelta(seconds=app.config['PERMANENT_SESSION_LIFETIME'].total_seconds()):
                session.clear()
                logger.info(f"Session expired for admin from {request.remote_addr}")
                flash('Сессия истекла. Войдите заново.', 'warning')
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
    
    # Базовый запрос
    query = Event.query
    
    # Применяем фильтр по разряду, если указан
    if rank_filter:
        query = query.join(Category, Event.id == Category.event_id).filter(
            Category.normalized_name == rank_filter
        ).distinct()
    
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
    
    return render_template('events.html', 
                         events=events, 
                         seasons=seasons,
                         current_sort=sort_by,
                         current_rank_filter=rank_filter,
                         available_ranks=available_ranks)

@app.route('/categories')
def categories():
    """Страница с группировкой по разрядам"""
    category_id = request.args.get('category', type=int)
    event_id = request.args.get('event', type=int)
    
    if category_id:
        # Показываем только конкретную категорию
        categories = Category.query.filter_by(id=category_id).all()
    else:
        # Показываем все категории или фильтруем по турниру
        query = Category.query.join(Event)
        if event_id:
            query = query.filter(Category.event_id == event_id)
        categories = query.order_by(Event.begin_date.desc(), Category.name).all()
    
    # Добавляем подсчет участников для каждой категории
    for category in categories:
        category.num_participants = db.session.query(Participant).filter_by(category_id=category.id).count()
        category.num_entries = category.num_participants  # Заявки = участники
    
    events = Event.query.order_by(Event.begin_date.desc()).all()
    return render_template('categories.html', categories=categories, events=events, selected_category=category_id, selected_event=event_id)

@app.route('/event/<int:event_id>')
def event_detail(event_id):
    """Детальная страница турнира"""
    event = Event.query.get_or_404(event_id)
    categories = Category.query.filter_by(event_id=event_id).all()
    
    # Добавляем подсчет участников для каждой категории
    for category in categories:
        category.num_participants = db.session.query(Participant).filter_by(category_id=category.id).count()
        category.num_entries = category.num_participants  # Заявки = участники
    
    return render_template('event_detail.html', event=event, categories=categories)

@app.route('/api/event/<int:event_id>/export')
def export_event_results(event_id):
    """Экспорт результатов турнира в CSV"""
    event = Event.query.get_or_404(event_id)
    
    # Получаем все результаты турнира
    results = db.session.query(
        Athlete.full_name,
        Athlete.short_name,
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
    csv_content = "ФИО,Краткое имя,Клуб,Категория,Пол,Тип,Место,Баллы,Турнир,Дата\n"
    
    for result in results:
        csv_content += f'"{result.full_name or ""}","{result.short_name or ""}","{result.club_name or ""}","{result.category_name or ""}","{result.gender or ""}","{result.category_type or ""}","{result.total_place or ""}","{round(result.total_points / 100, 2) if result.total_points else ""}","{result.event_name or ""}","{result.begin_date.strftime("%d.%m.%Y") if result.begin_date else ""}"\n'
    
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
                    'events': []
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
            
            athletes_data[athlete_id]['events'].append({
                'event_name': row.event_name,
                'event_date': row.event_date.strftime('%d.%m.%Y') if row.event_date else 'Дата не указана',
                'category_name': row.category_name,
                'rank': rank,
                'place': row.total_place,
                'points': points_display
            })
        
        # Сортируем по количеству бесплатных участий
        result = sorted(athletes_data.values(), key=lambda x: x['free_participations'], reverse=True)
        
        return jsonify({
            'athletes': result,
            'total_athletes': len(result),
            'total_free_participations': sum(a['free_participations'] for a in result)
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
            'gender_display': 'Женский' if athlete.gender == 'F' else 'Мужской' if athlete.gender == 'M' else '-',
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

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='127.0.0.1', port=5001)

# Для продакшена на Beget
if __name__ != '__main__':
    with app.app_context():
        db.create_all()

