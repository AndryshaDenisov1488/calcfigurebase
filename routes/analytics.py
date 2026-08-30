#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Analytics HTML routes."""
import io
import logging
import os
import re
from datetime import date, datetime

from flask import Blueprint, render_template, request, send_file, url_for, session

from sqlalchemy import func
from extensions import db
from models import Athlete, Participant, Event, Category, JudgeHelperFreeAudit
from rank_scope import category_scope_clause
from season_utils import event_in_season, get_active_season, get_season_display_name
from utils.access_control import SESSION_SITE_READER_KEY
from utils.client_ip import get_client_ip

analytics_bp = Blueprint('analytics', __name__)

logger = logging.getLogger(__name__)

# Максимум символов из поля «список ФИО» в журнал (защита от огромных вставок)
_JUDGE_HELPER_NAMES_RAW_MAX = int(os.environ.get('JUDGE_HELPER_NAMES_RAW_MAX', '600000'))


def _normalize_words(s):
    if not s or not isinstance(s, str):
        return []
    s = re.sub(r'\s+', ' ', (s or '').strip()).lower().replace('ё', 'е')
    return s.split() if s else []


def _is_year(s):
    """Строка — год (4 цифры)."""
    s = (s or '').strip()
    return len(s) == 4 and s.isdigit()


def _is_rank(s):
    """Строка похожа на разряд: 1С, 2Ю, 3 П и т.п."""
    s = (s or '').strip()
    return bool(re.match(r'^\d\s*[А-Яа-яЁё]\s*$', s)) or s.upper() in ('1С', '2С', '3С', '1Ю', '2Ю', '3Ю', '1П', '2П', '3П', 'МС', 'КМС')


def _is_city_or_school(s):
    """Строка похожа на город или школу (адрес, организация)."""
    s = (s or '').strip()
    if not s:
        return True
    s_lower = s.lower()
    if s_lower.startswith('москва') or s_lower.startswith('санкт-') or s_lower.startswith('спб'):
        return True
    if any(x in s for x in ('ГБУ', 'СШОР', 'ООО', 'ИП ', 'АНО', 'МОО', '(', 'школа', 'отд.', 'отд ', 'фигурного катания')):
        return True
    return False


def _looks_like_fio(s):
    """Строка похожа на ФИО: 2–3 слова, в основном кириллица."""
    s = (s or '').strip()
    if not s or len(s) < 3:
        return False
    words = re.split(r'\s+', s)
    if len(words) < 2 or len(words) > 4:
        return False
    for w in words:
        if not w:
            return False
        cyr = sum(1 for c in w if 'а' <= c.lower() <= 'я' or c in 'ёЁ')
        if cyr < len(w) * 0.6 and not re.match(r'^[А-Яа-яЁё\-]+$', w):
            return False
    return True


def _parse_birth_date(value):
    """Разобрать дату рождения из ячейки Excel / текста (ДД.ММ.ГГГГ и др.)."""
    if value is None or value == '':
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    s = str(value).strip()
    if not s:
        return None
    for fmt in ('%d.%m.%Y', '%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%d.%m.%y'):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _format_entry_label(fio, birth_date=None):
    if birth_date:
        return f"{fio} ({birth_date.strftime('%d.%m.%Y')})"
    return fio


def _split_table_cells(line):
    """Разбить строку вставки из Excel/CSV на ячейки."""
    if '\t' in line:
        return [c.strip() for c in line.split('\t')]
    if line.count(';') >= 2:
        return [c.strip() for c in line.split(';')]
    if line.count(',') >= 2:
        return [c.strip() for c in line.split(',')]
    return [line.strip()]


def _is_reg_header_row(cells):
    joined = ' '.join((c or '').lower() for c in cells)
    return ('фамили' in joined and 'имя' in joined) or 'дата рождения' in joined or '№ п.п' in joined


def _detect_fio_dob_indexes(header_cells):
    """Индексы колонок ФИО и ДР по заголовку выгрузки регистрации."""
    fio_idx = None
    dob_idx = None
    for i, cell in enumerate(header_cells):
        low = (cell or '').strip().lower().replace('ё', 'е')
        if fio_idx is None and ('фамили' in low or low in ('фио', 'спортсмен')):
            fio_idx = i
        if dob_idx is None and ('рожден' in low or low in ('др', 'дата др', 'д.р.', 'д.р')):
            dob_idx = i
    if fio_idx is None and len(header_cells) >= 2:
        fio_idx = 1
    if dob_idx is None and len(header_cells) >= 3:
        dob_idx = 2
    return fio_idx, dob_idx


