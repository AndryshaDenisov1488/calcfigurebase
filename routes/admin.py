#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Админские маршруты приложения
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session, flash, current_app
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import logging
from detailed_parser import ISUCalcFSParser
from auth.decorators import admin_required
from auth.password import verify_password
from utils.data_builders import analyze_categories_from_xml
from utils.database_save import save_to_database
from utils.category_normalization import RANK_DICTIONARY
from utils.admin_tools import (
    SCRIPT_DEFINITIONS, run_check_script, run_script_with_params,
    delete_event_completely, delete_participant_completely, delete_athlete_completely
)
from models import db, Event, Participant

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Создаем отдельный Blueprint для upload маршрутов без префикса /admin
upload_bp = Blueprint('upload', __name__)

logger = logging.getLogger(__name__)

# Функция для применения rate limiting через декоратор
# Используем limiter из app через current_app после инициализации
def rate_limit(limit_str):
    """Применяет rate limiting к функции используя limiter из app"""
    def decorator(f):
        # ВАЖНО: используем wraps(), иначе все view-функции будут называться "wrapper"
        # и Flask упадет с:
        # AssertionError: View function mapping is overwriting an existing endpoint function: upload.wrapper
        from functools import wraps
        
        # Создаем декоратор, который будет применен во время выполнения
        @wraps(f)
        def wrapper(*args, **kwargs):
            # Получаем limiter из current_app
            # Flask-Limiter регистрируется в app.extensions['limiter'] как объект Limiter
            try:
                # Используем прямой доступ через [], а не get(), чтобы избежать проблем
                limiter_instance = current_app.extensions['limiter']
                # Проверяем, что это действительно объект Limiter (имеет метод limit)
                if limiter_instance and hasattr(limiter_instance, 'limit'):
                    # Применяем rate limiting
                    return limiter_instance.limit(limit_str)(f)(*args, **kwargs)
            except (KeyError, AttributeError, TypeError):
                # Если limiter недоступен или произошла ошибка, вызываем функцию без rate limiting
                pass
            return f(*args, **kwargs)
        
        return wrapper
    return decorator

@admin_bp.route('/login', methods=['GET', 'POST'])
def admin_login():
    """Страница входа для администратора"""
    from config.settings import Config
    
    ADMIN_USERNAME = current_app.config['ADMIN_USERNAME']
    ADMIN_PASSWORD_HASH = current_app.config['ADMIN_PASSWORD_HASH']
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Проверяем имя пользователя и пароль с использованием хеширования
        if username == ADMIN_USERNAME and verify_password(ADMIN_PASSWORD_HASH, password):
            session['admin_logged_in'] = True
            session['last_activity'] = datetime.now().isoformat()
            flash('Успешный вход в систему', 'success')
            logger.info(f"Admin login successful from {request.remote_addr}")
            return redirect(url_for('main.index'))
        else:
            logger.warning(f"Failed admin login attempt from {request.remote_addr}")
            flash('Неверное имя пользователя или пароль', 'error')
    
    return render_template('admin_login.html')

@admin_bp.route('/logout')
def admin_logout():
    """Выход из системы"""
    session.pop('admin_logged_in', None)
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('main.index'))

@upload_bp.route('/upload', methods=['GET', 'POST'])
@admin_required
@rate_limit("5 per minute")
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
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        
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

@upload_bp.route('/analyze-xml', methods=['POST'])
@admin_required
@rate_limit("10 per minute")
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
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    
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

@upload_bp.route('/normalize-categories', methods=['GET', 'POST'])
@admin_required
def normalize_categories():
    """Страница для ручной нормализации категорий"""
    if 'parser_data' not in session:
        flash('Нет данных для нормализации', 'error')
        return redirect(url_for('admin.upload_file'))
    
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
            return redirect(url_for('main.index'))
            
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

@upload_bp.route('/upload-to-database', methods=['POST'])
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

@admin_bp.route('/export-google-sheets', methods=['GET', 'POST'])
@admin_required
def admin_export_google_sheets():
    """Страница экспорта в Google Sheets"""
    from google_sheets_sync import export_to_google_sheets, DEFAULT_SPREADSHEET_ID
    
    # Проверяем наличие credentials
    credentials_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'google_credentials.json')
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

@admin_bp.route('/free-participation', methods=['GET', 'POST'])
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
        
        return redirect(url_for('admin.admin_free_participation'))
    
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

@admin_bp.route('/tools', methods=['GET', 'POST'])
@admin_required
def admin_tools():
    """Админская панель с инструментами для работы с БД"""
    from models import Athlete, Category
    
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
                        return redirect(url_for('admin.admin_tools'))
                
                # Проверка параметров
                if script_def.get('requires_params'):
                    params = {}
                    for param_name in script_def['requires_params']:
                        param_value = request.form.get(param_name)
                        if not param_value:
                            flash(f'Не указан обязательный параметр: {param_name}', 'error')
                            return redirect(url_for('admin.admin_tools'))
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
            return redirect(url_for('admin.admin_tools'))
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

