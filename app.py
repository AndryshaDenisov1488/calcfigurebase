#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flask веб-приложение для управления турнирами по фигурному катанию
"""

from flask import Flask, render_template, request
from flask_migrate import Migrate
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
import os
import logging

# Импорты из новых модулей
from config.settings import Config
from utils.logging_config import setup_logging
from models import db

# Импорты Blueprint'ов
from routes.main import main_bp
from routes.admin import admin_bp, upload_bp
from api.endpoints import api_bp

# Загружаем переменные окружения
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)

# Применяем конфигурацию
try:
    app.config.from_object(Config)
except ValueError as e:
    # Если конфигурация не задана, выводим понятное сообщение
    print(f"\n{'='*60}")
    print("ОШИБКА КОНФИГУРАЦИИ!")
    print(f"{'='*60}")
    print(f"\n{e}")
    print("\nСоздайте файл .env на основе .env.example и заполните все обязательные переменные:")
    print("  - SECRET_KEY")
    print("  - ADMIN_USERNAME")
    print("  - ADMIN_PASSWORD_HASH (используйте scripts/generate_password_hash.py для генерации)")
    print(f"\n{'='*60}\n")
    raise

# Добавляем функции в контекст Jinja2
@app.template_global()
def format_season(date_obj):
    """Форматирует дату в сезон YYYY/YY"""
    if not date_obj:
        return "Неизвестно"
    
    if date_obj.month >= 7:
        # Сезон начинается в этом году
        start_year = date_obj.year
        end_year = date_obj.year + 1
    else:
        # Сезон начался в прошлом году
        start_year = date_obj.year - 1
        end_year = date_obj.year
    
    return f"{start_year}/{str(end_year)[-2:]}"

@app.template_filter('format_month')
def format_month_filter(month_str):
    """Форматирует месяц из формата YYYY-MM в читаемый вид"""
    if not month_str:
        return ""
    
    months_ru = {
        '01': 'Январь', '02': 'Февраль', '03': 'Март', '04': 'Апрель',
        '05': 'Май', '06': 'Июнь', '07': 'Июль', '08': 'Август',
        '09': 'Сентябрь', '10': 'Октябрь', '11': 'Ноябрь', '12': 'Декабрь'
    }
    
    try:
        year, month = month_str.split('-')
        return f"{months_ru.get(month, month)} {year}"
    except (ValueError, AttributeError):
        return month_str

# Настройка логирования с ротацией
setup_logging(
    log_level=app.config['LOG_LEVEL'],
    log_file=app.config['LOG_FILE']
)
logger = logging.getLogger(__name__)

# Создаем папку для загрузок
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Настройка rate limiting
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{app.config['RATE_LIMIT_PER_MINUTE']} per minute"]
)
limiter.init_app(app)

# Настройка CSRF защиты (только если включено в конфиге)
if app.config.get('WTF_CSRF_ENABLED', True):
    csrf = CSRFProtect(app)
    
    # Добавляем функцию csrf_token в контекст шаблонов
    @app.context_processor
    def inject_csrf_token():
        from flask_wtf.csrf import generate_csrf
        return dict(csrf_token=lambda: generate_csrf())
else:
    csrf = None
    
    # Если CSRF отключен, добавляем пустую функцию
    @app.context_processor
    def inject_csrf_token():
        return dict(csrf_token=lambda: '')

migrate = Migrate(app, db)
CORS(app)

# Настройка connection pooling для PostgreSQL
if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgresql'):
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = app.config.get('SQLALCHEMY_ENGINE_OPTIONS', {})

# Инициализация базы данных
db.init_app(app)

# Обработчики ошибок
@app.errorhandler(404)
def not_found_error(error):
    logger.warning(f"404 error: {request.url} from {request.remote_addr}")
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"500 error: {error} from {request.remote_addr}")
    db.session.rollback()
    return render_template('500.html'), 500

@app.errorhandler(413)
def too_large(error):
    logger.warning(f"File too large from {request.remote_addr}")
    from flask import flash, redirect, url_for
    flash('Файл слишком большой. Максимальный размер: 16MB', 'error')
    return redirect(url_for('upload.upload_file'))

# Security headers
@app.after_request
def set_security_headers(response):
    """Устанавливает security headers для защиты от различных атак"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Content-Security-Policy'] = "default-src 'self'"
    return response

# Регистрация Blueprint'ов
app.register_blueprint(main_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(upload_bp)
app.register_blueprint(api_bp)

# Исключаем API endpoints из CSRF после регистрации
if csrf:
    csrf.exempt(api_bp)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    # Используем host и port из конфигурации
    app.run(
        debug=app.config.get('DEBUG', False),
        host=app.config.get('FLASK_HOST', '127.0.0.1'),
        port=app.config.get('FLASK_PORT', 5001)
    )

# Для продакшена на Beget
if __name__ != '__main__':
    with app.app_context():
        db.create_all()
