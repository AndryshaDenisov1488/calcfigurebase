#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Admin routes."""
import logging
import os
import xml.etree.ElementTree as ET
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session, flash, current_app
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename

from extensions import limiter, db
from utils.auth import admin_required
from parsers.isu_calcfs_parser import ISUCalcFSParser
from services.rank_service import analyze_categories_from_xml
from services.import_service import save_to_database
from models import Event, Participant

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/upload', methods=['GET', 'POST'])
@admin_required
@limiter.limit("100 per minute")  # Увеличено для загрузки множественных файлов
def upload_file():
    """Загрузка и парсинг XML файла(ов)"""
    if request.method == 'POST':
        try:
            logger.info(f"File upload attempt from {request.remote_addr}")
            if 'file' not in request.files:
                logger.warning(f"No file in request from {request.remote_addr}")
                return jsonify({'error': 'Файл не выбран'}), 400
            
            # Поддержка множественной загрузки
            files = request.files.getlist('file')
            if not files or all(f.filename == '' for f in files):
                return jsonify({'error': 'Файл не выбран'}), 400
            
            uploaded_files = []
            errors = []
            
            for file in files:
                if file.filename == '':
                    continue
                if not file.filename.lower().endswith('.xml'):
                    errors.append(f'Файл "{file.filename}" не является XML файлом')
                    continue
                
                filename = secure_filename(file.filename)
                # Добавляем timestamp для уникальности при множественной загрузке
                import time
                timestamp = int(time.time() * 1000)
                name, ext = os.path.splitext(filename)
                filename = f"{name}_{timestamp}{ext}"
                filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                
                try:
                    file.save(filepath)
                    try:
                        ET.parse(filepath)
                    except ET.ParseError as e:
                        os.remove(filepath)
                        errors.append(f'Файл "{file.filename}" не является корректным XML: {str(e)}')
                        continue
                    
                    uploaded_files.append({'filepath': filepath, 'filename': file.filename, 'saved_filename': filename})
                except Exception as e:
                    if os.path.exists(filepath):
                        os.remove(filepath)
                    errors.append(f'Ошибка обработки файла "{file.filename}": {str(e)}')
            
            if not uploaded_files:
                return jsonify({'error': 'Не удалось загрузить ни одного файла. ' + '; '.join(errors)}), 400
            
            # Очищаем старые файлы из сессии и с диска перед загрузкой новых
            if 'uploaded_files' in session and session['uploaded_files']:
                logger.info(f"Очистка {len(session['uploaded_files'])} старых файлов из сессии")
                for old_file in session['uploaded_files']:
                    old_filepath = old_file.get('filepath')
                    if old_filepath and os.path.exists(old_filepath):
                        try:
                            os.remove(old_filepath)
                            logger.debug(f"Удален старый файл: {old_filepath}")
                        except Exception as e:
                            logger.warning(f"Не удалось удалить старый файл {old_filepath}: {str(e)}")
            
            # Очищаем старые данные парсера
            if 'parser_data' in session:
                old_parser_data = session.pop('parser_data', None)
                logger.debug("Очищены старые данные парсера из сессии")
            
            # Сохраняем новый список файлов в сессии (заменяем, а не добавляем)
            session['uploaded_files'] = uploaded_files
            session.modified = True
            logger.info(f"Загружено {len(uploaded_files)} новых файлов в сессию")
            
            message = f'Загружено файлов: {len(uploaded_files)}'
            if errors:
                message += f'. Ошибки: {len(errors)}'
            
            return jsonify({
                'success': True,
                'message': message + '. Используйте кнопку "Обработать XML" для анализа и нормализации категорий.',
                'uploaded_count': len(uploaded_files),
                'errors': errors if errors else None,
                'requires_normalization': True
            })
        except Exception as e:
            logger.error(f"Критическая ошибка при загрузке файлов: {str(e)}", exc_info=True)
            return jsonify({'error': f'Внутренняя ошибка сервера: {str(e)}'}), 500
    return render_template('upload.html')

