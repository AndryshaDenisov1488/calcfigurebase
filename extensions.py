#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Application extensions (SQLAlchemy, Migrate, CORS, Limiter).
"""
import os
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
# Это нужно сделать ДО чтения REDIS_URL
load_dotenv()

db = SQLAlchemy()
migrate = Migrate()
cors = CORS()

# Настройка Limiter с поддержкой Redis (если доступен)
# Если REDIS_URL не указан, используется in-memory хранилище (для разработки)
redis_url = os.environ.get('REDIS_URL')
if redis_url:
    # Используем Redis для rate limiting
    limiter = Limiter(
        key_func=get_remote_address,
        storage_uri=redis_url,
        default_limits=["1000 per hour", "100 per minute"]
    )
else:
    # In-memory хранилище (для разработки или если Redis недоступен)
    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=["1000 per hour", "100 per minute"]
    )
