#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Analytics HTML routes."""
from datetime import date
import io

from flask import Blueprint, render_template, request, send_file, url_for

analytics_bp = Blueprint('analytics', __name__)

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
