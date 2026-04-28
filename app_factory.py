#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Flask application factory."""
import logging
import os
from flask import Flask
from dotenv import load_dotenv
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from config import get_config
from extensions import db, migrate, cors, limiter
from utils.logging_config import setup_logging
from utils.formatters import format_season, format_month_filter


logger = logging.getLogger(__name__)


def _ensure_event_rank_column(app):
    """Add the nullable event_rank column on existing DBs created before it existed."""
    with app.app_context():
        inspector = inspect(db.engine)
        if not inspector.has_table('event'):
            return

        columns = {col['name'] for col in inspector.get_columns('event')}
        if 'event_rank' not in columns:
            column_type = 'TEXT' if db.engine.dialect.name == 'sqlite' else 'VARCHAR(50)'
            try:
                db.session.execute(text(f'ALTER TABLE event ADD COLUMN event_rank {column_type}'))
                db.session.commit()
                logger.info('Added missing event.event_rank column')
            except SQLAlchemyError as exc:
                db.session.rollback()
                message = str(exc).lower()
                if 'duplicate column' not in message and 'already exists' not in message:
                    raise

        indexes = {idx['name'] for idx in inspector.get_indexes('event')}
        if 'ix_event_event_rank' not in indexes:
            try:
                db.session.execute(text('CREATE INDEX ix_event_event_rank ON event (event_rank)'))
                db.session.commit()
            except SQLAlchemyError as exc:
                db.session.rollback()
                message = str(exc).lower()
                if 'already exists' not in message and 'duplicate' not in message:
                    raise


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
    _ensure_event_rank_column(app)
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
