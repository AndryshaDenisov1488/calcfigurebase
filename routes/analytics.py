#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Analytics HTML routes."""
from datetime import date
import io
import re

from flask import Blueprint, render_template, request, send_file, url_for
from extensions import db
from models import Athlete

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
    Сохраняем полное ФИО как вставил судья (для отображения); поиск по БД — по фамилии и имени (2 слова)."""
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
        fio_key = (words[0], words[1])
        if fio_key in seen:
            continue
        seen.add(fio_key)
        result.append(ln)
    return result


def _check_names_against_db(names):
    """По списку «Фамилия Имя» вернуть (found, not_found). found = [(name, [(id, full_name), ...]), ...]."""
    if not names:
        return [], []
    # Собираем по два слова из каждой записи
    name_keys = []
    for fio in names:
        words = _normalize_words(fio)
        if len(words) >= 2:
            name_keys.append((fio, frozenset(words[:2])))
    if not name_keys:
        return [], list(names)
    # Все спортсмены из БД: (id, full_name, set слов)
    athletes_data = []
    for a in Athlete.query.all():
        name = a.full_name
        words = set(_normalize_words(name))
        if words:
            athletes_data.append((a.id, name, words))
    found = []
    not_found = []
    seen_key = set()
    for fio, key in name_keys:
        if key in seen_key:
            continue
        seen_key.add(key)
        matches = [(aid, db_name) for aid, db_name, name_words in athletes_data if key <= name_words]
        if matches:
            found.append((fio, matches))
        else:
            not_found.append(fio)
    return found, not_found

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

@analytics_bp.route('/free-participation-analysis')
def free_participation_analysis():
    """Страница анализа бесплатного участия с фильтрацией"""
    return render_template('free_participation_analysis.html')


@analytics_bp.route('/judge-helper', methods=['GET', 'POST'])
def judge_helper():
    """Помощник главным судьям: вставка списка ФИО (по 4 строки на человека) и проверка, кого нет в БД."""
    found = []
    not_found = []
    pasted = ''
    if request.method == 'POST':
        pasted = (request.form.get('names_text') or '').strip()
        names = _parse_pasted_list(pasted)
        if names:
            found, not_found = _check_names_against_db(names)
    return render_template('judge_helper.html', found=found, not_found=not_found, pasted=pasted)


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
    import re

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