def _entries_from_fio_dob_pair(fio_raw, dob_raw):
    """Один спортсмен или пара «ФИО1 / ФИО2» с «ДР1 / ДР2» → список entries."""
    if fio_raw is None:
        return []
    if isinstance(fio_raw, (date, datetime)):
        return []
    fio_text = str(fio_raw).strip()
    if not fio_text:
        return []

    parts = [p.strip() for p in re.split(r'\s*/\s*', fio_text) if p.strip()]
    dob_parts = []
    if isinstance(dob_raw, (date, datetime)):
        dob_parts = [dob_raw]
    elif dob_raw is not None and str(dob_raw).strip():
        dob_parts = [p.strip() for p in re.split(r'\s*/\s*', str(dob_raw).strip()) if p.strip()]

    entries = []
    for i, part in enumerate(parts):
        if not _looks_like_fio(part):
            continue
        dob = _parse_birth_date(dob_parts[i]) if i < len(dob_parts) else None
        entries.append({'fio': part, 'birth_date': dob})
    return entries


def _entry_from_cells(cells, fio_idx=1, dob_idx=2):
    """Извлечь ФИО(+пары) и ДР из строки таблицы (по умолчанию B и C)."""
    if not cells:
        return []
    # Нормализуем к строкам / датам
    norm = []
    for c in cells:
        if c is None:
            norm.append('')
        elif isinstance(c, (date, datetime)):
            norm.append(c)
        else:
            norm.append(str(c).strip())

    if len(norm) == 1:
        return _entries_from_fio_dob_pair(norm[0], None)

    first = norm[0]
    first_s = first.strftime('%d.%m.%Y') if isinstance(first, (date, datetime)) else str(first)

    if first_s.isdigit() or first_s.lower().startswith('№'):
        fio = norm[fio_idx] if fio_idx < len(norm) else ''
        dob_raw = norm[dob_idx] if dob_idx < len(norm) else None
        return _entries_from_fio_dob_pair(fio, dob_raw)

    if isinstance(first, str) and _looks_like_fio(first):
        dob = norm[1] if len(norm) > 1 else None
        return _entries_from_fio_dob_pair(first, dob)

    if '/' in first_s:
        dob = norm[1] if len(norm) > 1 else (norm[dob_idx] if dob_idx < len(norm) else None)
        return _entries_from_fio_dob_pair(first, dob)

    if fio_idx < len(norm):
        dob_raw = norm[dob_idx] if dob_idx < len(norm) else None
        return _entries_from_fio_dob_pair(norm[fio_idx], dob_raw)
    return []


def _dedupe_entries(entries):
    result = []
    seen = set()
    for entry in entries:
        fio = (entry.get('fio') or '').strip()
        if not fio:
            continue
        words = _normalize_words(fio)
        if len(words) < 2:
            continue
        birth_date = entry.get('birth_date')
        fio_key = tuple(words[:3]) if len(words) >= 3 else tuple(words[:2])
        dedup_key = (fio_key, birth_date.isoformat() if birth_date else None)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        result.append({'fio': fio, 'birth_date': birth_date})
    return result


def _parse_pasted_entries(text):
    """Разобрать вставку: чистые ФИО или таблицу регистрации (кол. B = ФИО, C = ДР).

    Возвращает [{'fio': str, 'birth_date': date|None}, ...].
    """
    lines = [ln.strip() for ln in (text or '').splitlines() if ln.strip()]
    if not lines:
        return []

    entries = []
    fio_idx, dob_idx = 1, 2
    first_cells = _split_table_cells(lines[0])
    start = 0
    if len(first_cells) >= 2 and _is_reg_header_row(first_cells):
        detected = _detect_fio_dob_indexes(first_cells)
        fio_idx = detected[0] if detected[0] is not None else 1
        dob_idx = detected[1] if detected[1] is not None else 2
        start = 1

    for ln in lines[start:]:
        cells = _split_table_cells(ln)
        if len(cells) >= 2:
            if _is_reg_header_row(cells):
                detected = _detect_fio_dob_indexes(cells)
                fio_idx = detected[0] if detected[0] is not None else fio_idx
                dob_idx = detected[1] if detected[1] is not None else dob_idx
                continue
            entries.extend(_entry_from_cells(cells, fio_idx=fio_idx, dob_idx=dob_idx))
            continue

        if _is_year(ln) or _is_rank(ln) or _is_city_or_school(ln):
            continue
        if '/' in ln:
            entries.extend(_entries_from_fio_dob_pair(ln, None))
            continue
        if not _looks_like_fio(ln):
            continue
        entries.append({'fio': ln, 'birth_date': None})

    return _dedupe_entries(entries)


