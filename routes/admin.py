#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Admin routes."""
import logging
import os
import threading
import time
import json
import xml.etree.ElementTree as ET
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session, flash, current_app
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename

from extensions import limiter, db
from utils.auth import admin_required
from parsers.isu_calcfs_parser import ISUCalcFSParser
from services.rank_service import analyze_categories_from_xml
from services.import_service import save_to_database
from services.xml_import_prepare import iter_ready_parsers
from services.import_birth_conflict import (
    apply_birth_conflict_resolutions_json,
    find_birth_date_conflicts,
)
from services.xml_archive import archive_imported_xml
from collections import defaultdict

from sqlalchemy import and_, case, func

from event_rank_constants import EVENT_RANK_OPTIONS
from models import Category, Event, Participant, JudgeHelperFreeAudit

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__)


def _parse_normalize_category_form(request):
    """Читает normalize_* и delete_* из формы нормализации категорий."""
    normalizations = {}
    deleted_indices = set()
    for key, value in request.form.items():
        if key.startswith('normalize_'):
            normalizations[int(key.replace('normalize_', ''))] = value
        elif key.startswith('delete_') and value == '1':
            deleted_indices.add(int(key.replace('delete_', '')))
    return normalizations, deleted_indices


def _safe_parse_birth_conflict_resolutions(raw: str) -> list:
    if not raw or not str(raw).strip():
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning('birth_conflict_resolutions: невалидный JSON')
        return []
    if not isinstance(data, list):
        return []
    out = []
    for item in data:
        if not isinstance(item, dict):
            continue
        use = item.get('use')
        if use not in ('xml', 'db'):
            continue
        try:
            out.append({
                'person_id': str(item['person_id']),
                'athlete_id': int(item['athlete_id']),
                'use': use,
            })
        except (KeyError, TypeError, ValueError):
            continue
    return out


@admin_bp.route('/check-import-birth-conflicts', methods=['POST'])
@admin_required
@limiter.limit('30 per minute')
def check_import_birth_conflicts():
    """Проверка перед импортом: совпадение ФИО при разной дате рождения."""
    if 'parser_data' not in session:
        return jsonify({'success': False, 'error': 'Нет данных импорта в сессии'}), 400
    parser_data = session['parser_data']
    categories_analysis = parser_data['categories_analysis']

    normalizations, deleted_indices_form = _parse_normalize_category_form(request)
    ca_work = [dict(c) for c in categories_analysis]

    for index, normalized_name in normalizations.items():
        if index < len(ca_work):
            ca_work[index]['normalized'] = normalized_name
            ca_work[index]['needs_manual'] = False

    if 'files' in parser_data:
        deleted_indices = set(parser_data.get('deleted_category_indices', []))
    else:
        deleted_indices = deleted_indices_form

    conflicts_all = []
    try:
        for parser, _fp, _fn in iter_ready_parsers(parser_data, ca_work, deleted_indices):
            conflicts_all.extend(find_birth_date_conflicts(parser))
    except Exception as e:
        logger.error('check_import_birth_conflicts: %s', e, exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

    seen = set()
    uniq = []
    for c in conflicts_all:
        k = (c['person_id'], c['athlete_id'])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(c)

    return jsonify({'success': True, 'conflicts': uniq})

_export_job_lock = threading.Lock()


def _export_state_path(app_obj):
    """Путь к общему состоянию экспорта (доступен всем воркерам)."""
    os.makedirs(app_obj.instance_path, exist_ok=True)
    return os.path.join(app_obj.instance_path, 'google_export_state.json')


def _read_export_state(app_obj):
    path = _export_state_path(app_obj)
    if not os.path.exists(path):
        return {
            'running': False,
            'started_at': None,
            'finished_at': None,
            'success': None,
            'message': None,
            'url': None,
        }
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return {
                'running': bool(data.get('running', False)),
                'started_at': data.get('started_at'),
                'finished_at': data.get('finished_at'),
                'success': data.get('success'),
                'message': data.get('message'),
                'url': data.get('url'),
            }
    except Exception:
        return {
            'running': False,
            'started_at': None,
            'finished_at': None,
            'success': None,
            'message': None,
            'url': None,
        }


def _write_export_state(app_obj, state):
    path = _export_state_path(app_obj)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False)
    os.replace(tmp_path, path)


