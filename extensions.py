#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Application extensions (SQLAlchemy, Migrate, Limiter, CSRF).
CORS включается только при явном CORS_ORIGINS (через запятую).
"""
import os
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv

load_dotenv()

db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()

redis_url = os.environ.get('REDIS_URL')
if redis_url:
    limiter = Limiter(
        key_func=get_remote_address,
        storage_uri=redis_url,
        default_limits=["1000 per hour", "100 per minute"],
    )
else:
    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=["1000 per hour", "100 per minute"],
    )


def init_cors(app):
    """Ограниченный CORS только для /api/* и только для указанных origin."""
    from flask_cors import CORS

    origins_raw = os.environ.get('CORS_ORIGINS', '').strip()
    if not origins_raw:
        return
    origins = [o.strip() for o in origins_raw.split(',') if o.strip()]
    if not origins:
        return
    CORS(
        app,
        resources={
            r'/api/*': {
                'origins': origins,
                'supports_credentials': True,
            }
        },
    )
