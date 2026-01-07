#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Утилиты для админских инструментов
"""

import os
import subprocess
import sys
import logging
from datetime import datetime
from flask import session, flash, redirect, url_for, request, jsonify
from models import db, Event, Category, Athlete, Participant, Performance

logger = logging.getLogger(__name__)

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

def run_check_script(script_name, params=None):
    """Запускает скрипт проверки и возвращает результат"""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    scripts_dir = os.path.join(project_root, 'scripts')
    
    # Проверяем в корне проекта (приоритет, так как многие скрипты там)
    script_path = os.path.join(project_root, f'{script_name}.py')
    
    # Если не найден в корне, проверяем в директории scripts/
    if not os.path.exists(script_path):
        script_path = os.path.join(scripts_dir, f'{script_name}.py')
    
    if not os.path.exists(script_path):
        flash(f'Скрипт {script_name}.py не найден ни в scripts/, ни в корне проекта', 'error')
        logger.error(f'Script {script_name}.py not found in {scripts_dir} or {project_root}')
        return redirect(url_for('admin.admin_tools'))
    
    # Проверяем права доступа к файлу
    if not os.access(script_path, os.R_OK):
        flash(f'Нет прав на чтение скрипта {script_name}.py. Файл принадлежит другому пользователю. Обратитесь к администратору сервера.', 'error')
        logger.error(f'No read permission for script {script_path}. Owner: {os.stat(script_path).st_uid}, Permissions: {oct(os.stat(script_path).st_mode)}')
        return redirect(url_for('admin.admin_tools'))
    
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
        script_def = SCRIPT_DEFINITIONS.get(script_name, {})
        if script_def.get('requires_confirmation'):
            # Используем Popen для интерактивных скриптов
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
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
                cwd=project_root,
                env=env
            )
        
        output = result.stdout + result.stderr
        
        if result.returncode == 0:
            # Сохраняем полный вывод в файл
            output_dir = os.path.join(project_root, 'logs', 'script_outputs')
            os.makedirs(output_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = os.path.join(output_dir, f'{script_name}_{timestamp}.txt')
            
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(output)
                
                # Сохраняем только путь к файлу в сессии
                session[f'script_output_file_{script_name}'] = output_file
                session[f'script_output_time_{script_name}'] = timestamp
            except Exception as e:
                logger.error(f'Error saving script output to file: {str(e)}')
                session[f'script_output_{script_name}'] = output[:1000] if len(output) > 1000 else output
            
            output_preview = output[:500] if len(output) > 500 else output
            flash(f'Скрипт {script_name} выполнен успешно. Результаты сохранены.', 'success')
            logger.info(f'Admin ran script {script_name}:\n{output}')
        else:
            # Сохраняем ошибку в файл
            output_dir = os.path.join(project_root, 'logs', 'script_outputs')
            os.makedirs(output_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = os.path.join(output_dir, f'{script_name}_{timestamp}.txt')
            
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(output)
                
                session[f'script_output_file_{script_name}'] = output_file
                session[f'script_output_time_{script_name}'] = timestamp
            except Exception as e:
                logger.error(f'Error saving script output to file: {str(e)}')
                session[f'script_output_{script_name}'] = output[:1000] if len(output) > 1000 else output
            
            error_lines = output.split('\n')[:5]
            error_preview = '\n'.join(error_lines)
            flash(f'Скрипт {script_name} завершился с ошибкой. См. детали ниже.', 'error')
            logger.error(f'Script {script_name} failed:\n{output}')
            
    except subprocess.TimeoutExpired:
        flash(f'Скрипт {script_name} превысил время выполнения (10 минут)', 'error')
    except Exception as e:
        flash(f'Ошибка при запуске скрипта: {str(e)}', 'error')
        logger.error(f'Error running script {script_name}: {str(e)}')
    
    return redirect(url_for('admin.admin_tools'))

def run_script_with_params(script_name, params):
    """Запускает скрипт с параметрами"""
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
    
    return redirect(url_for('admin.admin_tools'))

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
        redirect_url = url_for('admin.admin_tools')
        if search_athlete or search_event:
            redirect_url += f'?search_athlete={search_athlete}&search_event={search_event}'
        return redirect(redirect_url)
        
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении участия: {str(e)}', 'error')
        logger.error(f'Error deleting participant {participant_id}: {str(e)}')
    
    return redirect(url_for('admin.admin_tools'))

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
            return redirect(url_for('admin.admin_tools'))
        
        # Удаляем спортсмена
        db.session.delete(athlete)
        db.session.commit()
        
        flash(f'Спортсмен "{athlete_name}" полностью удален из базы данных', 'success')
        logger.info(f'Admin deleted athlete {athlete_id} ({athlete_name}) completely')
        
        # Сохраняем параметры поиска если они были
        search_athlete_no_starts = request.form.get('search_athlete_no_starts', '')
        redirect_url = url_for('admin.admin_tools')
        if search_athlete_no_starts:
            redirect_url += f'?search_athlete_no_starts={search_athlete_no_starts}'
        return redirect(redirect_url)
        
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении спортсмена: {str(e)}', 'error')
        logger.error(f'Error deleting athlete {athlete_id}: {str(e)}')
    
    return redirect(url_for('admin.admin_tools'))

