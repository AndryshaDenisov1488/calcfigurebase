#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Error handlers."""
import logging
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_wtf.csrf import CSRFError
from werkzeug.exceptions import BadRequest
from extensions import db

logger = logging.getLogger(__name__)


def _wants_json_error():
    if request.path.startswith('/api'):
        return True
    best = request.accept_mimetypes.best_match(['application/json', 'text/html'])
    return best == 'application/json'


def register_error_handlers(app):
    @app.errorhandler(403)
    def forbidden_error(error):
        if request.path.startswith('/api'):
            return jsonify({
                'error': 'forbidden',
                'message': (
                    'Требуется доступ: войдите как администратор, откройте доступ судьи '
                    '(SITE_READ_PASSWORD) или передайте заголовок Authorization: Bearer … / X-API-Key.'
                ),
            }), 403
        logger.warning(f"403 error: {request.url} from {request.remote_addr}")
        flash('Доступ запрещён.', 'error')
        return redirect(url_for('public.index'))

    @app.errorhandler(404)
    def not_found_error(error):
        logger.warning(f"404 error: {request.url} from {request.remote_addr}")
        return render_template('404.html'), 404

    @app.errorhandler(CSRFError)
    def csrf_failed(error):
        logger.warning(
            "CSRF validation failed: %s from %s (%s)",
            request.url,
            request.remote_addr,
            error.description,
        )
        if _wants_json_error():
            return jsonify({
                'error': 'csrf_failed',
                'message': (
                    'Сессия устарела или отсутствует токен безопасности. '
                    'Обновите страницу и повторите действие.'
                ),
            }), 400
        return render_template(
            'error_stub.html',
            error_code=400,
            page_title='Требуется обновить страницу',
            heading='Не удалось подтвердить безопасность формы',
            message=(
                'Сессия могла устареть, страница открыта слишком долго или cookies недоступны. '
                'Обновите страницу и отправьте форму ещё раз.'
            ),
            hint=None,
        ), 400

    @app.errorhandler(400)
    def bad_request_error(error):
        if isinstance(error, BadRequest) and not isinstance(error, CSRFError):
            logger.warning(
                "400 Bad Request: %s from %s (%s)",
                request.url,
                request.remote_addr,
                getattr(error, 'description', error),
            )
        if _wants_json_error():
            return jsonify({
                'error': 'bad_request',
                'message': 'Запрос отклонён. Проверьте данные и повторите попытку.',
            }), 400
        return render_template(
            'error_stub.html',
            error_code=400,
            page_title='Ошибка запроса',
            heading='Запрос не может быть обработан',
            message=(
                'Данные запроса не прошли проверку или устарели. '
                'Попробуйте вернуться назад, обновить страницу или начать действие сначала.'
            ),
            hint=None,
        ), 400

    @app.errorhandler(405)
    def method_not_allowed_error(error):
        logger.warning(
            "405 Method Not Allowed: %s %s from %s",
            request.method,
            request.url,
            request.remote_addr,
        )
        if _wants_json_error():
            return jsonify({
                'error': 'method_not_allowed',
                'message': 'Этот метод не поддерживается для данного адреса.',
            }), 405
        return render_template(
            'error_stub.html',
            error_code=405,
            page_title='Метод не поддерживается',
            heading='Такое действие для этой страницы недоступно',
            message='Возможно, ссылка устарела или вы открыли адрес не так, как задумано.',
            hint=None,
        ), 405

    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"500 error: {error} from {request.remote_addr}")
        db.session.rollback()
        return render_template('500.html'), 500

    @app.errorhandler(413)
    def too_large(error):
        logger.warning(f"File too large from {request.remote_addr}")
        flash('Файл слишком большой. Максимальный размер: 16MB', 'error')
        return redirect(url_for('admin.upload_file'))