def _parse_pasted_list(text):
    """Совместимость: только список ФИО без дат."""
    return [e['fio'] for e in _parse_pasted_entries(text)]


def _parse_xlsx_entries(file_storage):
    """Разбор .xlsx выгрузки регистрации: колонка B = ФИО, C = дата рождения."""
    try:
        from openpyxl import load_workbook
    except ImportError:
        logger.warning('openpyxl недоступен для разбора xlsx judge-helper')
        return []

    raw = file_storage.read()
    if not raw:
        return []
    # read_only=False: у части выгрузок регистрации dimensions/колонки в read_only ломаются
    wb = load_workbook(io.BytesIO(raw), data_only=True, read_only=False)
    try:
        ws = wb.active
        rows = []
        for row in ws.iter_rows(min_row=1, max_row=ws.max_row or 1, max_col=max(ws.max_column or 1, 3), values_only=True):
            rows.append(row)
    finally:
        wb.close()

    if not rows:
        return []

    fio_idx, dob_idx = 1, 2
    start = 0
    header = [str(c).strip() if c is not None else '' for c in rows[0]]
    if _is_reg_header_row(header):
        detected = _detect_fio_dob_indexes(header)
        fio_idx = detected[0] if detected[0] is not None else 1
        dob_idx = detected[1] if detected[1] is not None else 2
        start = 1

    entries = []
    for row in rows[start:]:
        if not row or not any(c is not None and str(c).strip() for c in row):
            continue
        str_cells = [
            '' if c is None else (c.strftime('%d.%m.%Y') if isinstance(c, (date, datetime)) else str(c).strip())
            for c in row
        ]
        if _is_reg_header_row(str_cells):
            detected = _detect_fio_dob_indexes(str_cells)
            fio_idx = detected[0] if detected[0] is not None else fio_idx
            dob_idx = detected[1] if detected[1] is not None else dob_idx
            continue
        fio_raw = row[fio_idx] if fio_idx < len(row) else None
        dob_raw = row[dob_idx] if dob_idx < len(row) else None
        entries.extend(_entries_from_fio_dob_pair(fio_raw, dob_raw))
    return _dedupe_entries(entries)


