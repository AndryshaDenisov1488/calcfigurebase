#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Утилиты для работы с паролями
"""

from werkzeug.security import generate_password_hash, check_password_hash

def hash_password(password):
    """Хеширует пароль"""
    return generate_password_hash(password)

def verify_password(password_hash, password):
    """Проверяет пароль против хеша"""
    return check_password_hash(password_hash, password)

