#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для генерации хеша пароля администратора
"""

from werkzeug.security import generate_password_hash
import sys

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Использование: python generate_password_hash.py <пароль>")
        print("\nПример:")
        print("  python generate_password_hash.py mypassword123")
        sys.exit(1)
    
    password = sys.argv[1]
    password_hash = generate_password_hash(password)
    
    print("\n" + "="*60)
    print("ХЕШ ПАРОЛЯ ДЛЯ .env ФАЙЛА")
    print("="*60)
    print(f"\nADMIN_PASSWORD_HASH={password_hash}")
    print("\n" + "="*60)
    print("\nСкопируйте эту строку в ваш .env файл")
    print("="*60 + "\n")