def _check_names_against_db(names_or_entries, season=None):
    """По списку ФИО (или [{fio, birth_date}]) вернуть (found, fio_only_matches, not_found).

    found / fio_only_matches = [(display_label, [match_info, ...]), ...]
    match_info: id, full_name, birth_date, patronymic, rank
    При наличии ДР: приоритет совпадений ФИО/ФИ + дата рождения.
    Разряд в match_info — из участий выбранного сезона.
    """
    if not names_or_entries:
        return [], [], []

    season = season or get_active_season()
    entries = []
    for item in names_or_entries:
        if isinstance(item, dict):
            fio = (item.get('fio') or '').strip()
            birth_date = item.get('birth_date')
            if isinstance(birth_date, str):
                birth_date = _parse_birth_date(birth_date)
        else:
            fio = (item or '').strip()
            birth_date = None
        if fio:
            entries.append({'fio': fio, 'birth_date': birth_date})
    if not entries:
        return [], [], []

    name_keys = []
    for entry in entries:
        fio = entry['fio']
        birth_date = entry.get('birth_date')
        words = _normalize_words(fio)
        if len(words) >= 2:
            base_key = frozenset(words[:2])
            full_key = frozenset(words[:3]) if len(words) >= 3 else None
            dedup_key = (
                tuple(words[:3]) if len(words) >= 3 else tuple(words[:2]),
                birth_date.isoformat() if birth_date else None,
            )
            label = _format_entry_label(fio, birth_date)
            name_keys.append((label, base_key, full_key, dedup_key, birth_date))
    if not name_keys:
        return [], [], [_format_entry_label(e['fio'], e.get('birth_date')) for e in entries]

    athletes_data = []
    for a in Athlete.query.all():
        name = a.full_name
        words = set(_normalize_words(name))
        if words:
            athletes_data.append((a.id, name, words, a.birth_date))

    found = []
    fio_only_matches = []
    not_found = []
    seen_key = set()
    for label, base_key, full_key, dedup_key, birth_date in name_keys:
        if dedup_key in seen_key:
            continue
        seen_key.add(dedup_key)

        def _by_words(key):
            return [(aid, db_name) for aid, db_name, name_words, _bd in athletes_data if key <= name_words]

        def _filter_dob(raw):
            if not birth_date:
                return raw
            id_set = {aid for aid, _ in raw}
            return [
                (aid, db_name)
                for aid, db_name, _words, bd in athletes_data
                if aid in id_set and bd == birth_date
            ]

        raw_full = _by_words(full_key) if full_key else []
        raw_base = _by_words(base_key)

        if birth_date:
            # ДР из выгрузки: сначала ФИО+ДР, затем ФИ+ДР (сильный сигнал)
            dob_full = _filter_dob(raw_full) if raw_full else []
            dob_base = _filter_dob(raw_base)
            if dob_full:
                matches = _enrich_matches(dob_full, season=season)
                found.append((label, matches))
                continue
            if dob_base:
                matches = _enrich_matches(dob_base, season=season)
                found.append((label, matches))
                continue
            if raw_full:
                matches = _enrich_matches(raw_full, season=season)
                fio_only_matches.append((label, matches))
                continue
            if raw_base:
                matches = _enrich_matches(raw_base, season=season)
                fio_only_matches.append((label, matches))
                continue
            not_found.append(label)
            continue

        if full_key:
            raw_matches = raw_full
            if not raw_matches:
                matches = _enrich_matches(raw_base, season=season)
                if matches:
                    fio_only_matches.append((label, matches))
                    continue
        else:
            raw_matches = raw_base

        matches = _enrich_matches(raw_matches, season=season)
        if matches:
            found.append((label, matches))
        else:
            not_found.append(label)
    return found, fio_only_matches, not_found


def _enrich_matches(raw_matches, season=None):
    """Добавляет метаданные к совпадениям: дата рождения, отчество, текущий/последний разряд."""
    if not raw_matches:
        return []

    athlete_ids = [aid for aid, _ in raw_matches]
    season = season or get_active_season()

    athletes = Athlete.query.filter(Athlete.id.in_(athlete_ids)).all()
    athlete_map = {a.id: a for a in athletes}

    # Последний разряд по дате турнира в выбранном сезоне
    latest_rank_map = {}
    participations = (
        db.session.query(
            Participant.athlete_id,
            Participant.id.label('participant_id'),
            Event.begin_date.label('event_date'),
            Category.normalized_name,
            Category.name.label('category_name'),
        )
        .join(Category, Participant.category_id == Category.id)
        .join(Event, Participant.event_id == Event.id)
        .filter(
            Participant.athlete_id.in_(athlete_ids),
            *event_in_season(Event.begin_date, season),
            category_scope_clause(),
        )
        .order_by(Participant.athlete_id, Event.begin_date.desc(), Participant.id.desc())
        .all()
    )

    for row in participations:
        if row.athlete_id not in latest_rank_map:
            latest_rank_map[row.athlete_id] = row.normalized_name or row.category_name or 'Не указан'

    enriched = []
    for aid, db_name in raw_matches:
        athlete = athlete_map.get(aid)
        birth_date = athlete.birth_date.strftime('%d.%m.%Y') if athlete and athlete.birth_date else '—'
        patronymic = (athlete.patronymic or '—') if athlete else '—'
        rank = latest_rank_map.get(aid, 'Не указан')
        enriched.append({
            'id': aid,
            'full_name': db_name,
            'birth_date': birth_date,
            'patronymic': patronymic,
            'rank': rank,
        })
    return enriched