def _start_google_export_background(app_obj):
    """Запускает экспорт в отдельном потоке и обновляет состояние задачи."""
    from google_sheets_sync import export_to_google_sheets

    def _worker():
        with app_obj.app_context():
            try:
                result = export_to_google_sheets()
                with _export_job_lock:
                    state = _read_export_state(app_obj)
                    state['running'] = False
                    state['finished_at'] = int(time.time())
                    state['success'] = bool(result.get('success'))
                    state['message'] = result.get('message', 'Экспорт завершён')
                    state['url'] = result.get('url')
                    _write_export_state(app_obj, state)
            except Exception as e:
                logger.error(f"Ошибка фонового экспорта в Google Sheets: {e}", exc_info=True)
                with _export_job_lock:
                    state = _read_export_state(app_obj)
                    state['running'] = False
                    state['finished_at'] = int(time.time())
                    state['success'] = False
                    state['message'] = f'Ошибка экспорта: {str(e)}'
                    state['url'] = None
                    _write_export_state(app_obj, state)

    with _export_job_lock:
        state = _read_export_state(app_obj)
        if state.get('running'):
            return False
        state['running'] = True
        state['started_at'] = int(time.time())
        state['finished_at'] = None
        state['success'] = None
        state['message'] = 'Экспорт запущен. Это может занять несколько минут...'
        state['url'] = None
        _write_export_state(app_obj, state)

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    return True

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
            
            # Ограничение на количество файлов за раз (из-за ограничений сессии Flask)
            MAX_FILES_PER_UPLOAD = 15
            if len(files) > MAX_FILES_PER_UPLOAD:
                return jsonify({
                    'error': f'Слишком много файлов выбрано ({len(files)}). Максимальное количество файлов за раз: {MAX_FILES_PER_UPLOAD}. Пожалуйста, загрузите файлы порциями по {MAX_FILES_PER_UPLOAD} штук.'
                }), 400
            
            uploaded_files = []
            errors = []
            
            for file in files:
                if file.filename == '':
                    continue
                if not file.filename.lower().endswith('.xml'):
                    errors.append(f'Файл "{file.filename}" не является XML файлом')
                    continue
                
                filename = secure_filename(file.filename)
                # Добавляем timestamp и случайное число для уникальности при множественной загрузке
                import time
                import random
                timestamp = int(time.time() * 1000)
                random_suffix = random.randint(1000, 9999)
                name, ext = os.path.splitext(filename)
                filename = f"{name}_{timestamp}_{random_suffix}{ext}"
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
            # Ограничиваем размер данных в сессии - сохраняем только необходимую информацию
            try:
                session['uploaded_files'] = uploaded_files
                session.modified = True
                logger.info(f"Загружено {len(uploaded_files)} новых файлов в сессию")
            except Exception as session_error:
                logger.error(f"Ошибка сохранения в сессию: {str(session_error)}", exc_info=True)
                # Если не удалось сохранить в сессию, удаляем загруженные файлы
                for uploaded_file in uploaded_files:
                    filepath = uploaded_file.get('filepath')
                    if filepath and os.path.exists(filepath):
                        try:
                            os.remove(filepath)
                        except:
                            pass
                return jsonify({
                    'error': f'Ошибка сохранения данных: слишком много файлов для сессии. Пожалуйста, загрузите файлы порциями по 10-15 штук.'
                }), 500
            
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
            # Очищаем частично загруженные файлы при ошибке
            if 'uploaded_files' in locals():
                for uploaded_file in uploaded_files:
                    filepath = uploaded_file.get('filepath')
                    if filepath and os.path.exists(filepath):
                        try:
                            os.remove(filepath)
                        except:
                            pass
            error_message = str(e)
            # Если ошибка связана с сессией, даем более понятное сообщение
            if 'session' in error_message.lower() or 'too large' in error_message.lower():
                error_message = 'Слишком много файлов для обработки за раз. Попробуйте загрузить меньше файлов (рекомендуется не более 10-15 файлов за раз).'
            return jsonify({'error': f'Внутренняя ошибка сервера: {error_message}'}), 500
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
                'upload_original_filename': file.filename,
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
                deleted_indices = set(parser_data.get('deleted_category_indices', []))
                resolutions = _safe_parse_birth_conflict_resolutions(
                    request.form.get('birth_conflict_resolutions', '')
                )

                parsers_bundle = list(iter_ready_parsers(parser_data, categories_analysis, deleted_indices))
                if parsers_bundle:
                    apply_birth_conflict_resolutions_json(
                        resolutions, [p for p, _fp, _fn in parsers_bundle]
                    )
                    db.session.flush()

                total_athletes = 0
                up_folder = current_app.config['UPLOAD_FOLDER']
                for parser, filepath, original_filename in parsers_bundle:
                    save_to_database(parser)
                    total_athletes += len(parser.get_athletes_with_results())
                    archive_imported_xml(
                        filepath,
                        original_filename or os.path.basename(filepath),
                        up_folder,
                    )
                    if os.path.exists(filepath):
                        try:
                            os.remove(filepath)
                        except OSError as e:
                            logger.warning(f"Не удалось удалить файл {filepath}: {str(e)}")
                    else:
                        logger.warning(f"Файл уже не существует при попытке удаления: {filepath}")

                # Очищаем сессию
                session.pop('parser_data', None)
                session.pop('uploaded_files', None)
                deleted_count = len(deleted_indices)
                if deleted_count > 0:
                    flash(f'Успешно загружено файлов: {len(parser_data["files"])}. Добавлено спортсменов: {total_athletes}. Исключено категорий: {deleted_count}', 'success')
                else:
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
            deleted_indices = set()
            
            # Собираем нормализации и удаленные категории
            for key, value in request.form.items():
                if key.startswith('normalize_'):
                    category_index = int(key.replace('normalize_', ''))
                    normalizations[category_index] = value
                elif key.startswith('delete_'):
                    category_index = int(key.replace('delete_', ''))
                    if value == '1':  # Категория помечена как удаленная
                        deleted_indices.add(category_index)
            
            # Применяем нормализации (только для не удаленных категорий)
            for index, normalized_name in normalizations.items():
                if index not in deleted_indices and index < len(categories_analysis):
                    categories_analysis[index]['normalized'] = normalized_name
                    categories_analysis[index]['needs_manual'] = False
            
            # Помечаем удаленные категории
            for index in deleted_indices:
                if index < len(categories_analysis):
                    categories_analysis[index]['deleted'] = True
            
            session['parser_data']['categories_analysis'] = categories_analysis
            session['parser_data']['deleted_category_indices'] = list(deleted_indices)
            
            try:
                filepath = parser_data.get('filepath')
                if not filepath:
                    flash('Ошибка: путь к файлу не найден в данных сессии. Попробуйте загрузить файл заново.', 'error')
                    return redirect(url_for('admin.upload_file'))
                
                if not os.path.exists(filepath):
                    logger.error(f"Файл не найден: {filepath}")
                    flash(f'Ошибка: файл {os.path.basename(filepath)} не найден. Возможно, он был удален. Попробуйте загрузить файл заново.', 'error')
                    session.pop('parser_data', None)
                    return redirect(url_for('admin.upload_file'))

                resolutions = _safe_parse_birth_conflict_resolutions(
                    request.form.get('birth_conflict_resolutions', '')
                )

                parsers_bundle = list(iter_ready_parsers(parser_data, categories_analysis, deleted_indices))
                if parsers_bundle:
                    apply_birth_conflict_resolutions_json(
                        resolutions, [p for p, _fp, _fn in parsers_bundle]
                    )
                    db.session.flush()

                deleted_count = len(deleted_indices)
                up_folder = current_app.config['UPLOAD_FOLDER']
                if parsers_bundle:
                    parser, filepath, original_filename = parsers_bundle[0]
                    save_to_database(parser)
                    if deleted_count > 0:
                        flash(f'Файл успешно загружен и обработан с нормализацией категорий! Исключено категорий: {deleted_count}', 'success')
                    else:
                        flash('Файл успешно загружен и обработан с нормализацией категорий!', 'success')
                else:
                    flash('Файл обработан, но все категории были исключены из импорта.', 'warning')

                if parsers_bundle:
                    _parser, fp_del, orig_fn = parsers_bundle[0]
                    archive_imported_xml(
                        fp_del,
                        orig_fn or os.path.basename(fp_del),
                        up_folder,
                    )
                    if os.path.exists(fp_del):
                        try:
                            os.remove(fp_del)
                        except OSError as e:
                            logger.warning(f"Не удалось удалить файл {fp_del}: {str(e)}")
                    else:
                        logger.warning(f"Файл уже не существует при попытке удаления: {fp_del}")

                session.pop('parser_data', None)
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

