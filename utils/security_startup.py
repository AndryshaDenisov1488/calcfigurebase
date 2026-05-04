#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проверки конфигурации безопасности при старте приложения."""
import os
import logging

logger = logging.getLogger(__name__)


def is_security_relaxed():
    return (
        os.environ.get('FLASK_DEBUG', '').lower() in ('1', 'true', 'yes')
        or os.environ.get('ALLOW_INSECURE_DEFAULTS', '').lower() in ('1', 'true', 'yes')
    )


def validate_security_at_startup(app):
    """
    В «строгом» режиме требуем SECRET_KEY и способ закрыть публичный JSON API.
    Локально: FLASK_DEBUG=1 или ALLOW_INSECURE_DEFAULTS=1.
    Явное отключение проверки API: DISABLE_PUBLIC_API_AUTH=1 (только dev/stage).
    """
    relaxed = is_security_relaxed()
    if relaxed:
        logger.warning(
            'Режим ослабленных проверок (FLASK_DEBUG или ALLOW_INSECURE_DEFAULTS). '
            'Не используйте это на публичном интернете.'
        )
        return

    sk = app.config.get('SECRET_KEY')
    if not sk:
        raise RuntimeError(
            'Задайте переменную окружения SECRET_KEY (одинаковую для всех воркеров Gunicorn).'
        )

    if os.environ.get('DISABLE_PUBLIC_API_AUTH', '').lower() in ('1', 'true', 'yes'):
        logger.warning(
            'DISABLE_PUBLIC_API_AUTH включён: эндпойнты /api/* доступны анонимно. '
            'Только для разработки или изолированной сети.'
        )
        return

    pwd = (app.config.get('SITE_READ_PASSWORD') or '').strip()
    keys = app.config.get('API_KEYS') or []
    if not pwd and not keys:
        raise RuntimeError(
            'Задайте SITE_READ_PASSWORD (доступ судей в браузере) и/или API_KEYS '
            '(ключи через запятую для интеграций). Либо временно ALLOW_INSECURE_DEFAULTS=1 '
            'или DISABLE_PUBLIC_API_AUTH=1 только для разработки.'
        )

    if keys and not pwd:
        logger.warning(
            'SITE_READ_PASSWORD не задан: страницы с запросами к /api/* из браузера '
            'не получат данные без входа администратора.'
        )
    elif pwd and not keys:
        logger.info(
            'API_KEYS не заданы: программный доступ к API только с сессией судьи или администратора.'
        )
