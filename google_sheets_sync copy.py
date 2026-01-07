#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль для синхронизации данных с Google Sheets
"""

import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import logging
from app import app, db
from models import Athlete, Club, Category, Participant

logger = logging.getLogger(__name__)

# Настройки Google Sheets API
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

# ID основной Google Таблицы (всегда используется эта таблица)
DEFAULT_SPREADSHEET_ID = '1Db14waZDObeIra4JXm7kvb2oXQUA52_MhjqImgqFXSc'

def get_google_sheets_client():
    """Подключается к Google Sheets API"""
    try:
        import os
        
        # Путь к файлу с credentials (JSON)
        # Получаем абсолютный путь к файлу
        base_dir = os.path.dirname(os.path.abspath(__file__))
        credentials_path = os.path.join(base_dir, 'google_credentials.json')
        
        # Проверяем что файл существует
        if not os.path.exists(credentials_path):
            raise FileNotFoundError(f"Файл credentials не найден: {credentials_path}")
        
        # Проверяем права доступа
        if not os.access(credentials_path, os.R_OK):
            raise PermissionError(f"Нет прав на чтение файла: {credentials_path}")
        
        creds = Credentials.from_service_account_file(
            credentials_path,
            scopes=SCOPES
        )
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        logger.error(f"Ошибка подключения к Google Sheets: {e}")
        raise

def get_athletes_data():
    """Получает данные всех спортсменов из БД, сгруппированные по разрядам"""
    
    with app.app_context():
        from models import Event
        
        # Получаем всех спортсменов с их данными
        athletes_query = db.session.query(
            Athlete.id,
            Athlete.full_name_xml,
            Athlete.first_name,
            Athlete.last_name,
            Athlete.birth_date,
            Athlete.gender,
            Club.name.label('club_name'),
            Category.normalized_name.label('rank'),
            Event.name.label('event_name'),
            Event.begin_date.label('event_date'),
            Participant.pct_ppname.label('is_free')  # Отслеживаем бесплатные
        ).outerjoin(
            Club, Athlete.club_id == Club.id
        ).outerjoin(
            Participant, Athlete.id == Participant.athlete_id
        ).outerjoin(
            Category, Participant.category_id == Category.id
        ).outerjoin(
            Event, Participant.event_id == Event.id
        ).all()
        
        # Группируем по спортсменам
        athletes_dict = {}
        
        for row in athletes_query:
            athlete_id = row.id
            
            if athlete_id not in athletes_dict:
                full_name = row.full_name_xml or f"{row.last_name} {row.first_name}"
                
                athletes_dict[athlete_id] = {
                    'id': athlete_id,
                    'name': full_name,
                    'birth_date': row.birth_date.strftime('%d.%m.%Y') if row.birth_date else 'Не указана',
                    'gender': 'Ж' if row.gender == 'F' else 'М' if row.gender == 'M' else 'Пара' if row.gender == 'P' else '-',
                    'club': row.club_name or 'Не указан',
                    'ranks': set(),
                    'events': [],  # Список турниров (с отметками бесплатных)
                    'free_events': set(),  # Отдельно бесплатные турниры
                    'participations': 0,
                    'free_participations': 0
                }
            
            # Добавляем разряд
            if row.rank:
                athletes_dict[athlete_id]['ranks'].add(row.rank)
            
            # Добавляем турнир
            if row.event_name:
                # Форматируем дату турнира
                event_str = row.event_name
                if row.event_date:
                    event_str += f" ({row.event_date.strftime('%d.%m.%Y')})"
                
                # Помечаем бесплатные турниры текстом [БЕСПЛАТНО] вместо эмодзи
                is_free = row.is_free == 'БЕСП'
                if is_free:
                    event_str = f"[БЕСПЛАТНО] {event_str}"
                    athletes_dict[athlete_id]['free_events'].add(row.event_name)
                
                # Избегаем дубликатов
                if event_str not in athletes_dict[athlete_id]['events']:
                    athletes_dict[athlete_id]['events'].append(event_str)
        
        # Подсчитываем участия для каждого спортсмена
        for athlete_id in athletes_dict.keys():
            # Всего участий
            total_participations = Participant.query.filter_by(athlete_id=athlete_id).count()
            athletes_dict[athlete_id]['participations'] = total_participations
            
            # Бесплатных участий
            free_participations = Participant.query.filter_by(
                athlete_id=athlete_id,
                pct_ppname='БЕСП'
            ).count()
            athletes_dict[athlete_id]['free_participations'] = free_participations
            
            # Берем самый высокий разряд
            if athletes_dict[athlete_id]['ranks']:
                # Сортируем разряды по весу
                rank_weights = {
                    'МС': 1, 'КМС': 2,
                    '1 Спортивный': 3, '2 Спортивный': 4, '3 Спортивный': 5,
                    '1 Юношеский': 6, '2 Юношеский': 7, '3 Юношеский': 8,
                    'Юный Фигурист': 9, 'Дебют': 10, 'Новичок': 11
                }
                
                def get_rank_weight(rank):
                    base_rank = rank.split(',')[0].strip()
                    return rank_weights.get(base_rank, 99)
                
                best_rank = min(athletes_dict[athlete_id]['ranks'], key=get_rank_weight)
                athletes_dict[athlete_id]['rank'] = best_rank
            else:
                athletes_dict[athlete_id]['rank'] = 'Без разряда'
            
            # Форматируем список турниров (через перенос строки для Google Sheets)
            if athletes_dict[athlete_id]['events']:
                # Сортируем: сначала бесплатные ([БЕСПЛАТНО]), потом остальные
                events_sorted = sorted(athletes_dict[athlete_id]['events'], key=lambda x: (not x.startswith('[БЕСПЛАТНО]'), x))
                athletes_dict[athlete_id]['events_str'] = '\n'.join(events_sorted)
            else:
                athletes_dict[athlete_id]['events_str'] = '-'
        
        # Группируем по разрядам
        by_rank = {}
        
        for athlete in athletes_dict.values():
            rank = athlete['rank']
            
            if rank not in by_rank:
                by_rank[rank] = []
            
            by_rank[rank].append(athlete)
        
        # Сортируем спортсменов внутри каждого разряда по имени
        for rank in by_rank:
            by_rank[rank].sort(key=lambda x: x['name'])
        
        return by_rank

def get_schools_analysis_data():
    """Получает анализ по школам: статистика и список спортсменов"""
    
    with app.app_context():
        from models import Event
        
        # Получаем все школы с их спортсменами
        schools_query = db.session.query(
            Club.id,
            Club.name,
            Athlete.id.label('athlete_id'),
            Athlete.full_name_xml,
            Athlete.first_name,
            Athlete.last_name,
            Athlete.birth_date,
            Athlete.gender,
            Category.normalized_name.label('rank'),
            Event.name.label('event_name'),
            Event.begin_date.label('event_date'),
            Participant.pct_ppname.label('is_free')  # Отслеживаем бесплатные
        ).outerjoin(
            Athlete, Club.id == Athlete.club_id
        ).outerjoin(
            Participant, Athlete.id == Participant.athlete_id
        ).outerjoin(
            Category, Participant.category_id == Category.id
        ).outerjoin(
            Event, Participant.event_id == Event.id
        ).all()
        
        # Группируем по школам
        schools_dict = {}
        
        for row in schools_query:
            club_id = row.id
            club_name = row.name or 'Без школы'
            
            if club_id not in schools_dict:
                schools_dict[club_id] = {
                    'name': club_name,
                    'athletes': {},
                    'total_athletes': 0,
                    'total_participations': 0,
                    'free_participations': 0,
                    'paid_participations': 0
                }
            
            # Добавляем спортсмена
            athlete_id = row.athlete_id
            if athlete_id and athlete_id not in schools_dict[club_id]['athletes']:
                full_name = row.full_name_xml or f"{row.last_name} {row.first_name}"
                
                schools_dict[club_id]['athletes'][athlete_id] = {
                    'name': full_name,
                    'birth_date': row.birth_date.strftime('%d.%m.%Y') if row.birth_date else '-',
                    'gender': 'Ж' if row.gender == 'F' else 'М' if row.gender == 'M' else 'Пара' if row.gender == 'P' else '-',
                    'rank': row.rank or 'Без разряда',
                    'events': [],  # Список турниров (с отметками бесплатных)
                    'free_events': set(),  # Отдельно бесплатные турниры
                    'participations': 0,
                    'free_participations': 0
                }
            
            # Добавляем турнир
            if athlete_id and row.event_name:
                event_str = row.event_name
                if row.event_date:
                    event_str += f" ({row.event_date.strftime('%d.%m.%Y')})"
                
                # Помечаем бесплатные турниры текстом [БЕСПЛАТНО] вместо эмодзи
                is_free = row.is_free == 'БЕСП'
                if is_free:
                    event_str = f"[БЕСПЛАТНО] {event_str}"
                    schools_dict[club_id]['athletes'][athlete_id]['free_events'].add(row.event_name)
                
                # Избегаем дубликатов
                if event_str not in schools_dict[club_id]['athletes'][athlete_id]['events']:
                    schools_dict[club_id]['athletes'][athlete_id]['events'].append(event_str)
        
        # Подсчитываем статистику для каждой школы и каждого спортсмена
        for club_id in schools_dict.keys():
            club = Club.query.get(club_id)
            if club:
                # Количество спортсменов
                athlete_count = Athlete.query.filter_by(club_id=club_id).count()
                schools_dict[club_id]['total_athletes'] = athlete_count
                
                # Получаем всех спортсменов школы
                athletes = Athlete.query.filter_by(club_id=club_id).all()
                athlete_ids = [a.id for a in athletes]
                
                # Всего участий
                total_participations = Participant.query.filter(
                    Participant.athlete_id.in_(athlete_ids)
                ).count()
                schools_dict[club_id]['total_participations'] = total_participations
                
                # Бесплатных участий
                free_participations = Participant.query.filter(
                    Participant.athlete_id.in_(athlete_ids),
                    Participant.pct_ppname == 'БЕСП'
                ).count()
                schools_dict[club_id]['free_participations'] = free_participations
                
                # Платных участий
                schools_dict[club_id]['paid_participations'] = total_participations - free_participations
                
                # Подсчитываем статистику для КАЖДОГО спортсмена
                for athlete_id in schools_dict[club_id]['athletes'].keys():
                    # Всего участий спортсмена
                    athlete_participations = Participant.query.filter_by(athlete_id=athlete_id).count()
                    schools_dict[club_id]['athletes'][athlete_id]['participations'] = athlete_participations
                    
                    # Бесплатных участий спортсмена
                    athlete_free = Participant.query.filter_by(
                        athlete_id=athlete_id,
                        pct_ppname='БЕСП'
                    ).count()
                    schools_dict[club_id]['athletes'][athlete_id]['free_participations'] = athlete_free
                    
                    # Форматируем список турниров (бесплатные [БЕСПЛАТНО] в начале)
                    if schools_dict[club_id]['athletes'][athlete_id]['events']:
                        events_sorted = sorted(schools_dict[club_id]['athletes'][athlete_id]['events'], key=lambda x: (not x.startswith('[БЕСПЛАТНО]'), x))
                        schools_dict[club_id]['athletes'][athlete_id]['events_str'] = '\n'.join(events_sorted)
                    else:
                        schools_dict[club_id]['athletes'][athlete_id]['events_str'] = '-'
        
        # Сортируем школы по количеству спортсменов (по убыванию)
        sorted_schools = sorted(
            schools_dict.values(),
            key=lambda x: x['total_athletes'],
            reverse=True
        )
        
        return sorted_schools

def get_events_report_data():
    """Формирует сводные данные по турнирам для отчета в Google Sheets"""
    
    # Разряды, которые нужно исключить из отчета
    excluded_ranks = {
        'МС, Женщины',
        'МС, Мужчины',
        'КМС, Девушки',
        'КМС, Юноши',
        'КМС, Пары',
        'КМС, Танцы'
    }
    
    # Порядок разрядов для вывода внутри турнира
    rank_order = [
        'МС, Женщины', 'МС, Мужчины', 'МС, Пары', 'МС, Танцы',
        'КМС, Девушки', 'КМС, Юноши', 'КМС, Пары', 'КМС, Танцы',
        '1 Спортивный, Девочки', '1 Спортивный, Мальчики',
        '2 Спортивный, Девочки', '2 Спортивный, Мальчики',
        '3 Спортивный, Девочки', '3 Спортивный, Мальчики',
        '1 Юношеский, Девочки', '1 Юношеский, Мальчики',
        '2 Юношеский, Девочки', '2 Юношеский, Мальчики',
        '3 Юношеский, Девочки', '3 Юношеский, Мальчики',
        'Юный Фигурист, Девочки', 'Юный Фигурист, Мальчики',
        'Дебют, Девочки', 'Дебют, Мальчики',
        'Новичок, Девочки', 'Новичок, Мальчики',
        'Без разряда'
    ]
    rank_priority = {rank: index for index, rank in enumerate(rank_order)}
    
    with app.app_context():
        from models import Event, Category
        
        participants_query = db.session.query(
            Event.id.label('event_id'),
            Event.name.label('event_name'),
            Event.begin_date.label('event_date'),
            Participant.athlete_id,
            Participant.pct_ppname,
            Category.normalized_name.label('rank')
        ).join(
            Participant, Participant.event_id == Event.id
        ).join(
            Category, Participant.category_id == Category.id
        ).filter(
            db.or_(
                Category.normalized_name.is_(None),
                Category.normalized_name.notin_(excluded_ranks)
            )
        ).all()
        
        events_map = {}
        
        for row in participants_query:
            event_id = row.event_id
            
            if event_id not in events_map:
                events_map[event_id] = {
                    'event_name': row.event_name,
                    'event_date': row.event_date,
                    'athletes': set(),
                    'free_athletes': set(),
                    'rank_stats': {}
                }
            
            event_entry = events_map[event_id]
            event_entry['athletes'].add(row.athlete_id)
            
            # Группировка по разрядам
            rank_name = (row.rank or 'Без разряда').strip()
            
            if rank_name not in event_entry['rank_stats']:
                event_entry['rank_stats'][rank_name] = {
                    'athletes': set(),
                    'free_athletes': set()
                }
            
            event_entry['rank_stats'][rank_name]['athletes'].add(row.athlete_id)
            
            if row.pct_ppname == 'БЕСП':
                event_entry['free_athletes'].add(row.athlete_id)
                event_entry['rank_stats'][rank_name]['free_athletes'].add(row.athlete_id)
        
        events_data = []
        
        for event_id, event_info in events_map.items():
            total_children = len(event_info['athletes'])
            
            if total_children == 0:
                continue
            
            free_children = len(event_info['free_athletes'])
            rank_stats_prepared = []
            
            for rank_name, rank_sets in event_info['rank_stats'].items():
                total_rank_children = len(rank_sets['athletes'])
                if total_rank_children == 0:
                    continue
                
                rank_stats_prepared.append({
                    'rank': rank_name,
                    'total_children': total_rank_children,
                    'free_children': len(rank_sets['free_athletes'])
                })
            
            # Сортируем разряды согласно приоритету (неизвестные в конце по алфавиту)
            rank_stats_prepared.sort(
                key=lambda item: (
                    rank_priority.get(item['rank'], len(rank_order)),
                    item['rank']
                )
            )
            
            date_display = event_info['event_date'].strftime('%d.%m.%Y') if event_info['event_date'] else 'Дата не указана'
            
            events_data.append({
                'event_id': event_id,
                'event_name': event_info['event_name'],
                'event_date': event_info['event_date'],
                'event_date_display': date_display,
                'total_children': total_children,
                'free_children': free_children,
                'rank_stats': rank_stats_prepared
            })
        
        # Сортируем турниры по дате (новые сверху), без даты в конце
        events_data.sort(key=lambda x: (x['event_date'] is None, x['event_date']), reverse=True)
        
        totals = {
            'total_children': sum(event['total_children'] for event in events_data),
            'free_children': sum(event['free_children'] for event in events_data)
        }
        
        return {
            'events': events_data,
            'totals': totals,
            'rank_order': rank_order
        }

def export_to_google_sheets(spreadsheet_id=None):
    """
    Экспортирует данные в Google Sheets
    
    Args:
        spreadsheet_id: ID Google таблицы (если None, используется DEFAULT_SPREADSHEET_ID)
    
    Returns:
        dict: {'success': bool, 'url': str, 'message': str}
    """
    api_requests_count = 0  # Счётчик API запросов для отладки
    
    try:
        # Подключаемся к Google Sheets
        logger.info("Подключение к Google Sheets...")
        client = get_google_sheets_client()
        
        # Используем DEFAULT_SPREADSHEET_ID если не передан другой ID
        if not spreadsheet_id:
            spreadsheet_id = DEFAULT_SPREADSHEET_ID
            logger.info(f"Используется основная таблица: {spreadsheet_id}")
        
        # Открываем таблицу
        logger.info(f"Открытие таблицы: {spreadsheet_id}")
        spreadsheet = client.open_by_key(spreadsheet_id)
        
        # Получаем данные
        logger.info("Получение данных из БД...")
        athletes_by_rank = get_athletes_data()
        
        # Получаем первый лист (или создаем)
        try:
            worksheet = spreadsheet.sheet1
            sheet_id = worksheet.id
            
            # Переименовываем первый лист
            try:
                worksheet.update_title("Список спортсменов")
                logger.info("Первый лист переименован в 'Список спортсменов'")
            except Exception as e:
                logger.debug(f"Переименование первого листа: {e}")
            
            # ВАЖНО: Полная очистка листа (данные + форматирование + объединения)
            logger.info("Очистка первого листа...")
            
            # 1. Полная очистка через batch_update (данные + форматирование + условное форматирование)
            try:
                clear_requests = [
                    # Разъединяем все ячейки
                    {
                    'unmergeCells': {
                        'range': {
                            'sheetId': sheet_id,
                            'startRowIndex': 0,
                                'endRowIndex': 5000,  # Увеличено с 1000 до 5000
                            'startColumnIndex': 0,
                            'endColumnIndex': 10
                        }
                    }
                    },
                    # Очищаем ВСЁ форматирование (включая фоновые цвета, шрифты и т.д.)
                    {
                        'updateCells': {
                            'range': {
                                'sheetId': sheet_id,
                                'startRowIndex': 0,
                                'endRowIndex': 5000,  # Увеличено с 1000 до 5000
                                'startColumnIndex': 0,
                                'endColumnIndex': 10
                            },
                            'fields': 'userEnteredFormat,userEnteredValue'
                        }
                    },
                    # Удаляем ВСЕ правила условного форматирования
                    {
                        'setBasicFilter': {
                            'filter': {
                                'range': {
                                    'sheetId': sheet_id
                                }
                            }
                        }
                    }
                ]
                spreadsheet.batch_update({'requests': clear_requests})
                
                # Дополнительно: очищаем условное форматирование через отдельный запрос
                try:
                    # Получаем текущие правила условного форматирования
                    sheet_metadata = spreadsheet.fetch_sheet_metadata({'includeGridData': False})
                    for sheet in sheet_metadata['sheets']:
                        if sheet['properties']['sheetId'] == sheet_id:
                            # Очищаем условное форматирование, если оно есть
                            if 'conditionalFormats' in sheet:
                                clear_conditional = {
                                    'updateConditionalFormatRule': {
                                        'sheetId': sheet_id,
                                        'index': 0,
                                        'rule': None
                                    }
                                }
                                # Удаляем все правила
                                for _ in range(len(sheet.get('conditionalFormats', []))):
                                    try:
                                        spreadsheet.batch_update({'requests': [{
                                            'deleteConditionalFormatRule': {
                                                'sheetId': sheet_id,
                                                'index': 0
                                            }
                                        }]})
                                    except:
                                        break
                except Exception as e:
                    logger.debug(f"Очистка условного форматирования: {e}")
                
                logger.info("[OK] Лист полностью очищен (данные + форматирование + условное форматирование + объединения)")
            except Exception as e:
                logger.warning(f"Ошибка при очистке: {e}, пробуем обычную очистку...")
                worksheet.clear()
            
        except:
            worksheet = spreadsheet.add_worksheet(title="Спортсмены", rows=5000, cols=10)
            sheet_id = worksheet.id
        
        # Заголовок таблицы
        current_row = 1
        
        # Заголовок документа
        worksheet.update_acell(f'A{current_row}', 
            f'СПОРТСМЕНЫ ПО РАЗРЯДАМ - Обновлено: {datetime.now().strftime("%d.%m.%Y %H:%M")}')
        
        # Форматирование заголовка
        worksheet.format(f'A{current_row}:G{current_row}', {
            'textFormat': {'bold': True, 'fontSize': 14},
            'horizontalAlignment': 'CENTER',
            'backgroundColor': {'red': 0.29, 'green': 0.53, 'blue': 0.91}
        })
        
        # Объединение главного заголовка
        try:
            main_header_merge = {
                'mergeCells': {
                    'range': {
                        'sheetId': sheet_id,
                        'startRowIndex': 0,  # строка 1 в Google Sheets = индекс 0
                        'endRowIndex': 1,
                        'startColumnIndex': 0,  # колонка A
                        'endColumnIndex': 7  # колонка G (не включая)
                    },
                    'mergeType': 'MERGE_ALL'
                }
            }
            spreadsheet.batch_update({'requests': [main_header_merge]})
            logger.info("Главный заголовок объединен и центрирован")
        except Exception as e:
            logger.warning(f"Ошибка объединения главного заголовка: {e}")
        
        current_row += 2
        
        # Порядок разрядов
        rank_order = [
            'МС, Женщины', 'МС, Мужчины',
            'КМС, Девушки', 'КМС, Юноши',
            '1 Спортивный, Девочки', '1 Спортивный, Мальчики',
            '2 Спортивный, Девочки', '2 Спортивный, Мальчики',
            '3 Спортивный, Девочки', '3 Спортивный, Мальчики',
            '1 Юношеский, Девочки', '1 Юношеский, Мальчики',
            '2 Юношеский, Девочки', '2 Юношеский, Мальчики',
            '3 Юношеский, Девочки', '3 Юношеский, Мальчики',
            'Юный Фигурист, Девочки', 'Юный Фигурист, Мальчики',
            'Дебют, Девочки', 'Дебют, Мальчики',
            'Новичок, Девочки', 'Новичок, Мальчики',
        ]
        
        # Добавляем остальные разряды (которых нет в списке)
        for rank in athletes_by_rank.keys():
            if rank not in rank_order:
                rank_order.append(rank)
        
        # BATCH-ЗАПИСЬ: Собираем ВСЕ данные сразу, потом пишем одним пакетом
        all_data = []  # Все данные для записи
        format_requests = []  # Все форматирования
        merge_requests = []  # Объединения ячеек для заголовков
        
        start_row = current_row
        
        for rank in rank_order:
            if rank not in athletes_by_rank:
                continue
            
            athletes = athletes_by_rank[rank]
            
            if not athletes:
                continue
            
            # Заголовок разряда
            all_data.append([rank.upper(), '', '', '', '', '', ''])
            
            # Запоминаем для форматирования заголовка
            format_requests.append({
                'range': f'A{current_row}:G{current_row}',
                'format': {
                    'textFormat': {'bold': True, 'fontSize': 12},
                    'horizontalAlignment': 'CENTER',
                    'backgroundColor': {'red': 0.85, 'green': 0.92, 'blue': 0.83}
                }
            })
            # Объединяем ячейки для заголовка разряда
            merge_requests.append(f'A{current_row}:G{current_row}')
            
            current_row += 1
            
            # Шапка таблицы
            headers = ['№', 'ФИО', 'Дата рождения', 'Школа', 'Турниры', 'Участий', 'Бесплатно']
            all_data.append(headers)
            
            # Форматирование шапки
            format_requests.append({
                'range': f'A{current_row}:G{current_row}',
                'format': {
                    'textFormat': {'bold': True},
                    'horizontalAlignment': 'CENTER',
                    'backgroundColor': {'red': 0.8, 'green': 0.8, 'blue': 0.8}
                }
            })
            
            current_row += 1
            
            # Данные спортсменов
            for i, athlete in enumerate(athletes, 1):
                row_data = [
                    i,
                    athlete['name'],
                    athlete['birth_date'],
                    athlete['club'],
                    athlete.get('events_str', '-'),  # Турниры (с 🆓 эмодзи)
                    athlete['participations'],
                    athlete['free_participations']
                ]
                
                all_data.append(row_data)
                
                # НОВАЯ ЛОГИКА: Запоминаем конкретные ячейки для подсветки
                # Вместо зелёной строки - подсвечиваем только ячейки
                if athlete['free_participations'] > 0:
                    # Определяем оттенок зелёного по количеству бесплатных
                    if athlete['free_participations'] >= 4:
                        green_color = {'red': 0.50, 'green': 0.75, 'blue': 0.50}  # Ярко-зелёный
                    elif athlete['free_participations'] >= 2:
                        green_color = {'red': 0.66, 'green': 0.84, 'blue': 0.66}  # Средне-зелёный
                    else:
                        green_color = {'red': 0.79, 'green': 0.89, 'blue': 0.79}  # Светло-зелёный
                    
                    # Подсвечиваем ТОЛЬКО ячейку с количеством бесплатных (колонка G)
                    format_requests.append({
                        'range': f'G{current_row}',
                        'format': {
                            'backgroundColor': green_color,
                            'textFormat': {'bold': True}
                        }
                    })
                    
                    # Подсвечиваем ячейку с турнирами (колонка E) если есть бесплатные - ЯРКИЙ ЗЕЛЁНЫЙ
                    format_requests.append({
                        'range': f'E{current_row}',
                        'format': {
                            'backgroundColor': {'red': 0.85, 'green': 0.95, 'blue': 0.85},  # Светло-зелёный фон (видимый)
                            'textFormat': {'foregroundColor': {'red': 0.0, 'green': 0.5, 'blue': 0.0}}  # Тёмно-зелёный текст
                        }
                    })
                
                current_row += 1
            
            # Пустая строка между разрядами
            all_data.append(['', '', '', '', '', '', ''])
            current_row += 1
        
        # ЗАПИСЫВАЕМ ВСЕ ДАННЫЕ ОДНИМ ЗАПРОСОМ!
        logger.info(f"Запись {len(all_data)} строк одним пакетом...")
        if all_data:
            worksheet.update(f'A{start_row}:G{current_row-1}', all_data)
        
        # ИСПОЛЬЗУЕМ BATCH_FORMAT - ВСЁ ФОРМАТИРОВАНИЕ ОДНИМ ЗАПРОСОМ!
        logger.info(f"Применение форматирования батчем (1 запрос)...")
        
        # ПРИМЕНЯЕМ ВСЁ ФОРМАТИРОВАНИЕ ОДНИМ BATCH-ЗАПРОСОМ!
        # (форматирование уже собрано в format_requests, включая точечную подсветку)
        if format_requests:
            batch_format_data = []
            for fmt in format_requests:
                batch_format_data.append({
                    'range': fmt['range'],
                    'format': fmt['format']
                })
            
            worksheet.batch_format(batch_format_data)
            logger.info(f"[OK] Применено {len(batch_format_data)} форматов одним запросом!")
        
        # ОБЪЕДИНЯЕМ ЯЧЕЙКИ для заголовков разрядов
        if merge_requests:
            logger.info(f"Объединение {len(merge_requests)} заголовков разрядов...")
            merge_batch_requests = []
            for merge_range in merge_requests:
                # Парсим диапазон (например, 'A3:G3')
                start_cell, end_cell = merge_range.split(':')
                
                # Извлекаем row и column из start_cell
                import re
                match_start = re.match(r'([A-Z]+)(\d+)', start_cell)
                match_end = re.match(r'([A-Z]+)(\d+)', end_cell)
                
                if match_start and match_end:
                    start_col = ord(match_start.group(1)) - ord('A')
                    start_row = int(match_start.group(2)) - 1
                    end_col = ord(match_end.group(1)) - ord('A') + 1
                    end_row = int(match_end.group(2))
                    
                    merge_batch_requests.append({
                        'mergeCells': {
                            'range': {
                                'sheetId': sheet_id,
                                'startRowIndex': start_row,
                                'endRowIndex': end_row,
                                'startColumnIndex': start_col,
                                'endColumnIndex': end_col
                            },
                            'mergeType': 'MERGE_ALL'
                        }
                    })
            
            if merge_batch_requests:
                try:
                    spreadsheet.batch_update({'requests': merge_batch_requests})
                    logger.info(f"[OK] Объединено {len(merge_batch_requests)} заголовков!")
                except Exception as e:
                    logger.warning(f"Ошибка объединения ячеек: {e}")
        
        # УСТАНАВЛИВАЕМ ШИРИНУ КОЛОНОК БАТЧЕМ (одним запросом!)
        logger.info("Установка ширины колонок батчем...")
        column_widths = [
            ('A', 50),   # №
            ('B', 300),  # ФИО
            ('C', 120),  # Дата рождения (уменьшена)
            ('D', 400),  # Школа (увеличена!)
            ('E', 350),  # Турниры (увеличена! с 🆓 эмодзи)
            ('F', 80),   # Участий (уменьшена)
            ('G', 100)   # Бесплатно (уменьшена)
        ]
        
        width_batch_requests = []
        sheet_id = worksheet.id
        
        for col_letter, width in column_widths:
            col_index = ord(col_letter) - ord('A')
            width_batch_requests.append({
                'updateDimensionProperties': {
                    'range': {
                        'sheetId': sheet_id,
                        'dimension': 'COLUMNS',
                        'startIndex': col_index,
                        'endIndex': col_index + 1
                    },
                    'properties': {
                        'pixelSize': width
                    },
                    'fields': 'pixelSize'
                }
            })
        
        if width_batch_requests:
            body = {'requests': width_batch_requests}
            spreadsheet.batch_update(body)
            logger.info(f"[OK] Установлена ширина {len(column_widths)} колонок одним запросом!")
        
        # УСЛОВНОЕ ФОРМАТИРОВАНИЕ: Выделение дубликатов ФИО
        logger.info("Добавление условного форматирования для дубликатов...")
        try:
            # Определяем диапазон данных (колонка B, начиная со строки 3)
            # Строка 1 - главный заголовок, строка 3 - начало данных
            conditional_format_request = {
                'addConditionalFormatRule': {
                    'rule': {
                        'ranges': [{
                            'sheetId': sheet_id,
                            'startRowIndex': 2,  # Строка 3 (индекс 2)
                            'endRowIndex': 5000,  # До 5000 строки
                            'startColumnIndex': 1,  # Колонка B (индекс 1)
                            'endColumnIndex': 2  # Только колонка B
                        }],
                        'booleanRule': {
                            'condition': {
                                'type': 'CUSTOM_FORMULA',
                                'values': [{
                                    'userEnteredValue': '=COUNTIF($B:$B, B3)>1'
                                }]
                            },
                            'format': {
                                'backgroundColor': {
                                    'red': 1.0,
                                    'green': 0.4,
                                    'blue': 0.8
                                }
                            }
                        }
                    },
                    'index': 0
                }
            }
            spreadsheet.batch_update({'requests': [conditional_format_request]})
            logger.info("[OK] Условное форматирование для дубликатов добавлено!")
        except Exception as e:
            logger.warning(f"Ошибка добавления условного форматирования: {e}")
        
        # Замораживаем первую строку
        worksheet.freeze(rows=1)
        
        logger.info("[OK] Первый лист 'Спортсмены по разрядам' создан!")
        
        # ========================================
        # ВТОРОЙ ЛИСТ: АНАЛИЗ ПО ШКОЛАМ
        # ========================================
        
        logger.info("Создание второго листа 'Анализ по школам'...")
        schools_data = get_schools_analysis_data()
        
        # Создаём или получаем второй лист
        try:
            worksheet2 = spreadsheet.worksheet("Анализ по школам")
            sheet_id2 = worksheet2.id
            
            # ВАЖНО: Полная очистка листа (данные + форматирование + объединения)
            logger.info("Очистка второго листа...")
            
            # 1. Полная очистка через batch_update (данные + форматирование + условное форматирование)
            try:
                clear_requests2 = [
                    # Разъединяем все ячейки
                    {
                    'unmergeCells': {
                        'range': {
                            'sheetId': sheet_id2,
                            'startRowIndex': 0,
                                'endRowIndex': 5000,  # Увеличено с 2000 до 5000
                            'startColumnIndex': 0,
                            'endColumnIndex': 10
                        }
                    }
                    },
                    # Очищаем ВСЁ форматирование (включая фоновые цвета, шрифты и т.д.)
                    {
                        'updateCells': {
                            'range': {
                                'sheetId': sheet_id2,
                                'startRowIndex': 0,
                                'endRowIndex': 5000,  # Увеличено с 2000 до 5000
                                'startColumnIndex': 0,
                                'endColumnIndex': 10
                            },
                            'fields': 'userEnteredFormat,userEnteredValue'
                        }
                    }
                ]
                spreadsheet.batch_update({'requests': clear_requests2})
                
                # Дополнительно: очищаем условное форматирование второго листа
                try:
                    sheet_metadata = spreadsheet.fetch_sheet_metadata({'includeGridData': False})
                    for sheet in sheet_metadata['sheets']:
                        if sheet['properties']['sheetId'] == sheet_id2:
                            if 'conditionalFormats' in sheet:
                                # Удаляем все правила условного форматирования
                                for _ in range(len(sheet.get('conditionalFormats', []))):
                                    try:
                                        spreadsheet.batch_update({'requests': [{
                                            'deleteConditionalFormatRule': {
                                                'sheetId': sheet_id2,
                                                'index': 0
                                            }
                                        }]})
                                    except:
                                        break
                except Exception as e:
                    logger.debug(f"Очистка условного форматирования второго листа: {e}")
                
                logger.info("[OK] Второй лист полностью очищен (данные + форматирование + условное форматирование + объединения)")
            except Exception as e:
                logger.warning(f"Ошибка при очистке второго листа: {e}, пробуем обычную очистку...")
                worksheet2.clear()
            
        except:
            worksheet2 = spreadsheet.add_worksheet(title="Анализ по школам", rows=5000, cols=10)
            sheet_id2 = worksheet2.id
        
        # Заголовок второго листа
        worksheet2.update_acell('A1', 
            f'АНАЛИЗ ПО ШКОЛАМ - Обновлено: {datetime.now().strftime("%d.%m.%Y %H:%M")}')
        worksheet2.format('A1:F1', {
            'textFormat': {'bold': True, 'fontSize': 14},
            'horizontalAlignment': 'CENTER',
            'backgroundColor': {'red': 0.29, 'green': 0.53, 'blue': 0.91}
        })
        
        # Объединение главного заголовка второго листа
        try:
            main_header_merge2 = {
                'mergeCells': {
                    'range': {
                        'sheetId': sheet_id2,
                        'startRowIndex': 0,  # строка 1 в Google Sheets = индекс 0
                        'endRowIndex': 1,
                        'startColumnIndex': 0,  # колонка A
                        'endColumnIndex': 6  # колонка F (не включая)
                    },
                    'mergeType': 'MERGE_ALL'
                }
            }
            spreadsheet.batch_update({'requests': [main_header_merge2]})
            logger.info("Главный заголовок второго листа объединен и центрирован")
        except Exception as e:
            logger.warning(f"Ошибка объединения главного заголовка второго листа: {e}")
        
        # Формируем данные для второго листа
        schools_all_data = []
        schools_format_requests = []
        schools_merge_requests = []  # Объединения ячеек для школ
        current_row = 3
        
        for school in schools_data:
            # Заголовок школы с статистикой
            school_header = f"{school['name']} | Всего: {school['total_athletes']} | Участий: {school['total_participations']} | Бесплатно: {school['free_participations']} | Платно: {school['paid_participations']}"
            schools_all_data.append([school_header, '', '', '', '', ''])
            
            # Форматирование заголовка школы (СИНИЙ ФОН)
            schools_format_requests.append({
                'range': f'A{current_row}:F{current_row}',
                'format': {
                    'textFormat': {'bold': True, 'fontSize': 13},
                    'horizontalAlignment': 'LEFT',
                    'backgroundColor': {'red': 0.67, 'green': 0.82, 'blue': 0.95}  # Голубой
                }
            })
            # Объединяем ячейки для заголовка школы
            schools_merge_requests.append(f'A{current_row}:F{current_row}')
            current_row += 1
            
            # Группируем спортсменов по разрядам
            athletes_by_rank = {}
            for athlete in school['athletes'].values():
                rank = athlete['rank']
                if rank not in athletes_by_rank:
                    athletes_by_rank[rank] = []
                athletes_by_rank[rank].append(athlete)
            
            # Порядок разрядов (тот же что на первом листе)
            rank_order = [
                'МС, Женщины', 'МС, Мужчины',
                'КМС, Девушки', 'КМС, Юноши',
                '1 Спортивный, Девочки', '1 Спортивный, Мальчики',
                '2 Спортивный, Девочки', '2 Спортивный, Мальчики',
                '3 Спортивный, Девочки', '3 Спортивный, Мальчики',
                '1 Юношеский, Девочки', '1 Юношеский, Мальчики',
                '2 Юношеский, Девочки', '2 Юношеский, Мальчики',
                '3 Юношеский, Девочки', '3 Юношеский, Мальчики',
                'Юный Фигурист, Девочки', 'Юный Фигурист, Мальчики',
                'Дебют, Девочки', 'Дебют, Мальчики',
                'Новичок, Девочки', 'Новичок, Мальчики',
                'Без разряда'
            ]
            
            # Добавляем остальные разряды (которых нет в списке)
            for rank in athletes_by_rank.keys():
                if rank not in rank_order:
                    rank_order.append(rank)
            
            # Выводим по разрядам
            for rank in rank_order:
                if rank not in athletes_by_rank:
                    continue
                
                athletes_list = athletes_by_rank[rank]
                if not athletes_list:
                    continue
                
                athletes_list.sort(key=lambda x: x['name'])
                
                # ЗАГОЛОВОК РАЗРЯДА (объединённая ячейка)
                schools_all_data.append([f"  {rank}", '', '', '', '', ''])
                schools_format_requests.append({
                    'range': f'A{current_row}:F{current_row}',
                    'format': {
                        'textFormat': {'bold': True, 'fontSize': 11, 'italic': True},
                        'horizontalAlignment': 'LEFT',
                        'backgroundColor': {'red': 0.95, 'green': 0.95, 'blue': 0.95}  # Светло-серый
                    }
                })
                # Объединяем ячейки для заголовка разряда
                schools_merge_requests.append(f'A{current_row}:F{current_row}')
                current_row += 1
                
                # Шапка таблицы
                headers = ['№', 'ФИО', 'Дата рождения', 'Турниры', 'Участий', 'Бесплатно']
                schools_all_data.append(headers)
                schools_format_requests.append({
                    'range': f'A{current_row}:F{current_row}',
                    'format': {
                        'textFormat': {'bold': True, 'fontSize': 9},
                        'horizontalAlignment': 'CENTER',
                        'backgroundColor': {'red': 0.85, 'green': 0.85, 'blue': 0.85}
                    }
                })
                current_row += 1
                
                # Спортсмены разряда
                for i, athlete in enumerate(athletes_list, 1):
                    row_data = [
                        i,
                        athlete['name'],
                        athlete['birth_date'],
                        athlete.get('events_str', '-'),
                        athlete.get('participations', 0),
                        athlete.get('free_participations', 0)
                    ]
                    schools_all_data.append(row_data)
                    
                    # ТОЧЕЧНАЯ ПОДСВЕТКА: подсвечиваем только ячейки
                    if athlete.get('free_participations', 0) > 0:
                        # Определяем оттенок зелёного
                        free_count = athlete.get('free_participations', 0)
                        if free_count >= 4:
                            green_color = {'red': 0.50, 'green': 0.75, 'blue': 0.50}  # Ярко-зелёный
                        elif free_count >= 2:
                            green_color = {'red': 0.66, 'green': 0.84, 'blue': 0.66}  # Средне-зелёный
                        else:
                            green_color = {'red': 0.79, 'green': 0.89, 'blue': 0.79}  # Светло-зелёный
                        
                        # Подсвечиваем ячейку с количеством бесплатных (колонка F)
                        schools_format_requests.append({
                            'range': f'F{current_row}',
                            'format': {
                                'backgroundColor': green_color,
                                'textFormat': {'bold': True}
                            }
                        })
                        
                        # Подсвечиваем ячейку с турнирами (колонка D) - ЯРКИЙ ЗЕЛЁНЫЙ
                        schools_format_requests.append({
                            'range': f'D{current_row}',
                            'format': {
                                'backgroundColor': {'red': 0.85, 'green': 0.95, 'blue': 0.85},  # Светло-зелёный фон (видимый)
                                'textFormat': {'foregroundColor': {'red': 0.0, 'green': 0.5, 'blue': 0.0}}  # Тёмно-зелёный текст
                            }
                        })
                    
                    current_row += 1
            
            # Пустая строка между школами
            schools_all_data.append(['', '', '', '', '', ''])
            current_row += 1
        
        # ЗАПИСЫВАЕМ ВСЕ ДАННЫЕ ВТОРОГО ЛИСТА ОДНИМ ЗАПРОСОМ!
        logger.info(f"Запись {len(schools_all_data)} строк для школ одним пакетом...")
        if schools_all_data:
            worksheet2.update(f'A3:F{current_row}', schools_all_data)
        
        # ФОРМАТИРОВАНИЕ ВТОРОГО ЛИСТА (точечная подсветка уже в schools_format_requests)
        logger.info("Применение форматирования для второго листа...")
        if schools_format_requests:
            schools_batch_format_data = []
            for fmt in schools_format_requests:
                schools_batch_format_data.append({
                    'range': fmt['range'],
                    'format': fmt['format']
                })
            
            worksheet2.batch_format(schools_batch_format_data)
            logger.info(f"[OK] Применено {len(schools_batch_format_data)} форматов для второго листа!")
        
        # ОБЪЕДИНЕНИЕ ЯЧЕЕК ДЛЯ ВТОРОГО ЛИСТА (школы и разряды)
        if schools_merge_requests:
            logger.info(f"Объединение {len(schools_merge_requests)} заголовков школ и разрядов...")
            schools_merge_batch_requests = []
            for merge_range in schools_merge_requests:
                # Парсим диапазон (например, 'A3:F3')
                start_cell, end_cell = merge_range.split(':')
                
                # Извлекаем row и column из start_cell
                import re
                match_start = re.match(r'([A-Z]+)(\d+)', start_cell)
                match_end = re.match(r'([A-Z]+)(\d+)', end_cell)
                
                if match_start and match_end:
                    start_col = ord(match_start.group(1)) - ord('A')
                    start_row = int(match_start.group(2)) - 1
                    end_col = ord(match_end.group(1)) - ord('A') + 1
                    end_row = int(match_end.group(2))
                    
                    schools_merge_batch_requests.append({
                        'mergeCells': {
                            'range': {
                                'sheetId': sheet_id2,
                                'startRowIndex': start_row,
                                'endRowIndex': end_row,
                                'startColumnIndex': start_col,
                                'endColumnIndex': end_col
                            },
                            'mergeType': 'MERGE_ALL'
                        }
                    })
            
            if schools_merge_batch_requests:
                try:
                    spreadsheet.batch_update({'requests': schools_merge_batch_requests})
                    logger.info(f"[OK] Объединено {len(schools_merge_batch_requests)} заголовков для школ!")
                except Exception as e:
                    logger.warning(f"Ошибка объединения ячеек для школ: {e}")
        
        # ШИРИНА КОЛОНОК ДЛЯ ВТОРОГО ЛИСТА
        logger.info("Установка ширины колонок для второго листа...")
        column_widths2 = [
            ('A', 50),   # №
            ('B', 300),  # ФИО
            ('C', 120),  # Дата рождения
            ('D', 380),  # Турниры (увеличена для текста [БЕСПЛАТНО])
            ('E', 70),   # Участий (ещё меньше)
            ('F', 90)    # Бесплатно (ещё меньше)
        ]
        
        width_batch_requests2 = []
        sheet_id2 = worksheet2.id
        
        for col_letter, width in column_widths2:
            col_index = ord(col_letter) - ord('A')
            width_batch_requests2.append({
                'updateDimensionProperties': {
                    'range': {
                        'sheetId': sheet_id2,
                        'dimension': 'COLUMNS',
                        'startIndex': col_index,
                        'endIndex': col_index + 1
                    },
                    'properties': {
                        'pixelSize': width
                    },
                    'fields': 'pixelSize'
                }
            })
        
        if width_batch_requests2:
            body = {'requests': width_batch_requests2}
            spreadsheet.batch_update(body)
        
        # УСЛОВНОЕ ФОРМАТИРОВАНИЕ ДЛЯ ВТОРОГО ЛИСТА: Выделение дубликатов ФИО
        logger.info("Добавление условного форматирования для дубликатов (лист 2)...")
        try:
            conditional_format_request2 = {
                'addConditionalFormatRule': {
                    'rule': {
                        'ranges': [{
                            'sheetId': sheet_id2,
                            'startRowIndex': 2,  # Начало данных (после заголовков)
                            'endRowIndex': 5000,
                            'startColumnIndex': 1,  # Колонка B (ФИО)
                            'endColumnIndex': 2
                        }],
                        'booleanRule': {
                            'condition': {
                                'type': 'CUSTOM_FORMULA',
                                'values': [{
                                    'userEnteredValue': '=COUNTIF($B:$B, B3)>1'
                                }]
                            },
                            'format': {
                                'backgroundColor': {
                                    'red': 1.0,
                                    'green': 0.4,
                                    'blue': 0.8
                                }
                            }
                        }
                    },
                    'index': 0
                }
            }
            spreadsheet.batch_update({'requests': [conditional_format_request2]})
            logger.info("[OK] Условное форматирование для дубликатов добавлено (лист 2)!")
        except Exception as e:
            logger.warning(f"Ошибка добавления условного форматирования (лист 2): {e}")
        
        worksheet2.freeze(rows=1)
        
        logger.info("[OK] Второй лист 'Анализ по школам' создан!")
        
        # ========================================
        # ТРЕТИЙ ЛИСТ: СТАТИСТИКА БЕСПЛАТНЫХ УЧАСТИЙ
        # ========================================
        
        logger.info("Создание третьего листа 'Статистика'...")
        
        # ВАЖНО: Получаем данные заново, т.к. athletes_by_rank уже использовался
        logger.info("Получение данных для статистики...")
        athletes_by_rank_stats = get_athletes_data()
        
        # Подсчитываем статистику по бесплатным участиям
        # 1. Детальная статистика по 1 Спортивному
        stats_1_sport = {
            'девочки_соло': {'total': 0, 'multiple': 0},
            'мальчики_соло': {'total': 0, 'multiple': 0},
            'танцы': {'total': 0, 'multiple': 0},
            'пары': {'total': 0, 'multiple': 0}
        }
        
        # 2. Статистика по всем остальным разрядам
        stats_by_rank = {}  # {разряд: {'total': X, 'multiple': Y}}
        
        # Логирование для отладки
        logger.info(f"Доступные разряды: {list(athletes_by_rank_stats.keys())}")
        
        for rank, athletes in athletes_by_rank_stats.items():
            rank_total = 0
            rank_multiple = 0
            
            for athlete in athletes:
                if athlete['free_participations'] > 0:
                    logger.debug(f"Спортсмен с бесплатными: {athlete['name']}, разряд: {rank}, бесплатных: {athlete['free_participations']}")
                    
                    # 1 Спортивный разряд (регистронезависимая проверка)
                    rank_lower = rank.lower()
                    if '1 спортивный' in rank_lower or '1 спорт' in rank_lower:
                        is_multiple = athlete['free_participations'] > 1
                        
                        if 'танц' in rank_lower:
                            stats_1_sport['танцы']['total'] += 1
                            if is_multiple:
                                stats_1_sport['танцы']['multiple'] += 1
                        elif 'пар' in rank_lower:
                            stats_1_sport['пары']['total'] += 1
                            if is_multiple:
                                stats_1_sport['пары']['multiple'] += 1
                        elif 'девочк' in rank_lower or 'девуш' in rank_lower:
                            stats_1_sport['девочки_соло']['total'] += 1
                            if is_multiple:
                                stats_1_sport['девочки_соло']['multiple'] += 1
                        elif 'мальчик' in rank_lower or 'юнош' in rank_lower:
                            stats_1_sport['мальчики_соло']['total'] += 1
                            if is_multiple:
                                stats_1_sport['мальчики_соло']['multiple'] += 1
                    else:
                        # Остальные разряды
                        rank_total += 1
                        if athlete['free_participations'] > 1:
                            rank_multiple += 1
            
            # Сохраняем статистику по разряду (если есть бесплатные)
            if rank_total > 0:
                stats_by_rank[rank] = {
                    'total': rank_total,
                    'multiple': rank_multiple
                }
        
        # Считаем итоги для 1 Спортивного
        total_1_sport = sum(cat['total'] for cat in stats_1_sport.values())
        multiple_1_sport = sum(cat['multiple'] for cat in stats_1_sport.values())
        
        # Считаем итоги для остальных разрядов
        total_other = sum(stat['total'] for stat in stats_by_rank.values())
        multiple_other = sum(stat['multiple'] for stat in stats_by_rank.values())
        
        # Общий итог
        total_free = total_1_sport + total_other
        total_multiple = multiple_1_sport + multiple_other
        
        # Логирование итогов
        logger.info(f"Статистика подсчета:")
        logger.info(f"  1 Спорт (девочки): {stats_1_sport['девочки_соло']['total']} (из них >1 раза: {stats_1_sport['девочки_соло']['multiple']})")
        logger.info(f"  1 Спорт (мальчики): {stats_1_sport['мальчики_соло']['total']} (из них >1 раза: {stats_1_sport['мальчики_соло']['multiple']})")
        logger.info(f"  1 Спорт (танцы): {stats_1_sport['танцы']['total']} (из них >1 раза: {stats_1_sport['танцы']['multiple']})")
        logger.info(f"  1 Спорт (пары): {stats_1_sport['пары']['total']} (из них >1 раза: {stats_1_sport['пары']['multiple']})")
        logger.info(f"  Итого 1 Спорт: {total_1_sport} (из них >1 раза: {multiple_1_sport})")
        logger.info(f"  Остальные разряды: {total_other} (из них >1 раза: {multiple_other})")
        logger.info(f"  ВСЕГО бесплатных: {total_free} (из них >1 раза: {total_multiple})")
        
        # Создаём или получаем третий лист
        try:
            worksheet3 = spreadsheet.worksheet("Статистика")
            sheet_id3 = worksheet3.id
            
            # Очистка третьего листа
            logger.info("Очистка третьего листа...")
            try:
                clear_requests3 = [
                    {
                        'unmergeCells': {
                            'range': {
                                'sheetId': sheet_id3,
                                'startRowIndex': 0,
                                'endRowIndex': 100,
                                'startColumnIndex': 0,
                                'endColumnIndex': 5
                            }
                        }
                    },
                    {
                        'updateCells': {
                            'range': {
                                'sheetId': sheet_id3,
                                'startRowIndex': 0,
                                'endRowIndex': 100,
                                'startColumnIndex': 0,
                                'endColumnIndex': 5
                            },
                            'fields': 'userEnteredFormat,userEnteredValue'
                        }
                    }
                ]
                spreadsheet.batch_update({'requests': clear_requests3})
                logger.info("[OK] Третий лист очищен")
            except Exception as e:
                logger.warning(f"Ошибка при очистке третьего листа: {e}")
                worksheet3.clear()
            
        except:
            worksheet3 = spreadsheet.add_worksheet(title="Статистика", rows=100, cols=5)
            sheet_id3 = worksheet3.id
        
        # Заголовок третьего листа
        worksheet3.update_acell('A1', 
            f'СТАТИСТИКА БЕСПЛАТНЫХ УЧАСТИЙ - Обновлено: {datetime.now().strftime("%d.%m.%Y %H:%M")}')
        worksheet3.format('A1:D1', {
            'textFormat': {'bold': True, 'fontSize': 14},
            'horizontalAlignment': 'CENTER',
            'backgroundColor': {'red': 0.29, 'green': 0.53, 'blue': 0.91}
        })
        
        # Объединение главного заголовка третьего листа
        try:
            main_header_merge3 = {
                'mergeCells': {
                    'range': {
                        'sheetId': sheet_id3,
                        'startRowIndex': 0,
                        'endRowIndex': 1,
                        'startColumnIndex': 0,
                        'endColumnIndex': 4
                    },
                    'mergeType': 'MERGE_ALL'
                }
            }
            spreadsheet.batch_update({'requests': [main_header_merge3]})
        except Exception as e:
            logger.debug(f"Объединение заголовка третьего листа: {e}")
        
        # Формируем данные для третьего листа
        stats_data = []
        current_row = 3
        
        # Заголовок секции "1 СПОРТИВНЫЙ РАЗРЯД"
        stats_data.append(['1 СПОРТИВНЫЙ РАЗРЯД', '', '', ''])
        stats_data.append(['Категория', 'Всего', 'Выступали >1 раза', '%'])
        
        # Данные по 1 Спортивному
        for category, key in [('Девочки', 'девочки_соло'), ('Мальчики', 'мальчики_соло'), 
                               ('Танцы', 'танцы'), ('Пары', 'пары')]:
            total = stats_1_sport[key]['total']
            multiple = stats_1_sport[key]['multiple']
            percent = round((multiple / total * 100) if total > 0 else 0, 1)
            stats_data.append([f'  • {category}', total, multiple, f'{percent}%'])
        
        stats_data.append(['', '', '', ''])
        percent_1_sport = round((multiple_1_sport / total_1_sport * 100) if total_1_sport > 0 else 0, 1)
        stats_data.append(['ИТОГО 1 Спортивный:', total_1_sport, multiple_1_sport, f'{percent_1_sport}%'])
        stats_data.append(['', '', '', ''])
        
        # Остальные разряды - таблица
        stats_data.append(['ОСТАЛЬНЫЕ РАЗРЯДЫ', '', '', ''])
        stats_data.append(['Разряд', 'Всего', 'Выступали >1 раза', '%'])
        
        # Сортируем разряды по порядку (как в основном списке)
        rank_order = [
            'МС, Женщины', 'МС, Мужчины', 'МС, Пары', 'МС, Танцы',
            'КМС, Девушки', 'КМС, Юноши', 'КМС, Пары', 'КМС, Танцы',
            '2 Спортивный, Девочки', '2 Спортивный, Мальчики', '2 Спортивный, Пары', '2 Спортивный, Танцы',
            '3 Спортивный, Девочки', '3 Спортивный, Мальчики', '3 Спортивный, Пары', '3 Спортивный, Танцы',
            '1 Юношеский, Девочки', '1 Юношеский, Мальчики',
            '2 Юношеский, Девочки', '2 Юношеский, Мальчики',
            '3 Юношеский, Девочки', '3 Юношеский, Мальчики',
            'Юный Фигурист, Девочки', 'Юный Фигурист, Мальчики',
            'Дебют, Девочки', 'Дебют, Мальчики',
            'Новичок, Девочки', 'Новичок, Мальчики',
        ]
        
        # Добавляем остальные разряды
        for rank in stats_by_rank.keys():
            if rank not in rank_order:
                rank_order.append(rank)
        
        # Выводим разряды в порядке
        for rank in rank_order:
            if rank in stats_by_rank:
                stat = stats_by_rank[rank]
                total = stat['total']
                multiple = stat['multiple']
                percent = round((multiple / total * 100) if total > 0 else 0, 1)
                stats_data.append([rank, total, multiple, f'{percent}%'])
        
        stats_data.append(['', '', '', ''])
        percent_other = round((multiple_other / total_other * 100) if total_other > 0 else 0, 1)
        stats_data.append(['ИТОГО остальные:', total_other, multiple_other, f'{percent_other}%'])
        stats_data.append(['', '', '', ''])
        
        # Общий итог
        stats_data.append(['═══════════════════════════════════════', '', '', ''])
        percent_total = round((total_multiple / total_free * 100) if total_free > 0 else 0, 1)
        stats_data.append(['ВСЕГО БЕСПЛАТНЫХ:', total_free, total_multiple, f'{percent_total}%'])
        
        # Записываем данные (динамически определяем количество строк)
        end_row = current_row + len(stats_data) - 1
        worksheet3.update(f'A{current_row}:D{end_row}', stats_data)
        
        # Форматирование третьего листа
        # Вычисляем номера строк для форматирования
        row_1_sport_header = current_row  # 3: "1 СПОРТИВНЫЙ РАЗРЯД"
        row_1_sport_table = current_row + 1  # 4: шапка таблицы "Категория | Всего..."
        # После заголовка (1) + шапка (1) + 4 категории (4) + пустая (1) = 7 строк
        row_1_sport_total = current_row + 6  # 9: "ИТОГО 1 Спортивный"
        row_other_header = row_1_sport_total + 2  # 11: "ОСТАЛЬНЫЕ РАЗРЯДЫ"
        row_other_table = row_other_header + 1  # 12: шапка таблицы "Разряд | Всего..."
        row_other_total = end_row - 2  # предпоследняя строка перед итогом
        row_total = end_row  # последняя строка
        
        # Заголовок "1 СПОРТИВНЫЙ РАЗРЯД"
        worksheet3.format(f'A{row_1_sport_header}:D{row_1_sport_header}', {
            'textFormat': {'bold': True, 'fontSize': 12},
            'horizontalAlignment': 'LEFT',
            'backgroundColor': {'red': 0.85, 'green': 0.92, 'blue': 0.83}
        })
        
        # Шапка таблицы 1 Спортивного
        worksheet3.format(f'A{row_1_sport_table}:D{row_1_sport_table}', {
            'textFormat': {'bold': True},
            'horizontalAlignment': 'CENTER',
            'backgroundColor': {'red': 0.8, 'green': 0.8, 'blue': 0.8}
        })
        
        # "ИТОГО 1 Спортивный"
        worksheet3.format(f'A{row_1_sport_total}:D{row_1_sport_total}', {
            'textFormat': {'bold': True},
            'horizontalAlignment': 'LEFT',
            'backgroundColor': {'red': 0.95, 'green': 0.95, 'blue': 0.95}
        })
        
        # "ОСТАЛЬНЫЕ РАЗРЯДЫ"
        worksheet3.format(f'A{row_other_header}:D{row_other_header}', {
            'textFormat': {'bold': True, 'fontSize': 12},
            'horizontalAlignment': 'LEFT',
            'backgroundColor': {'red': 0.85, 'green': 0.92, 'blue': 0.83}
        })
        
        # Шапка таблицы остальных разрядов
        worksheet3.format(f'A{row_other_table}:D{row_other_table}', {
            'textFormat': {'bold': True},
            'horizontalAlignment': 'CENTER',
            'backgroundColor': {'red': 0.8, 'green': 0.8, 'blue': 0.8}
        })
        
        # "ИТОГО остальные"
        worksheet3.format(f'A{row_other_total}:D{row_other_total}', {
            'textFormat': {'bold': True},
            'horizontalAlignment': 'LEFT',
            'backgroundColor': {'red': 0.95, 'green': 0.95, 'blue': 0.95}
        })
        
        # "ВСЕГО БЕСПЛАТНЫХ"
        worksheet3.format(f'A{row_total}:D{row_total}', {
            'textFormat': {'bold': True, 'fontSize': 13},
            'horizontalAlignment': 'LEFT',
            'backgroundColor': {'red': 0.29, 'green': 0.53, 'blue': 0.91}
        })
        
        # Ширина колонок третьего листа
        width_batch_requests3 = [
            {
                'updateDimensionProperties': {
                    'range': {
                        'sheetId': sheet_id3,
                        'dimension': 'COLUMNS',
                        'startIndex': 0,  # A - Разряд/Категория
                        'endIndex': 1
                    },
                    'properties': {'pixelSize': 350},
                    'fields': 'pixelSize'
                }
            },
            {
                'updateDimensionProperties': {
                    'range': {
                        'sheetId': sheet_id3,
                        'dimension': 'COLUMNS',
                        'startIndex': 1,  # B - Всего
                        'endIndex': 2
                    },
                    'properties': {'pixelSize': 100},
                    'fields': 'pixelSize'
                }
            },
            {
                'updateDimensionProperties': {
                    'range': {
                        'sheetId': sheet_id3,
                        'dimension': 'COLUMNS',
                        'startIndex': 2,  # C - Выступали >1 раза
                        'endIndex': 3
                    },
                    'properties': {'pixelSize': 150},
                    'fields': 'pixelSize'
                }
            },
            {
                'updateDimensionProperties': {
                    'range': {
                        'sheetId': sheet_id3,
                        'dimension': 'COLUMNS',
                        'startIndex': 3,  # D - %
                        'endIndex': 4
                    },
                    'properties': {'pixelSize': 80},
                    'fields': 'pixelSize'
                }
            }
        ]
        
        if width_batch_requests3:
            spreadsheet.batch_update({'requests': width_batch_requests3})
        
        worksheet3.freeze(rows=1)
        
        logger.info("[OK] Третий лист 'Статистика' создан!")
        
        # ========================================
        # ЧЕТВЁРТЫЙ ЛИСТ: ОТЧЁТ ПО ТУРНИРАМ
        # ========================================
        
        logger.info("Создание четвертого листа 'Отчет по турнирам'...")
        events_report = get_events_report_data()
        events_summary = events_report['events']
        events_totals = events_report['totals']
        
        try:
            worksheet4 = spreadsheet.worksheet("Отчет по турнирам")
            sheet_id4 = worksheet4.id
            
            logger.info("Очистка четвертого листа...")
            try:
                clear_requests4 = [
                    {
                        'unmergeCells': {
                            'range': {
                                'sheetId': sheet_id4,
                                'startRowIndex': 0,
                                'endRowIndex': 2000,
                                'startColumnIndex': 0,
                                'endColumnIndex': 6
                            }
                        }
                    },
                    {
                        'updateCells': {
                            'range': {
                                'sheetId': sheet_id4,
                                'startRowIndex': 0,
                                'endRowIndex': 2000,
                                'startColumnIndex': 0,
                                'endColumnIndex': 6
                            },
                            'fields': 'userEnteredFormat,userEnteredValue'
                        }
                    }
                ]
                spreadsheet.batch_update({'requests': clear_requests4})
                logger.info("[OK] Четвертый лист очищен полностью")
            except Exception as e:
                logger.warning(f"Ошибка при полной очистке четвертого листа: {e}, выполняем стандартную очистку...")
                worksheet4.clear()
        except:
            worksheet4 = spreadsheet.add_worksheet(title="Отчет по турнирам", rows=2000, cols=6)
            sheet_id4 = worksheet4.id
        
        # Заголовок четвертого листа
        worksheet4.update_acell('A1', 
            f'ОТЧЕТ ПО ТУРНИРАМ - Обновлено: {datetime.now().strftime("%d.%m.%Y %H:%M")}')
        worksheet4.format('A1:D1', {
            'textFormat': {'bold': True, 'fontSize': 14},
            'horizontalAlignment': 'CENTER',
            'backgroundColor': {'red': 0.29, 'green': 0.53, 'blue': 0.91}
        })
        
        # Объединяем главный заголовок
        try:
            main_header_merge4 = {
                'mergeCells': {
                    'range': {
                        'sheetId': sheet_id4,
                        'startRowIndex': 0,
                        'endRowIndex': 1,
                        'startColumnIndex': 0,
                        'endColumnIndex': 4
                    },
                    'mergeType': 'MERGE_ALL'
                }
            }
            spreadsheet.batch_update({'requests': [main_header_merge4]})
        except Exception as e:
            logger.debug(f"Объединение заголовка четвертого листа: {e}")
        
        current_row = 3
        table_rows = []
        format_requests4 = []
        
        header_row_index = current_row
        table_rows.append(['Дата турнира', 'Название турнира', 'Участников (детей)', 'Бесплатно'])
        format_requests4.append({
            'range': f'A{header_row_index}:D{header_row_index}',
            'format': {
                'textFormat': {'bold': True},
                'horizontalAlignment': 'CENTER',
                'backgroundColor': {'red': 0.8, 'green': 0.8, 'blue': 0.8}
            }
        })
        current_row += 1
        
        summary_rows = []
        summary_free_rows = []
        rank_header_rows = []
        rank_free_rows = []
        data_start_row = current_row
        
        for idx, event in enumerate(events_summary):
            summary_row_index = current_row
            table_rows.append([
                event['event_date_display'],
                event['event_name'],
                event['total_children'],
                event['free_children']
            ])
            summary_rows.append(summary_row_index)
            if event['free_children'] > 0:
                summary_free_rows.append(summary_row_index)
            current_row += 1
            
            if event.get('rank_stats'):
                rank_header_index = current_row
                table_rows.append(['', 'Разряд', 'Участников (детей)', 'Бесплатно'])
                rank_header_rows.append(rank_header_index)
                current_row += 1
                
                for rank_stat in event['rank_stats']:
                    rank_row_index = current_row
                    table_rows.append([
                        '',
                        rank_stat['rank'],
                        rank_stat['total_children'],
                        rank_stat['free_children']
                    ])
                    if rank_stat['free_children'] > 0:
                        rank_free_rows.append(rank_row_index)
                    current_row += 1
            
            # Пустая строка между турнирами (кроме последнего)
            if idx != len(events_summary) - 1:
                table_rows.append(['', '', '', ''])
                current_row += 1
        
        if not events_summary:
            summary_row_index = current_row
            table_rows.append(['-', 'Нет данных', 0, 0])
            summary_rows.append(summary_row_index)
            current_row += 1
        
        if table_rows:
            table_rows.append(['', '', '', ''])
            current_row += 1
        
        totals_row_index = current_row
        table_rows.append([
            '',
            'ИТОГО (без МС/КМС)',
            events_totals['total_children'],
            events_totals['free_children']
        ])
        current_row += 1
        
        end_row = header_row_index + len(table_rows) - 1
        worksheet4.update(f'A{header_row_index}:D{end_row}', table_rows)
        
        # Форматирование числовых столбцов (выравнивание по центру)
        if totals_row_index >= data_start_row:
            format_requests4.append({
                'range': f'C{data_start_row}:D{totals_row_index}',
                'format': {
                    'horizontalAlignment': 'CENTER'
                }
            })
        
        # Форматирование сводных строк по турнирам
        for row_index in summary_rows:
            format_requests4.append({
                'range': f'A{row_index}:D{row_index}',
                'format': {
                    'textFormat': {'bold': True},
                    'backgroundColor': {'red': 0.87, 'green': 0.93, 'blue': 0.98}
                }
            })
        
        # Шапки разрядов
        for row_index in rank_header_rows:
            format_requests4.append({
                'range': f'B{row_index}:D{row_index}',
                'format': {
                    'textFormat': {'bold': True},
                    'horizontalAlignment': 'CENTER',
                    'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9}
                }
            })
        
        # Подсветка бесплатных значений
        for row_index in summary_free_rows:
            format_requests4.append({
                'range': f'D{row_index}',
                'format': {
                    'backgroundColor': {'red': 0.79, 'green': 0.89, 'blue': 0.79},
                    'textFormat': {'bold': True}
                }
            })
        for row_index in rank_free_rows:
            format_requests4.append({
                'range': f'D{row_index}',
                'format': {
                    'backgroundColor': {'red': 0.85, 'green': 0.95, 'blue': 0.85},
                    'textFormat': {'bold': True}
                }
            })
        
        # Форматирование строки итогов
        format_requests4.append({
            'range': f'A{totals_row_index}:D{totals_row_index}',
            'format': {
                'textFormat': {'bold': True},
                'horizontalAlignment': 'LEFT',
                'backgroundColor': {'red': 0.95, 'green': 0.95, 'blue': 0.95}
            }
        })
        if events_totals['free_children'] > 0:
            format_requests4.append({
                'range': f'D{totals_row_index}',
                'format': {
                    'backgroundColor': {'red': 0.72, 'green': 0.86, 'blue': 0.72},
                    'textFormat': {'bold': True}
                }
            })
        
        if format_requests4:
            worksheet4.batch_format(format_requests4)
        
        # Ширина колонок
        column_widths4 = [
            ('A', 140),
            ('B', 420),
            ('C', 160),
            ('D', 160)
        ]
        width_batch_requests4 = []
        for col_letter, width in column_widths4:
            col_index = ord(col_letter) - ord('A')
            width_batch_requests4.append({
                'updateDimensionProperties': {
                    'range': {
                        'sheetId': sheet_id4,
                        'dimension': 'COLUMNS',
                        'startIndex': col_index,
                        'endIndex': col_index + 1
                    },
                    'properties': {'pixelSize': width},
                    'fields': 'pixelSize'
                }
            })
        
        if width_batch_requests4:
            spreadsheet.batch_update({'requests': width_batch_requests4})
        
        worksheet4.freeze(rows=1)
        
        logger.info("[OK] Четвертый лист 'Отчет по турнирам' создан (без МС/КМС)!")
        logger.info("Экспорт завершен успешно!")
        logger.info("Примерное количество API запросов: ~25-30")
        
        total_athletes = sum(len(athletes) for athletes in athletes_by_rank_stats.values())
        total_schools = len(schools_data)
        total_events = len(events_summary)
        
        return {
            'success': True,
            'url': spreadsheet.url,
            'spreadsheet_id': spreadsheet.id,
            'message': (
                f'Экспорт завершен! Создано 4 листа: '
                f'"Список спортсменов" ({total_athletes} спортсменов), '
                f'"Анализ по школам" ({total_schools} школ), '
                f'"Статистика" ({total_free} бесплатных участий) и '
                f'"Отчет по турнирам" ({total_events} турниров, '
                f'{events_totals["total_children"]} детей / {events_totals["free_children"]} бесплатно, без МС/КМС).'
            )
        }
        
    except Exception as e:
        logger.error(f"Ошибка при экспорте в Google Sheets: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            'success': False,
            'url': None,
            'message': f'Ошибка экспорта: {str(e)}'
        }

if __name__ == '__main__':
    """Тестовый запуск"""
    print("🧪 Тестовый экспорт в Google Sheets...")
    result = export_to_google_sheets()
    
    if result['success']:
        print(f"✅ {result['message']}")
        print(f"🔗 URL: {result['url']}")
    else:
        print(f"❌ {result['message']}")

