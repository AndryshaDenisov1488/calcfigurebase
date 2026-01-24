#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Authentication helpers."""
from functools import wraps
from datetime import datetime
from flask import session, request, redirect, url_for, flash, current_app
import logging

logger = logging.getLogger(__name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            logger.warning(f"Unauthorized access attempt to {request.endpoint} from {request.remote_addr}")
            flash('Необходима авторизация администратора', 'error')
            return redirect(url_for('admin.admin_login'))
        if 'last_activity' in session:
            last_activity = datetime.fromisoformat(session['last_activity'])
            if datetime.now() - last_activity > current_app.config['PERMANENT_SESSION_LIFETIME']:
                session.clear()
                logger.info(f"Session expired for admin from {request.remote_addr}")
                flash('Сессия истекла. Войдите заново.', 'warning')
                return redirect(url_for('admin.admin_login'))
        session['last_activity'] = datetime.now().isoformat()
        return f(*args, **kwargs)
    return decorated_function
