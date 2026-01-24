#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Application configuration loaded from environment variables.
"""
import os
import secrets
from datetime import timedelta

def get_config():
    """Return Flask config dictionary."""
    return {
        'SECRET_KEY': os.environ.get('SECRET_KEY', secrets.token_hex(32)),
        'SQLALCHEMY_DATABASE_URI': os.environ.get('DATABASE_URL', 'sqlite:///figure_skating.db'),
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'UPLOAD_FOLDER': os.environ.get('UPLOAD_FOLDER', 'uploads'),
        'MAX_CONTENT_LENGTH': int(os.environ.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024)),
        'PERMANENT_SESSION_LIFETIME': timedelta(seconds=int(os.environ.get('SESSION_TIMEOUT', 3600))),
        'ADMIN_USERNAME': os.environ.get('ADMIN_USERNAME', 'admin'),
        'ADMIN_PASSWORD': os.environ.get('ADMIN_PASSWORD'),
        'ADMIN_PASSWORD_HASH': os.environ.get('ADMIN_PASSWORD_HASH'),
        'LOG_LEVEL': os.environ.get('LOG_LEVEL', 'INFO'),
        'LOG_FILE': os.environ.get('LOG_FILE', 'logs/app.log'),
        'RATE_LIMIT_PER_MINUTE': os.environ.get('RATE_LIMIT_PER_MINUTE', 60),
        'SESSION_COOKIE_HTTPONLY': True,
        'SESSION_COOKIE_SAMESITE': 'Lax',
        'SESSION_COOKIE_SECURE': os.environ.get('SESSION_COOKIE_SECURE', '0') == '1',
    }