def _get_participation_counts(season=None):
    """Возвращает (total_by_athlete, free_by_athlete) только за выбранный сезон."""
    season = season or get_active_season()
    free_counts = (
        db.session.query(Participant.athlete_id, func.count(Participant.id).label('cnt'))
        .join(Category, Participant.category_id == Category.id)
        .join(Event, Participant.event_id == Event.id)
        .filter(
            Participant.pct_ppname == 'БЕСП',
            db.or_(Participant.exclude_free_from_reports.is_(False), Participant.exclude_free_from_reports.is_(None)),
            db.or_(Event.exclude_free_from_reports.is_(False), Event.exclude_free_from_reports.is_(None)),
            *event_in_season(Event.begin_date, season),
            category_scope_clause(),
        )
        .group_by(Participant.athlete_id)
    )
    free_by_athlete = {row.athlete_id: row.cnt for row in free_counts}
    total_counts = (
        db.session.query(Participant.athlete_id, func.count(Participant.id).label('cnt'))
        .join(Category, Participant.category_id == Category.id)
        .join(Event, Participant.event_id == Event.id)
        .filter(*event_in_season(Event.begin_date, season), category_scope_clause())
        .group_by(Participant.athlete_id)
    )
    total_by_athlete = {row.athlete_id: row.cnt for row in total_counts}
    return total_by_athlete, free_by_athlete


def _check_names_against_db_free(names_or_entries, season=None):
    """Проверка списка ФИО (или [{fio, birth_date}]) по БД с учётом БЕСП за сезон.
    Возвращает (has_free, no_free, fio_only_matches, not_found):
    - has_free: [(display_fio, match_info, total_participations, free_count), ...]
    - no_free: [(display_fio, match_info, total_participations, 0), ...]
    - fio_only_matches: [(display_fio, match_info, total_participations, free_count), ...]
    - not_found: [display_fio, ...]
    ВАЖНО: если по одному ФИО найдено несколько id, каждый id раскладывается отдельно
    в свою колонку (с БЕСП / без БЕСП), чтобы не смешивать разных людей.
    Счётчики участий и БЕСП — только за выбранный сезон (по умолчанию активный).
    """
    if not names_or_entries:
        return [], [], [], []
    season = season or get_active_season()
    found, fio_only_found, not_found = _check_names_against_db(names_or_entries, season=season)
    total_by_athlete, free_by_athlete = _get_participation_counts(season)
    has_free = []
    no_free = []
    fio_only_matches = []
    for fio, matches in found:
        # Каждый match рассматриваем отдельно, чтобы не объединять разных людей с одинаковым ФИО
        for match in matches:
            athlete_id = match['id']
            total = total_by_athlete.get(athlete_id, 0)
            free = free_by_athlete.get(athlete_id, 0)
            if free > 0:
                has_free.append((fio, match, total, free, athlete_id))
            else:
                no_free.append((fio, match, total, 0, athlete_id))

    # Мягкий fallback: нет точного ФИО, но есть совпадения по ФИ.
    for fio, matches in fio_only_found:
        for match in matches:
            athlete_id = match['id']
            total = total_by_athlete.get(athlete_id, 0)
            free = free_by_athlete.get(athlete_id, 0)
            fio_only_matches.append((fio, match, total, free, athlete_id))

    return has_free, no_free, fio_only_matches, not_found


@analytics_bp.route('/analytics')
def analytics():
    """Страница аналитики"""
    return render_template('analytics.html')

@analytics_bp.route('/free-participation')
def free_participation():
    """Страница спортсменов с бесплатным участием"""
    return render_template('free_participation.html')

@analytics_bp.route('/club-free-analysis')
def club_free_analysis():
    """Страница анализа бесплатного участия по школам"""
    return render_template('club_free_analysis.html')


@analytics_bp.route('/school-segment-event-ranks')
def school_segment_event_ranks():
    """Участия по типам школ: МАФКК / ЦСКА Жук / коммерческие — несколько срезов и PDF."""
    from services.school_segment_stats import (
        build_event_rank_school_segment_report,
        build_per_category_school_segment_report,
        build_per_event_category_school_segment_report,
        build_per_event_school_segment_report,
        count_distinct_athletes_filtered,
    )

    reports = {
        'overall': build_event_rank_school_segment_report(db.session),
        'events': build_per_event_school_segment_report(db.session),
        'categories': build_per_category_school_segment_report(db.session),
        'event_categories': build_per_event_category_school_segment_report(db.session),
    }

    distinct_athletes_filtered = count_distinct_athletes_filtered(db.session)
    return render_template(
        'school_segment_event_rank.html',
        reports=reports,
        distinct_athletes_filtered=distinct_athletes_filtered,
    )


