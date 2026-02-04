#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Analytics HTML routes."""
from flask import Blueprint, render_template

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
    report = get_events_first_timers_report_data()
    return render_template('first_timers_detail.html', report=report)
