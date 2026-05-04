#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Analytics HTML routes."""
from datetime import date
import io
import re

from flask import Blueprint, render_template, request, send_file, url_for

from sqlalchemy import func
from extensions import db
from models import Athlete, Participant, Event, Category

analytics_bp = Blueprint('analytics', __name__)


def _normalize_words(s):
    if not s or not isinstance(s, str):
        return []
    s = re.sub(r'\s+', ' ', (s or '').strip()).lower()
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


def _parse_pasted_list(text):
    """Умный разбор: из вставленного текста извлечь все строки, похожие на ФИО (игнорируя год, разряд, город/школу).
    Сохраняем полное ФИО как вставил судья (для отображения).
    Поиск по БД:
    - если введено отчество, матчим по 3 словам (фамилия+имя+отчество)
    - если отчества нет, матчим по 2 словам (фамилия+имя)"""
    lines = [ln.strip() for ln in (text or '').splitlines() if ln.strip()]
    result = []
    seen = set()
    for ln in lines:
        if _is_year(ln) or _is_rank(ln) or _is_city_or_school(ln):
            continue
        if not _looks_like_fio(ln):
            continue
        words = _normalize_words(ln)
        if len(words) < 2:
            continue
        # Не схлопываем разных людей с одинаковыми фамилией+именем:
        # если есть отчество, считаем ключ по 3 словам.
        fio_key = tuple(words[:3]) if len(words) >= 3 else tuple(words[:2])
        if fio_key in seen:
            continue
        seen.add(fio_key)
        result.append(ln)
    return result


def _check_names_against_db(names):
    """По списку ФИО вернуть (found, fio_only_matches, not_found).
    found = [(name, [match_info, ...]), ...], где match_info содержит:
      id, full_name, birth_date, patronymic, rank
    fio_only_matches = [(input_fio, [match_info, ...]), ...] — когда точного ФИО нет,
      но есть совпадения по фамилии+имени
    """
    if not names:
        return [], [], []
    # Собираем ключи поиска:
    # - full_key (3 слова), если в вводе есть отчество
    # - base_key (2 слова) для случая без отчества
    name_keys = []
    for fio in names:
        words = _normalize_words(fio)
        if len(words) >= 2:
            base_key = frozenset(words[:2])
            full_key = frozenset(words[:3]) if len(words) >= 3 else None
            dedup_key = tuple(words[:3]) if len(words) >= 3 else tuple(words[:2])
            name_keys.append((fio, base_key, full_key, dedup_key))
    if not name_keys:
        return [], [], list(names)
    # Все спортсмены из БД: (id, full_name, set слов)
    athletes_data = []
    for a in Athlete.query.all():
        name = a.full_name
        words = set(_normalize_words(name))
        if words:
            athletes_data.append((a.id, name, words))
    found = []
    fio_only_matches = []
    not_found = []
    seen_key = set()
    for fio, base_key, full_key, dedup_key in name_keys:
        if dedup_key in seen_key:
            continue
        seen_key.add(dedup_key)

        # Если ввели отчество — ищем точное совпадение по 3 словам.
        if full_key:
            raw_matches = [(aid, db_name) for aid, db_name, name_words in athletes_data if full_key <= name_words]
            if not raw_matches:
                # Мягкий fallback: точного ФИО нет, но есть совпадения по ФИ.
                base_matches = [(aid, db_name) for aid, db_name, name_words in athletes_data if base_key <= name_words]
                matches = _enrich_matches(base_matches)
                if matches:
                    fio_only_matches.append((fio, matches))
                    continue
        else:
            # Без отчества показываем все варианты с одинаковыми фамилией и именем.
            raw_matches = [(aid, db_name) for aid, db_name, name_words in athletes_data if base_key <= name_words]

        matches = _enrich_matches(raw_matches)
        if matches:
            found.append((fio, matches))
        else:
            not_found.append(fio)
    return found, fio_only_matches, not_found


def _enrich_matches(raw_matches):
    """Добавляет метаданные к совпадениям: дата рождения, отчество, текущий/последний разряд."""
    if not raw_matches:
        return []

    athlete_ids = [aid for aid, _ in raw_matches]

    athletes = Athlete.query.filter(Athlete.id.in_(athlete_ids)).all()
    athlete_map = {a.id: a for a in athletes}

    # Последний разряд по дате турнира (при равенстве дат — по более новой записи Participant.id)
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
        .filter(Participant.athlete_id.in_(athlete_ids))
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


def _get_participation_counts():
    """Возвращает (total_by_athlete, free_by_athlete) — словари athlete_id -> count."""
    free_counts = (
        db.session.query(Participant.athlete_id, func.count(Participant.id).label('cnt'))
        .join(Event, Participant.event_id == Event.id)
        .filter(
            Participant.pct_ppname == 'БЕСП',
            db.or_(Participant.exclude_free_from_reports.is_(False), Participant.exclude_free_from_reports.is_(None)),
            db.or_(Event.exclude_free_from_reports.is_(False), Event.exclude_free_from_reports.is_(None))
        )
        .group_by(Participant.athlete_id)
    )
    free_by_athlete = {row.athlete_id: row.cnt for row in free_counts}
    total_counts = (
        db.session.query(Participant.athlete_id, func.count(Participant.id).label('cnt'))
        .group_by(Participant.athlete_id)
    )
    total_by_athlete = {row.athlete_id: row.cnt for row in total_counts}
    return total_by_athlete, free_by_athlete


def _check_names_against_db_free(names):
    """Проверка списка ФИО по БД с учётом бесплатных участий (БЕСП).
    Возвращает (has_free, no_free, fio_only_matches, not_found):
    - has_free: [(display_fio, match_info, total_participations, free_count), ...]
    - no_free: [(display_fio, match_info, total_participations, 0), ...]
    - fio_only_matches: [(display_fio, match_info, total_participations, free_count), ...]
    - not_found: [display_fio, ...]
    ВАЖНО: если по одному ФИО найдено несколько id, каждый id раскладывается отдельно
    в свою колонку (с БЕСП / без БЕСП), чтобы не смешивать разных людей.
    """
    if not names:
        return [], [], [], []
    found, fio_only_found, not_found = _check_names_against_db(names)
    total_by_athlete, free_by_athlete = _get_participation_counts()
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
    if request.method == 'POST':
        pasted = (request.form.get('names_text') or '').strip()
        names = _parse_pasted_list(pasted)
        if names:
            has_free, no_free, fio_only_matches, not_found = _check_names_against_db_free(names)
    return render_template(
        'judge_helper_free.html',
        has_free=has_free,
        no_free=no_free,
        fio_only_matches=fio_only_matches,
        not_found=not_found,
        pasted=pasted,
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
