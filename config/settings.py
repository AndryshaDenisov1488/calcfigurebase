#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Конфигурация приложения
"""

import os
from datetime import timedelta
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

class Config:
    """Базовая конфигурация"""
    
    # SECRET_KEY - ОБЯЗАТЕЛЬНО должен быть задан через переменные окружения!
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError("SECRET_KEY должен быть задан через переменную окружения!")
    
    # База данных
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///figure_skating.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Загрузка файлов
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))
    
    # Сессии
    PERMANENT_SESSION_LIFETIME = timedelta(seconds=int(os.environ.get('SESSION_TIMEOUT', 3600)))
    
    # Админские данные - ОБЯЗАТЕЛЬНО через переменные окружения!
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME')
    ADMIN_PASSWORD_HASH = os.environ.get('ADMIN_PASSWORD_HASH')  # Хеш пароля
    
    if not ADMIN_USERNAME:
        raise ValueError("ADMIN_USERNAME должен быть задан через переменную окружения!")
    if not ADMIN_PASSWORD_HASH:
        raise ValueError("ADMIN_PASSWORD_HASH должен быть задан через переменную окружения!")
    
    # Логирование
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = os.environ.get('LOG_FILE', 'logs/app.log')
    
    # Rate limiting
    RATE_LIMIT_PER_MINUTE = int(os.environ.get('RATE_LIMIT_PER_MINUTE', 60))
    
    # Debug режим - только для разработки!
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    # CSRF Protection (Flask-WTF)
    WTF_CSRF_ENABLED = os.environ.get('WTF_CSRF_ENABLED', 'True').lower() == 'true'
    WTF_CSRF_TIME_LIMIT = int(os.environ.get('WTF_CSRF_TIME_LIMIT', 3600))
    WTF_CSRF_SECRET_KEY = os.environ.get('WTF_CSRF_SECRET_KEY') or os.environ.get('SECRET_KEY')
    
    # Connection Pooling для PostgreSQL (если используется)
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': int(os.environ.get('DB_POOL_SIZE', 10)),
        'pool_recycle': int(os.environ.get('DB_POOL_RECYCLE', 3600)),
        'pool_pre_ping': os.environ.get('DB_POOL_PRE_PING', 'True').lower() == 'true',
        'max_overflow': int(os.environ.get('DB_MAX_OVERFLOW', 20))
    }
    
    # Host и Port для запуска
    FLASK_HOST = os.environ.get('FLASK_HOST', '127.0.0.1')
    FLASK_PORT = int(os.environ.get('FLASK_PORT', 5001))