@admin_bp.route('/admin/judge-helper-audit')
@admin_required
def admin_judge_helper_audit():
    """Журнал проверок страницы помощника судьям (бесплатные участия)."""
    page = request.args.get('page', 1, type=int)
    per_page = min(max(request.args.get('per_page', 50, type=int) or 50, 10), 200)
    pagination = JudgeHelperFreeAudit.query.order_by(
        JudgeHelperFreeAudit.created_at.desc()
    ).paginate(page=page, per_page=per_page)
    return render_template('admin_judge_helper_audit.html', pagination=pagination)


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
                archive_imported_xml(
                    file_info['filepath'],
                    file_info.get('filename') or os.path.basename(file_info['filepath']),
                    current_app.config['UPLOAD_FOLDER'],
                )
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
            archive_imported_xml(
                parser_data['filepath'],
                parser_data.get('upload_original_filename') or os.path.basename(parser_data['filepath']),
                current_app.config['UPLOAD_FOLDER'],
            )
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
            session.clear()
            session['admin_logged_in'] = True
            session.permanent = True
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
    """Экспорт данных в Google Sheets и подготовка ссылок PDF по ключевым таблицам."""
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

    pdf_urls = {}

    if request.method == 'POST':
        # Проверяем, что запрос ожидает JSON (AJAX запрос)
        wants_json = request.headers.get('Content-Type') == 'application/json' or \
                     request.headers.get('Accept', '').find('application/json') != -1
        
        if not credentials_exists:
            if wants_json:
                return jsonify({
                    'success': False,
                    'message': 'Файл google_credentials.json не найден или недоступен для чтения'
                }), 400
            else:
                flash('Файл google_credentials.json не найден или недоступен для чтения', 'error')
                return render_template(
                    'admin_export_google_sheets.html',
                    credentials_exists=credentials_exists,
                    spreadsheet_id=DEFAULT_SPREADSHEET_ID,
                    pdf_urls={}
                )
        
        if wants_json:
            # Для AJAX запускаем задачу в фоне и сразу возвращаем JSON, чтобы не упереться в timeout прокси
            started = _start_google_export_background(current_app._get_current_object())
            if started:
                return jsonify({
                    'success': True,
                    'started': True,
                    'running': True,
                    'message': 'Экспорт запущен. Это может занять несколько минут...'
                })
            with _export_job_lock:
                state = _read_export_state(current_app._get_current_object())
                return jsonify({
                    'success': True,
                    'started': False,
                    'running': bool(state.get('running')),
                    'message': state.get('message') or 'Экспорт уже выполняется'
                })

        # Для обычного POST оставляем синхронное поведение
        try:
            result = export_to_google_sheets()
            if result.get('success'):
                flash('Данные успешно экспортированы в Google Sheets!', 'success')
            else:
                flash(f'Ошибка экспорта: {result.get("message", "Неизвестная ошибка")}', 'error')
        except Exception as e:
            logger.error(f"Ошибка экспорта в Google Sheets: {e}", exc_info=True)
            flash(f'Ошибка экспорта: {str(e)}', 'error')
    
    # GET-запрос: просто показываем страницу с текущим статусом
    return render_template(
        'admin_export_google_sheets.html',
        credentials_exists=credentials_exists,
        spreadsheet_id=DEFAULT_SPREADSHEET_ID,
        pdf_urls=pdf_urls
    )


