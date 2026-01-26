#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для создания базы данных с нуля
Использование: python scripts/create_database.py
"""

import os
import sys

# Добавляем текущую директорию в путь
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app_factory import create_app
from extensions import db

def create_database():
    """Создает все таблицы в базе данных"""
    app = create_app()
    
    with app.app_context():
        print("=" * 80)
        print("СОЗДАНИЕ БАЗЫ ДАННЫХ")
        print("=" * 80)
        print()
        
        # Проверяем, существует ли БД
        db_path = app.config.get('SQLALCHEMY_DATABASE_URI', '').replace('sqlite:///', '')
        if db_path and os.path.exists(db_path):
            print(f"⚠️  База данных уже существует: {db_path}")
            response = input("Удалить и создать заново? (yes/no): ")
            if response.lower() != 'yes':
                print("Отменено.")
                return
        
        print("Создание всех таблиц...")
        db.create_all()
        print("✅ База данных создана успешно!")
        print()
        
        # Проверяем созданные таблицы
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        print(f"Создано таблиц: {len(tables)}")
        for table in sorted(tables):
            print(f"  - {table}")
        print()
        print("=" * 80)
        print("Готово!")
        print("=" * 80)

if __name__ == '__main__':
    create_database()