@admin_bp.route('/analyze-xml', methods=['POST'])
@admin_required
@limiter.limit("10 per minute")
def analyze_xml():
    """Анализ XML файла(ов) без сохранения в базу"""
    try:
        logger.info(f"Запрос на анализ XML. Сессия содержит uploaded_files: {'uploaded_files' in session}")
        
        # Проверяем, есть ли файлы в сессии (множественная загрузка)
        if 'uploaded_files' in session and session['uploaded_files']:
        uploaded_files = session['uploaded_files']
        logger.info(f"Анализ {len(uploaded_files)} файлов из сессии")
        
        all_categories_analysis = []
        all_parser_summaries = []
        all_file_data = []
        errors = []
        
        for file_info in uploaded_files:
            filepath = file_info['filepath']
            if not os.path.exists(filepath):
                error_msg = f'Файл "{file_info["filename"]}" не найден на сервере'
                logger.error(error_msg)
                errors.append(error_msg)
                continue
                
            try:
                parser = ISUCalcFSParser(filepath)
                parser.parse()
                categories_analysis = analyze_categories_from_xml(parser)
                
                all_categories_analysis.extend(categories_analysis)
                all_parser_summaries.append({
                    'filename': file_info['filename'],
                    'events': len(parser.events),
                    'categories': len(parser.categories),
                    'segments': len(parser.segments),
                    'persons': len(parser.persons),
                    'clubs': len(parser.clubs),
                    'participants': len(parser.participants),
                    'performances': len(parser.performances)
                })
                all_file_data.append({
                    'filepath': filepath,
                    'filename': file_info['filename'],
                    'saved_filename': file_info['saved_filename'],
                    'categories_count': len(categories_analysis)
                })
                logger.info(f"Файл {file_info['filename']} успешно проанализирован")
            except Exception as e:
                error_msg = f'Ошибка анализа файла "{file_info["filename"]}": {str(e)}'
                logger.error(error_msg, exc_info=True)
                errors.append(error_msg)
        
        if not all_file_data:
            return jsonify({'error': 'Не удалось проанализировать ни одного файла. ' + '; '.join(errors)}), 500
        
        # Сохраняем данные всех файлов в сессии
        session['parser_data'] = {
            'files': all_file_data,
            'categories_analysis': all_categories_analysis,
            'parser_summaries': all_parser_summaries
        }
        session.modified = True
        
        total_categories = len(all_categories_analysis)
        total_files = len(all_file_data)
        
        message = f'Проанализировано файлов: {total_files}. Найдено категорий: {total_categories}'
        if errors:
            message += f'. Ошибок: {len(errors)}'
        
        return jsonify({
            'success': True,
            'categories_analysis': all_categories_analysis,
            'parser_summaries': all_parser_summaries,
            'files_count': total_files,
            'message': message,
            'errors': errors if errors else None
        })
        
        # Если файлов нет в сессии, возвращаем ошибку
        logger.warning("Нет файлов в сессии для анализа. Проверяем прямой запрос с файлом...")
        
        # Обработка одного файла (старая логика для совместимости - прямой запрос с файлом)
        # Это используется только если файл отправляется напрямую в запросе
        if 'file' not in request.files:
            return jsonify({
                'error': 'Нет загруженных файлов для анализа. Сначала загрузите файлы через форму загрузки, затем нажмите "Обработать XML".'
            }), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'Файл не выбран'}), 400
        if not file.filename.lower().endswith('.xml'):
            return jsonify({'error': f'Неверный формат файла. Ожидается .xml, получен: {file.filename}'}), 400
        filename = secure_filename(file.filename)
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        try:
        file.save(filepath)
        try:
            ET.parse(filepath)
        except ET.ParseError as e:
            os.remove(filepath)
            return jsonify({'error': f'Файл не является корректным XML: {str(e)}'}), 400
        parser = ISUCalcFSParser(filepath)
        parser.parse()
        categories_analysis = analyze_categories_from_xml(parser)
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
            logger.error(f"Ошибка анализа файла: {str(e)}", exc_info=True)
            if 'filepath' in locals() and os.path.exists(filepath):
                os.remove(filepath)
            return jsonify({'error': f'Ошибка анализа файла: {str(e)}'}), 500
    except Exception as e:
        logger.error(f"Критическая ошибка при анализе XML (внешний обработчик): {str(e)}", exc_info=True)
        return jsonify({'error': f'Внутренняя ошибка сервера при анализе XML: {str(e)}'}), 500

