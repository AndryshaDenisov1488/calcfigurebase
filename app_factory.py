#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Flask application factory."""
import os
from flask import Flask
from dotenv import load_dotenv

from config import get_config
from extensions import db, migrate, cors, limiter
from utils.logging_config import setup_logging
from utils.formatters import format_season, format_month_filter

def create_app():
    load_dotenv()
    app = Flask(__name__)
    config = get_config()
    app.config.update(config)

    setup_logging(config['LOG_LEVEL'], config['LOG_FILE'])

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    db.init_app(app)
    # Import models so metadata is populated for migrations.
    import models  # noqa: F401
    migrate.init_app(app, db)
    cors.init_app(app)
    limiter.init_app(app)

    app.template_global()(format_season)
    app.template_filter('format_month')(format_month_filter)

    from routes.public import public_bp
    from routes.admin import admin_bp
    from routes.api import api_bp
    from routes.analytics import analytics_bp
    from routes.errors import register_error_handlers

    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(analytics_bp)
    register_error_handlers(app)

    # Убираем 404 в логах от запросов браузера к /favicon.ico
    @app.route('/favicon.ico')
    def favicon():
        return '', 204

    return app