@admin_bp.route('/admin/export-google-sheets-status', methods=['GET'])
@admin_required
def admin_export_google_sheets_status():
    """Статус фонового экспорта в Google Sheets для polling из UI."""
    with _export_job_lock:
        state = _read_export_state(current_app._get_current_object())
        return jsonify({
            'running': bool(state.get('running')),
            'success': state.get('success'),
            'message': state.get('message'),
            'url': state.get('url'),
            'started_at': state.get('started_at'),
            'finished_at': state.get('finished_at'),
        })


@admin_bp.route('/admin/event-rank-update', methods=['POST'])
@admin_required
def admin_event_rank_update():
    """Сохранение ранга турнира через AJAX (без перезагрузки страницы)."""
    allowed_ranks = set(EVENT_RANK_OPTIONS)
    data = request.get_json(silent=True) or {}
    event_id = data.get('event_id')
    if event_id is not None:
        try:
            event_id = int(event_id)
        except (TypeError, ValueError):
            event_id = None
    selected_rank = (data.get('event_rank') or '').strip()

    event = Event.query.get(event_id) if event_id else None
    if not event:
        return jsonify({'success': False, 'message': 'Турнир не найден'}), 404

    if selected_rank and selected_rank not in allowed_ranks:
        return jsonify({'success': False, 'message': 'Недопустимый ранг турнира'}), 400

    event.event_rank = selected_rank or None
    try:
        db.session.commit()
        return jsonify({
            'success': True,
            'message': 'Сохранено',
            'event_id': event.id,
            'event_rank': event.event_rank or '',
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error updating event rank for event_id={event_id}: {e}')
        return jsonify({'success': False, 'message': f'Ошибка: {str(e)}'}), 500


def _event_ranks_list_details_by_id(event_ids: list[int]) -> dict[int, dict]:
    """Участия, уникальные спортсмены, БЕСП (как в отчётах), названия разрядов — по id турнира."""
    if not event_ids:
        return {}

    free_flag = case(
        (
            and_(
                Participant.pct_ppname == 'БЕСП',
                Participant.exclude_free_from_reports.is_(False),
                Event.exclude_free_from_reports.is_(False),
            ),
            1,
        ),
        else_=0,
    )

    agg_rows = (
        db.session.query(
            Participant.event_id,
            func.count(Participant.id).label('participants_total'),
            func.count(func.distinct(Participant.athlete_id)).label('participants_unique'),
            func.coalesce(func.sum(free_flag), 0).label('free_total'),
        )
        .join(Event, Participant.event_id == Event.id)
        .filter(Participant.event_id.in_(event_ids))
        .group_by(Participant.event_id)
        .all()
    )

    by_id = {
        eid: {
            'participants_total': 0,
            'participants_unique': 0,
            'free_total': 0,
            'category_labels': [],
        }
        for eid in event_ids
    }

    for row in agg_rows:
        eid = row.event_id
        by_id[eid]['participants_total'] = int(row.participants_total or 0)
        by_id[eid]['participants_unique'] = int(row.participants_unique or 0)
        by_id[eid]['free_total'] = int(row.free_total or 0)

    cat_rows = (
        db.session.query(Category.event_id, Category.name, Category.normalized_name)
        .filter(Category.event_id.in_(event_ids))
        .all()
    )
    labels_by_event: dict[int, set[str]] = defaultdict(set)
    for eid, name, norm in cat_rows:
        label = (norm or name or '').strip()
        if label:
            labels_by_event[eid].add(label)

    for eid in event_ids:
        by_id[eid]['category_labels'] = sorted(labels_by_event[eid])

    return by_id


@admin_bp.route('/admin/event-ranks', methods=['GET', 'POST'])
@admin_required
def admin_event_ranks():
    """Управление рангами турниров + статистика по рангам."""
    from google_sheets_sync import get_event_rank_statistics_data

    allowed_ranks = set(EVENT_RANK_OPTIONS)

    if request.method == 'POST':
        event_id = request.form.get('event_id', type=int)
        selected_rank = (request.form.get('event_rank') or '').strip()
        event = Event.query.get(event_id) if event_id else None
        if not event:
            flash('Турнир не найден', 'error')
            return redirect(url_for('admin.admin_event_ranks'))

        if selected_rank and selected_rank not in allowed_ranks:
            flash('Недопустимый ранг турнира', 'error')
            return redirect(url_for('admin.admin_event_ranks'))

        event.event_rank = selected_rank or None
        try:
            db.session.commit()
            flash(f'Ранг турнира "{event.name}" обновлён', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении ранга: {str(e)}', 'error')
            logger.error(f'Error updating event rank for event_id={event_id}: {e}')
        return redirect(url_for('admin.admin_event_ranks'))

    events = Event.query.order_by(Event.begin_date.desc(), Event.id.desc()).all()
    rank_stats_bundle = get_event_rank_statistics_data()
    event_ids = [e.id for e in events]
    event_list_details = _event_ranks_list_details_by_id(event_ids)
    return render_template(
        'admin_event_ranks.html',
        events=events,
        rank_options=EVENT_RANK_OPTIONS,
        rank_stats=rank_stats_bundle['without_ms_kms'],
        rank_stats_with_ms_kms=rank_stats_bundle['with_ms_kms'],
        rank_stats_totals=rank_stats_bundle['totals_without_ms_kms'],
        rank_stats_with_ms_kms_totals=rank_stats_bundle['totals_with_ms_kms'],
        event_list_details=event_list_details,
    )

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

        elif action == 'toggle_report_exclusion':
            # Переключаем флаг исключения бесплатных участий из отчётов для турнира
            event = Event.query.get(event_id)
            if not event:
                flash('Турнир не найден', 'error')
                return redirect(url_for('admin.admin_free_participation'))

            requested_value = (request.form.get('exclude_from_reports') or '').strip().lower()
            new_value = requested_value in ('1', 'true', 'yes', 'on')
            event.exclude_free_from_reports = new_value

            try:
                db.session.commit()
                if new_value:
                    flash(
                        f'Турнир "{event.name}" исключен из БЕСП-отчетов. '
                        f'Исходные метки БЕСП сохранены в базе.',
                        'warning'
                    )
                else:
                    flash(
                        f'Турнир "{event.name}" снова учитывается в БЕСП-отчетах.',
                        'success'
                    )
            except Exception as e:
                db.session.rollback()
                flash(f'Ошибка при обновлении флага отчета: {str(e)}', 'error')
                logger.error(f'Error toggling report exclusion for event {event_id}: {str(e)}')
        
        return redirect(url_for('admin.admin_free_participation'))
    
    # GET запрос - показываем форму
    events = Event.query.order_by(Event.begin_date.desc()).all()
    
    # Добавляем статистику для каждого события
    events_data = []
    for event in events:
        total_participants = Participant.query.filter_by(event_id=event.id).count()
        free_participants = Participant.query.filter_by(event_id=event.id, pct_ppname='БЕСП').count()
        effective_free_participants = 0 if event.exclude_free_from_reports else Participant.query.filter(
            Participant.event_id == event.id,
            Participant.pct_ppname == 'БЕСП',
            db.or_(Participant.exclude_free_from_reports.is_(False), Participant.exclude_free_from_reports.is_(None))
        ).count()
        
        events_data.append({
            'event': event,
            'total_participants': total_participants,
            'free_participants': free_participants,
            'effective_free_participants': effective_free_participants,
            'paid_participants': total_participants - free_participants
        })
    
    return render_template('admin_free_participation.html', events_data=events_data)


@admin_bp.route('/admin/participant-free-report-toggle', methods=['POST'])
@admin_required
def participant_free_report_toggle():
    """Включает/исключает конкретное БЕСП-участие из отчетов."""
    participant_id = request.form.get('participant_id', type=int)
    include_in_reports = (request.form.get('include_in_reports') or '').strip().lower() in ('1', 'true', 'yes', 'on')
    redirect_to = request.form.get('redirect_to') or url_for('admin.admin_free_participation')

    participant = Participant.query.get(participant_id) if participant_id else None
    if not participant:
        flash('Участие не найдено', 'error')
        return redirect(redirect_to)

    participant.exclude_free_from_reports = not include_in_reports
    try:
        db.session.commit()
        if include_in_reports:
            flash('Участие снова учитывается как БЕСП в отчетах', 'success')
        else:
            flash('Участие исключено из БЕСП-отчетов', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при обновлении участия: {str(e)}', 'error')
        logger.error(f'Error toggling participant free report flag: {str(e)}')

    return redirect(redirect_to)

