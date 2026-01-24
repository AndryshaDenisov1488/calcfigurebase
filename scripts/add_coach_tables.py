#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для добавления таблиц тренеров в базу данных
Использование: python scripts/add_coach_tables.py
"""

import os
import sys
import sqlite3

# Добавляем текущую директорию в путь
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app import app, db
from models import Coach, CoachAssignment

def add_coach_tables():
    """Добавляет таблицы coach и coach_assignment в базу данных"""
    with app.app_context():
        print("=" * 80)
        print("ДОБАВЛЕНИЕ ТАБЛИЦ ТРЕНЕРОВ В БАЗУ ДАННЫХ")
        print("=" * 80)
        print()
        
        # Проверяем, существуют ли таблицы
        inspector = db.inspect(db.engine)
        existing_tables = inspector.get_table_names()
        
        if 'coach' in existing_tables:
            print("Таблица 'coach' уже существует")
        else:
            print("Создание таблицы 'coach'...")
            db.create_all()
            print("Таблица 'coach' создана")
        
        if 'coach_assignment' in existing_tables:
            print("Таблица 'coach_assignment' уже существует")
        else:
            print("Создание таблицы 'coach_assignment'...")
            db.create_all()
            print("Таблица 'coach_assignment' создана")
        
        print()
        print("=" * 80)
        print("Готово! Таблицы тренеров добавлены в базу данных.")
        print("=" * 80)

if __name__ == '__main__':
    add_coach_tables()