@admin_bp.route('/normalize-categories', methods=['GET', 'POST'])
@admin_required
def normalize_categories():
    """Страница для ручной нормализации категорий"""
    if 'parser_data' not in session:
        flash('Нет данных для нормализации', 'error')
        return redirect(url_for('admin.upload_file'))
    parser_data = session['parser_data']
    
    # Поддержка множественных файлов
    if 'files' in parser_data:
        # Множественная загрузка
        categories_analysis = parser_data['categories_analysis']
        parser_summaries = parser_data['parser_summaries']
        
        if request.method == 'POST':
            normalizations = {}
            for key, value in request.form.items():
                if key.startswith('normalize_'):
                    category_index = int(key.replace('normalize_', ''))
                    normalizations[category_index] = value
            for index, normalized_name in normalizations.items():
                if index < len(categories_analysis):
                    categories_analysis[index]['normalized'] = normalized_name
                    categories_analysis[index]['needs_manual'] = False
            session['parser_data']['categories_analysis'] = categories_analysis
            
            # Сохраняем все файлы последовательно
            try:
                category_index = 0
                total_athletes = 0
                for file_info in parser_data['files']:
                    parser = ISUCalcFSParser(file_info['filepath'])
                    parser.parse()
                    
                    # Применяем нормализацию к категориям этого файла
                    file_categories_count = file_info['categories_count']
                    for i, category in enumerate(parser.categories):
                        if category_index < len(categories_analysis):
                            category['normalized_name'] = categories_analysis[category_index]['normalized']
                            category_index += 1
                    
                    save_to_database(parser)
                    total_athletes += len(parser.get_athletes_with_results())
                    os.remove(file_info['filepath'])
                
                # Очищаем сессию
                session.pop('parser_data', None)
                session.pop('uploaded_files', None)
                flash(f'Успешно загружено файлов: {len(parser_data["files"])}. Добавлено спортсменов: {total_athletes}', 'success')
                return redirect(url_for('public.index'))
            except Exception as e:
                logger.error(f"Ошибка при сохранении нормализованных данных: {str(e)}")
                flash(f'Ошибка при сохранении данных: {str(e)}', 'error')
        
        all_ranks = []
        from services.rank_service import RANK_DICTIONARY
        for rank_data in RANK_DICTIONARY.values():
            for _, name in rank_data['genders'].items():
                all_ranks.append(name)
        
        return render_template(
            'normalize_categories.html',
            categories_analysis=categories_analysis,
            all_ranks=sorted(set(all_ranks)),
            parser_summaries=parser_summaries,
            files_count=len(parser_data['files'])
        )
    else:
        # Один файл (старая логика)
        categories_analysis = parser_data['categories_analysis']
        if request.method == 'POST':
            normalizations = {}
            for key, value in request.form.items():
                if key.startswith('normalize_'):
                    category_index = int(key.replace('normalize_', ''))
                    normalizations[category_index] = value
            for index, normalized_name in normalizations.items():
                if index < len(categories_analysis):
                    categories_analysis[index]['normalized'] = normalized_name
                    categories_analysis[index]['needs_manual'] = False
            session['parser_data']['categories_analysis'] = categories_analysis
            try:
                parser = ISUCalcFSParser(parser_data['filepath'])
                parser.parse()
                for i, category in enumerate(parser.categories):
                    if i < len(categories_analysis):
                        category['normalized_name'] = categories_analysis[i]['normalized']
                save_to_database(parser)
                os.remove(parser_data['filepath'])
                session.pop('parser_data', None)
                flash('Файл успешно загружен и обработан с нормализацией категорий!', 'success')
                return redirect(url_for('public.index'))
            except Exception as e:
                logger.error(f"Ошибка при сохранении нормализованных данных: {str(e)}")
                flash(f'Ошибка при сохранении данных: {str(e)}', 'error')
        all_ranks = []
        from services.rank_service import RANK_DICTIONARY
        for rank_data in RANK_DICTIONARY.values():
            for _, name in rank_data['genders'].items():
                all_ranks.append(name)
        return render_template(
            'normalize_categories.html',
            categories_analysis=categories_analysis,
            all_ranks=sorted(set(all_ranks)),
            parser_summary=parser_data.get('parser_summary', {}),
            files_count=1
        )