@analytics_bp.route('/school-segment-report.pdf')
def school_segment_report_pdf():
    """Скачать PDF отчёта МАФКК / ЦСКА / коммерция. kind=overall|events|categories|event_categories."""
    from services.pdf_generator import generate_school_segment_pdf_bytes
    from services.school_segment_stats import (
        build_event_rank_school_segment_report,
        build_per_category_school_segment_report,
        build_per_event_category_school_segment_report,
        build_per_event_school_segment_report,
        count_distinct_athletes_filtered,
    )

    kind = (request.args.get('kind') or 'overall').strip().lower()
    builders = {
        'overall': build_event_rank_school_segment_report,
        'events': build_per_event_school_segment_report,
        'categories': build_per_category_school_segment_report,
        'event_categories': build_per_event_category_school_segment_report,
    }
    if kind not in builders:
        kind = 'overall'

    report = builders[kind](db.session)
    report['distinct_athletes_filtered'] = count_distinct_athletes_filtered(db.session)
    pdf_bytes = generate_school_segment_pdf_bytes(report, kind)
    filename = f'school-segment-{kind}-{date.today().isoformat()}.pdf'
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename,
    )

@analytics_bp.route('/free-participation-analysis')
def free_participation_analysis():
    """Страница анализа бесплатного участия с фильтрацией"""
    return render_template('free_participation_analysis.html')


@analytics_bp.route('/judge-helper-free', methods=['GET', 'POST'])
def judge_helper_free():
    """Помощник главным судьям — только для бесплатных участий: кто уже выступал с БЕСП, кто только платно, кого нет в базе."""
    has_free = []
    no_free = []
    fio_only_matches = []
    not_found = []
    pasted = ''
    upload_error = None

    # Сезон для подсчёта участий/БЕСП: из формы или активный (по умолчанию текущий, сейчас 2026/27)
    if request.method == 'POST':
        season = get_active_season(request.form.get('season'))
    else:
        season = get_active_season(request.args.get('season'))

    if request.method == 'POST':
        raw_body = request.form.get('names_text') or ''
        pasted = raw_body.strip()
        entries = _parse_pasted_entries(pasted)

        upload = request.files.get('reg_file')
        if upload and upload.filename:
            filename = (upload.filename or '').lower()
            if filename.endswith(('.xlsx', '.xlsm')):
                try:
                    xlsx_entries = _parse_xlsx_entries(upload)
                    if xlsx_entries:
                        # Файл дополняет/заменяет текстовую вставку
                        entries = _dedupe_entries(entries + xlsx_entries)
                        if not pasted:
                            pasted = '\n'.join(
                                _format_entry_label(e['fio'], e.get('birth_date'))
                                for e in xlsx_entries
                            )
                    else:
                        upload_error = 'В файле не найдены строки с ФИО (ожидаются колонки «Фамилия Имя» и «Дата рождения»).'
                except Exception as exc:
                    logger.warning('Judge helper xlsx parse: %s', exc, exc_info=True)
                    upload_error = 'Не удалось прочитать Excel-файл. Сохраните выгрузку как .xlsx и попробуйте снова.'
            else:
                upload_error = 'Нужен файл .xlsx (выгрузка с сайта регистрации).'

        if entries:
            has_free, no_free, fio_only_matches, not_found = _check_names_against_db_free(entries, season=season)
        else:
            has_free = no_free = fio_only_matches = not_found = []

        truncated = False
        stored_raw = raw_body
        if len(stored_raw) > _JUDGE_HELPER_NAMES_RAW_MAX:
            stored_raw = stored_raw[:_JUDGE_HELPER_NAMES_RAW_MAX]
            truncated = True
        if upload and upload.filename:
            stored_raw = (stored_raw + f'\n[upload:{upload.filename};rows={len(entries)};season={season}]').strip()
        elif entries:
            stored_raw = (stored_raw + f'\n[season={season}]').strip()

        try:
            row = JudgeHelperFreeAudit(
                remote_addr=(get_client_ip(request) or '')[:45],
                reader_logged_in=bool(session.get(SESSION_SITE_READER_KEY)),
                parsed_names_count=len(entries),
                input_char_len=len(raw_body),
                names_raw=stored_raw if stored_raw else None,
                input_truncated=truncated,
                result_has_free=len(has_free),
                result_no_free=len(no_free),
                result_fio_only=len(fio_only_matches),
                result_not_found=len(not_found),
            )
            db.session.add(row)
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            logger.warning('Judge helper free audit: %s', exc, exc_info=True)
    return render_template(
        'judge_helper_free.html',
        has_free=has_free,
        no_free=no_free,
        fio_only_matches=fio_only_matches,
        not_found=not_found,
        pasted=pasted,
        upload_error=upload_error,
        helper_season=season,
        helper_season_label=get_season_display_name(season),
    )


