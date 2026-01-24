#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для добавления колонки coach в таблицу participant
"""

from app_factory import create_app
from extensions import db
import sqlite3
import os

def add_coach_column():
    """Добавляет колонку coach в таблицу participant"""
    app = create_app()
    
    with app.app_context():
        # Получаем путь к базе данных
        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        if db_uri.startswith('sqlite:///'):
            db_path = db_uri.replace('sqlite:///', '')
            # Если относительный путь, ищем в корне проекта или в instance
            if not os.path.isabs(db_path):
                # Проверяем в корне проекта
                project_root = os.path.dirname(os.path.abspath(__file__))
                possible_paths = [
                    os.path.join(project_root, db_path),
                    os.path.join(project_root, 'instance', db_path),
                    db_path
                ]
                for path in possible_paths:
                    if os.path.exists(path):
                        db_path = path
                        break
        else:
            print("ERROR: База данных не найдена")
            print("Проверьте путь к базе данных в конфигурации")
            return
        
        if not os.path.exists(db_path):
            print(f"ERROR: Файл базы данных не найден: {db_path}")
            print("Искали в:")
            if db_uri.startswith('sqlite:///'):
                project_root = os.path.dirname(os.path.abspath(__file__))
                print(f"  - {os.path.join(project_root, db_uri.replace('sqlite:///', ''))}")
                print(f"  - {os.path.join(project_root, 'instance', db_uri.replace('sqlite:///', ''))}")
            return
        
        print(f"База данных: {db_path}")
        
        # Подключаемся к базе напрямую через sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        try:
            # Проверяем, существует ли колонка
            cursor.execute("PRAGMA table_info(participant)")
            columns = [row[1] for row in cursor.fetchall()]
            
            if 'coach' in columns:
                print("OK: Колонка 'coach' уже существует в таблице participant")
            else:
                print("Добавляем колонку 'coach' в таблицу participant...")
                cursor.execute("ALTER TABLE participant ADD COLUMN coach VARCHAR(200)")
                conn.commit()
                print("OK: Колонка 'coach' успешно добавлена!")
                
        except sqlite3.Error as e:
            print(f"ERROR: Ошибка при добавлении колонки: {e}")
            conn.rollback()
        finally:
            conn.close()

if __name__ == '__main__':
    print("\n" + "="*80)
    print("ДОБАВЛЕНИЕ КОЛОНКИ COACH В ТАБЛИЦУ PARTICIPANT")
    print("="*80 + "\n")
    add_coach_column()
    print("\n" + "="*80)
    print("ГОТОВО!")
    print("="*80 + "\n")