@admin_bp.route('/upload-to-database', methods=['POST'])
@admin_required
def upload_to_database():
    """Финальная загрузка данных в базу после нормализации"""
    if 'parser_data' not in session:
        return jsonify({'error': 'Нет данных для загрузки'}), 400
    parser_data = session['parser_data']
    
    try:
        # Поддержка множественных файлов
        if 'files' in parser_data:
            category_index = 0
            total_athletes = 0
            processed_files = []
            
            for file_info in parser_data['files']:
                parser = ISUCalcFSParser(file_info['filepath'])
                parser.parse()
                
                # Применяем нормализацию к категориям этого файла
                file_categories_count = file_info['categories_count']
                categories_analysis = parser_data['categories_analysis']
                
                for i, category in enumerate(parser.categories):
                    if category_index < len(categories_analysis):
                        category['normalized_name'] = categories_analysis[category_index]['normalized']
                        category_index += 1
                
                save_to_database(parser)
                athletes_count = len(parser.get_athletes_with_results())
                total_athletes += athletes_count
                processed_files.append({
                    'filename': file_info['filename'],
                    'athletes': athletes_count
                })
                os.remove(file_info['filepath'])
            
            session.pop('parser_data', None)
            session.pop('uploaded_files', None)
            
            files_info = ', '.join([f"{f['filename']} ({f['athletes']} спортсменов)" for f in processed_files])
            return jsonify({
                'success': True,
                'message': f'Успешно загружено файлов: {len(processed_files)}. Всего добавлено спортсменов: {total_athletes}.',
                'files_info': files_info,
                'total_athletes': total_athletes
            })
        else:
            # Один файл (старая логика)
            parser = ISUCalcFSParser(parser_data['filepath'])
            parser.parse()
            categories_analysis = parser_data['categories_analysis']
            for i, category in enumerate(parser.categories):
                if i < len(categories_analysis):
                    category['normalized_name'] = categories_analysis[i]['normalized']
            save_to_database(parser)
            athletes_count = len(parser.get_athletes_with_results())
            os.remove(parser_data['filepath'])
            session.pop('parser_data', None)
            return jsonify({
                'success': True,
                'message': f'Файл успешно загружен в базу данных! Добавлено {athletes_count} спортсменов.'
            })
    except Exception as e:
        logger.error(f"Ошибка при загрузке в базу: {str(e)}")
        return jsonify({'error': f'Ошибка при загрузке в базу: {str(e)}'}), 500

@admin_bp.route('/admin/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def admin_login():
    """Страница входа для администратора"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        password_hash = current_app.config.get('ADMIN_PASSWORD_HASH')
        password_plain = current_app.config.get('ADMIN_PASSWORD')
        is_valid_password = False
        if password_hash:
            is_valid_password = check_password_hash(password_hash, password or '')
        elif password_plain:
            is_valid_password = password == password_plain
        if username == current_app.config['ADMIN_USERNAME'] and is_valid_password:
            session['admin_logged_in'] = True
            flash('Успешный вход в систему', 'success')
            return redirect(url_for('public.index'))
        flash('Неверное имя пользователя или пароль', 'error')
    return render_template('admin_login.html')

@admin_bp.route('/admin/logout')
def admin_logout():
    """Выход из системы"""
    session.pop('admin_logged_in', None)
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('public.index'))

@admin_bp.route('/admin/export-google-sheets', methods=['GET', 'POST'])
@admin_required
def admin_export_google_sheets():
    """Экспорт данных в Google Sheets"""
    from google_sheets_sync import export_to_google_sheets, DEFAULT_SPREADSHEET_ID
    
    # Проверяем наличие файла credentials (используем тот же способ, что и в google_sheets_sync.py)
    import os
    # Определяем корень проекта так же, как в google_sheets_sync.py
    # Если google_sheets_sync.py в корне проекта, используем его директорию
    try:
        import google_sheets_sync
        base_dir = os.path.dirname(os.path.abspath(google_sheets_sync.__file__))
    except:
        # Fallback: определяем корень проекта относительно текущего файла
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    credentials_path = os.environ.get('GOOGLE_CREDENTIALS_PATH') or os.path.join(base_dir, 'google_credentials.json')
    credentials_exists = os.path.exists(credentials_path) and os.access(credentials_path, os.R_OK)
    
    if request.method == 'POST':
        if not credentials_exists:
            flash('Файл google_credentials.json не найден или недоступен для чтения', 'error')
            return render_template('admin_export_google_sheets.html', 
                                 credentials_exists=credentials_exists,
                                 spreadsheet_id=DEFAULT_SPREADSHEET_ID)
        try:
            result = export_to_google_sheets()
            if result.get('success'):
                flash('Данные успешно экспортированы в Google Sheets!', 'success')
            else:
                flash(f'Ошибка экспорта: {result.get("message", "Неизвестная ошибка")}', 'error')
        except Exception as e:
            logger.error(f"Ошибка экспорта в Google Sheets: {e}", exc_info=True)
            flash(f'Ошибка экспорта: {str(e)}', 'error')
    
    return render_template('admin_export_google_sheets.html', 
                         credentials_exists=credentials_exists,
                         spreadsheet_id=DEFAULT_SPREADSHEET_ID)

@admin_bp.route('/admin/free-participation', methods=['GET', 'POST'])
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