@analytics_bp.route('/first-timers-detail')
def first_timers_detail():
    """Детальный отчёт «Новички и повторяющиеся»: по каждому турниру и разряду — кто повторяющийся и откуда (где выступал раньше)."""
    from google_sheets_sync import get_events_first_timers_report_data
    rank = (request.args.get('rank') or '').strip() or None
    free_only = request.args.get('free_only', '').strip().lower() in ('1', 'true', 'yes')
    report = get_events_first_timers_report_data(rank_contains=rank, free_only=free_only)
    page_title = "Новички и повторяющиеся — детальный отчёт" if not rank else f"Новички и повторяющиеся — {rank}"
    if free_only:
        page_title = "Новички и повторяющиеся — только бесплатные участия"
    pdf_url = url_for('analytics.first_timers_detail_pdf', rank=rank or None, free_only=1 if free_only else None)
    return render_template('first_timers_detail.html', report=report, page_title=page_title, pdf_url=pdf_url, is_free_only=free_only)


@analytics_bp.route('/first-timers-detail-1-sport')
def first_timers_detail_1_sport():
    """Детальный отчёт «Новички и повторяющиеся» только для разрядов «1 Спортивный»."""
    from google_sheets_sync import get_events_first_timers_report_data
    rank = "1 Спортивный"
    report = get_events_first_timers_report_data(rank_contains=rank)
    page_title = f"Новички и повторяющиеся — {rank}"
    pdf_url = url_for('analytics.first_timers_detail_pdf', rank=rank)
    return render_template('first_timers_detail.html', report=report, page_title=page_title, pdf_url=pdf_url, is_free_only=False)


@analytics_bp.route('/first-timers-detail-free')
def first_timers_detail_free():
    """Детальный отчёт «Новички и повторяющиеся» только по бесплатным участиям (БЕСП)."""
    from google_sheets_sync import get_events_first_timers_report_data
    report = get_events_first_timers_report_data(free_only=True)
    page_title = "Новички и повторяющиеся — только бесплатные участия"
    pdf_url = url_for('analytics.first_timers_detail_pdf', free_only=1)
    return render_template('first_timers_detail.html', report=report, page_title=page_title, pdf_url=pdf_url, is_free_only=True)


@analytics_bp.route('/first-timers-detail.pdf')
def first_timers_detail_pdf():
    """Скачать детальный отчёт «Новички и повторяющиеся» в PDF."""
    from google_sheets_sync import get_events_first_timers_report_data
    from services.pdf_generator import generate_first_timers_detail_pdf_bytes

    rank = (request.args.get('rank') or '').strip() or None
    free_only = request.args.get('free_only', '').strip().lower() in ('1', 'true', 'yes')
    report = get_events_first_timers_report_data(rank_contains=rank, free_only=free_only)
    if free_only:
        title = "Новички и повторяющиеся — только бесплатные участия"
    else:
        title = "Новички и повторяющиеся — детальный отчёт" if not rank else f"Новички и повторяющиеся — {rank}"
    pdf_bytes = generate_first_timers_detail_pdf_bytes(report, title=title)

    def _safe_part(s: str) -> str:
        s = re.sub(r"\s+", "-", (s or "").strip())
        s = re.sub(r"[^0-9A-Za-zА-Яа-яЁё._-]+", "", s)
        return (s[:60] or "filter")

    suffix = ""
    if free_only:
        suffix = "-free"
    elif rank:
        suffix = f"-{_safe_part(rank)}"
    filename = f"first-timers-detail{suffix}-{date.today().isoformat()}.pdf"

    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename,
    )
