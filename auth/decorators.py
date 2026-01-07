#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Декораторы для аутентификации
"""

from functools import wraps
from flask import session, redirect, url_for, flash, request
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

def admin_required(f):
    """Декоратор для проверки авторизации администратора"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from flask import current_app
        
        if not session.get('admin_logged_in'):
            logger.warning(f"Unauthorized access attempt to {request.endpoint} from {request.remote_addr}")
            flash('Необходима авторизация администратора', 'error')
            return redirect(url_for('admin_login'))
        
        # Проверяем время сессии
        if 'last_activity' in session:
            last_activity = datetime.fromisoformat(session['last_activity'])
            session_lifetime = current_app.config['PERMANENT_SESSION_LIFETIME']
            if datetime.now() - last_activity > timedelta(seconds=session_lifetime.total_seconds()):
                session.clear()
                logger.info(f"Session expired for admin from {request.remote_addr}")
                flash('Сессия истекла. Войдите заново.', 'warning')
                return redirect(url_for('admin_login'))
        
        # Обновляем время последней активности
        session['last_activity'] = datetime.now().isoformat()
        return f(*args, **kwargs)
    return decorated_function

