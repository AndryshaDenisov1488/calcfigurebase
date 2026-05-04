#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Доступ к JSON API: сессия админа/судьи, API-ключ или отключение проверки (только dev)."""
import os
from flask import session, current_app

SESSION_SITE_READER_KEY = 'site_reader_ok'

_HTML_GATE_SKIP_ENDPOINTS_PUBLIC = frozenset({
    'public.site_access',
    'public.site_reader_logout',
})


def public_html_gate_enabled():
    """
    HTML-страницы с данными закрываются для гостей, если задан SITE_READ_PASSWORD.
    Отключение: DISABLE_PUBLIC_HTML_GATE=1 (экстренный режим).
    """
    if os.environ.get('DISABLE_PUBLIC_HTML_GATE', '').lower() in ('1', 'true', 'yes'):
        return False
    if not current_app:
        return False
    return bool((current_app.config.get('SITE_READ_PASSWORD') or '').strip())


def session_has_reader_or_admin():
    return bool(session.get('admin_logged_in') or session.get(SESSION_SITE_READER_KEY))


def safe_same_site_redirect_path(candidate):
    """Только относительный путь на этом же сайте (без open redirect)."""
    if not candidate or not isinstance(candidate, str):
        return None
    candidate = candidate.strip()
    if not candidate.startswith('/') or candidate.startswith('//'):
        return None
    if '\n' in candidate or '\r' in candidate:
        return None
    return candidate


def should_redirect_public_html_request(endpoint):
    if not public_html_gate_enabled():
        return False
    if endpoint in _HTML_GATE_SKIP_ENDPOINTS_PUBLIC:
        return False
    if session_has_reader_or_admin():
        return False
    return True


def api_auth_disabled():
    return os.environ.get('DISABLE_PUBLIC_API_AUTH', '').lower() in ('1', 'true', 'yes')


def request_has_api_access():
    if api_auth_disabled():
        return True
    if session.get('admin_logged_in'):
        return True
    if session.get(SESSION_SITE_READER_KEY):
        return True
    auth_header = request.headers.get('Authorization', '')
    token = ''
    if auth_header.lower().startswith('bearer '):
        token = auth_header[7:].strip()
    if not token:
        token = request.headers.get('X-API-Key', '').strip()
    keys = []
    if current_app:
        keys = current_app.config.get('API_KEYS') or []
    if token and keys and token in keys:
        return True
    return False
