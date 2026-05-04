#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Application configuration loaded from environment variables.
"""
import os
import secrets
from datetime import timedelta

# Каталог проекта (рядом с этим файлом). Нужен для SQLite URI с относительным путём:
# у Gunicorn cwd воркера не всегда совпадает с корнем сайта → «unable to open database file».
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


def _resolve_sqlite_database_uri(uri):
    if not uri.startswith('sqlite:///'):
        return uri
    tail = uri[len('sqlite:///'):]
    if tail.startswith(':memory:'):
        return uri
    if os.path.isabs(tail):
        return uri
    abs_path = os.path.normpath(os.path.join(_PROJECT_ROOT, tail))
    return 'sqlite:///' + abs_path


def _parse_api_keys():
    raw = os.environ.get('API_KEYS', '').strip()
    return [x.strip() for x in raw.split(',') if x.strip()]


def get_config():
    """Return Flask config dictionary."""
    from utils.security_startup import is_security_relaxed

    relaxed = is_security_relaxed()
    secret_key = os.environ.get('SECRET_KEY')
    if not secret_key:
        if relaxed:
            secret_key = secrets.token_hex(32)
        else:
            secret_key = ''

    database_uri = (
        os.environ.get('DATABASE_URL')
        or os.environ.get('SQLALCHEMY_DATABASE_URI')
        or 'sqlite:///figure_skating.db'
    )
    database_uri = _resolve_sqlite_database_uri(database_uri)

    return {
        'SECRET_KEY': secret_key,
        'SQLALCHEMY_DATABASE_URI': database_uri,
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'UPLOAD_FOLDER': os.environ.get('UPLOAD_FOLDER', 'uploads'),
        'MAX_CONTENT_LENGTH': int(os.environ.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024)),
        'PERMANENT_SESSION_LIFETIME': timedelta(seconds=int(os.environ.get('SESSION_TIMEOUT', 3600))),
        'ADMIN_USERNAME': os.environ.get('ADMIN_USERNAME', 'admin'),
        'ADMIN_PASSWORD': os.environ.get('ADMIN_PASSWORD'),
        'ADMIN_PASSWORD_HASH': os.environ.get('ADMIN_PASSWORD_HASH'),
        'SITE_READ_PASSWORD': os.environ.get('SITE_READ_PASSWORD', '').strip(),
        'API_KEYS': _parse_api_keys(),
        'LOG_LEVEL': os.environ.get('LOG_LEVEL', 'INFO'),
        'LOG_FILE': os.environ.get('LOG_FILE', 'logs/app.log'),
        'RATE_LIMIT_PER_MINUTE': os.environ.get('RATE_LIMIT_PER_MINUTE', 60),
        'SESSION_COOKIE_HTTPONLY': True,
        'SESSION_COOKIE_SAMESITE': 'Lax',
        'SESSION_COOKIE_SECURE': os.environ.get('SESSION_COOKIE_SECURE', '0') == '1',
        'WTF_CSRF_TIME_LIMIT': None,
    }
