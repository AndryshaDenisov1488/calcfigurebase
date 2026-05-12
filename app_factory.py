#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Flask application factory."""
import os
from flask import Flask, session
from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix

from config import get_config
from extensions import db, migrate, limiter, csrf, init_cors
from utils.logging_config import setup_logging
from utils.formatters import format_season, format_month_filter
from utils.security_startup import validate_security_at_startup
from utils.access_control import SESSION_SITE_READER_KEY

def create_app():
    load_dotenv()
    app = Flask(__name__)
    # За nginx с TLS: корректные request.is_secure, url_for(..., _external=True), cookies
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)
    config = get_config()
    app.config.update(config)

    validate_security_at_startup(app)

    setup_logging(config['LOG_LEVEL'], config['LOG_FILE'])

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    db.init_app(app)
    # Import models so metadata is populated for migrations.
    import models  # noqa: F401
    migrate.init_app(app, db)
    init_cors(app)
    csrf.init_app(app)
    limiter.init_app(app)

    app.template_global()(format_season)
    app.template_filter('format_month')(format_month_filter)

    from routes.public import public_bp
    from routes.admin import admin_bp
    from routes.api import api_bp
    from routes.analytics import analytics_bp
    from routes.errors import register_error_handlers

    csrf.exempt(api_bp)

    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(analytics_bp)
    register_error_handlers(app)

    @app.before_request
    def _reader_gate_public_analytics_blueprints():
        from flask import request, redirect, url_for, flash
        from utils.access_control import should_redirect_public_html_request

        if request.blueprint not in ('public', 'analytics'):
            return None
        if not should_redirect_public_html_request(request.endpoint):
            return None
        flash(
            'Чтобы открыть страницы с данными турниров и спортсменов, войдите через «Доступ судьи» '
            'или как администратор.',
            'warning',
        )
        # Не использовать request.full_path: для «/» иногда получается «/?», в URL выглядит как next=/? и ломает редирект
        if request.query_string:
            next_arg = (request.path or '/') + '?' + request.query_string.decode('utf-8', errors='replace')
        else:
            next_arg = request.path or '/'
        return redirect(url_for('public.site_access', next=next_arg))

    @app.after_request
    def _no_store_sensitive_html(response):
        from flask import request
        from utils.access_control import public_html_gate_enabled

        if public_html_gate_enabled() and request.blueprint in ('public', 'analytics'):
            response.headers['Cache-Control'] = 'private, no-store'
        return response

    @app.context_processor
    def inject_reader_nav():
        return {
            'site_reader_gate_enabled': bool(app.config.get('SITE_READ_PASSWORD')),
            'site_reader_ok': session.get(SESSION_SITE_READER_KEY),
        }

    # Убираем 404 в логах от запросов браузера к /favicon.ico
    @app.route('/favicon.ico')
    def favicon():
        return '', 204

    return app
