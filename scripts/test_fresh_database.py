#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест создания БД с нуля - проверяем что структура правильная
"""

import os
import shutil
from datetime import datetime
from app import app, db
from models import Event, Club, Category, Athlete

def test_fresh_database_creation():
    """Тестирует создание БД с нуля"""
    print(f"\n{'='*80}")
    print(f"🧪 ТЕСТ: Создание БД с нуля")
    print(f"{'='*80}\n")
    
    # Временная БД для теста
    test_db_path = 'instance/test_figure_skating.db'
    
    # Удаляем если существует
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
        print(f"🗑️  Удалена старая тестовая БД")
    
    # Настраиваем приложение на тестовую БД
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{test_db_path}'
    
    with app.app_context():
        # Создаем БД с нуля
        print(f"🔨 Создание БД с нуля...")
        db.create_all()
        print(f"✅ БД создана!")
        
        # Проверяем структуру через SQLite
        import sqlite3
        conn = sqlite3.connect(test_db_path)
        cursor = conn.cursor()
        
        # Проверяем индексы Event
        print(f"\n📊 ИНДЕКСЫ ТАБЛИЦЫ 'event':")
        cursor.execute("""
            SELECT name, sql 
            FROM sqlite_master 
            WHERE type='index' AND tbl_name='event'
        """)
        event_indexes = cursor.fetchall()
        
        has_unique_event = False
        for idx_name, idx_sql in event_indexes:
            if idx_sql:  # Некоторые индексы могут быть None
                is_unique = 'UNIQUE' in idx_sql.upper()
                if is_unique and 'external_id' in idx_sql.lower():
                    has_unique_event = True
                    print(f"   ❌ {idx_name}: {idx_sql}")
                    print(f"      ^ ПРОБЛЕМА: external_id имеет UNIQUE constraint!")
                else:
                    status = "⚠️ UNIQUE" if is_unique else "✅"
                    print(f"   {status} {idx_name}: {idx_sql}")
        
        # Проверяем индексы Club
        print(f"\n📊 ИНДЕКСЫ ТАБЛИЦЫ 'club':")
        cursor.execute("""
            SELECT name, sql 
            FROM sqlite_master 
            WHERE type='index' AND tbl_name='club'
        """)
        club_indexes = cursor.fetchall()
        
        has_unique_club = False
        for idx_name, idx_sql in club_indexes:
            if idx_sql:
                is_unique = 'UNIQUE' in idx_sql.upper()
                if is_unique and 'external_id' in idx_sql.lower():
                    has_unique_club = True
                    print(f"   ❌ {idx_name}: {idx_sql}")
                    print(f"      ^ ПРОБЛЕМА: external_id имеет UNIQUE constraint!")
                else:
                    status = "⚠️ UNIQUE" if is_unique else "✅"
                    print(f"   {status} {idx_name}: {idx_sql}")
        
        conn.close()
        
        # ТЕСТ: Попытка создать два объекта с одинаковым external_id
        print(f"\n🧪 ТЕСТ: Создание двух клубов с одинаковым external_id...")
        
        try:
            club1 = Club(
                external_id='test_001',
                name='Тестовый клуб 1',
                short_name='ТК1',
                country='RUS',
                city='Москва'
            )
            db.session.add(club1)
            db.session.commit()
            print(f"   ✅ Клуб 1 создан (ID: {club1.id})")
            
            club2 = Club(
                external_id='test_001',  # Тот же external_id!
                name='Тестовый клуб 2',
                short_name='ТК2',
                country='RUS',
                city='Санкт-Петербург'
            )
            db.session.add(club2)
            db.session.commit()
            print(f"   ✅ Клуб 2 создан (ID: {club2.id})")
            
            print(f"\n   🎉 ТЕСТ ПРОЙДЕН! Два клуба с одинаковым external_id созданы!")
            test_passed = True
            
        except Exception as e:
            print(f"   ❌ ОШИБКА: {e}")
            print(f"   ❌ ТЕСТ НЕ ПРОЙДЕН! external_id все еще unique")
            test_passed = False
            db.session.rollback()
        
        # Очистка
        print(f"\n🗑️  Удаление тестовой БД...")
        db.session.remove()
    
    # Удаляем тестовую БД
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
        print(f"✅ Тестовая БД удалена")
    
    # Восстанавливаем настройки
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///instance/figure_skating.db'
    
    # ИТОГИ
    print(f"\n{'='*80}")
    print(f"📊 ИТОГИ")
    print(f"{'='*80}\n")
    
    if not has_unique_event and not has_unique_club and test_passed:
        print(f"✅ ВСЕ ОТЛИЧНО!")
        print(f"   - Event.external_id: НЕ unique ✅")
        print(f"   - Club.external_id: НЕ unique ✅")
        print(f"   - Тест создания дубликатов: ПРОЙДЕН ✅")
        print(f"\n🎉 БД будет создаваться ПРАВИЛЬНО при db.create_all()!")
        return True
    else:
        print(f"⚠️ ЕСТЬ ПРОБЛЕМЫ:")
        if has_unique_event:
            print(f"   ❌ Event.external_id все еще имеет UNIQUE constraint")
        if has_unique_club:
            print(f"   ❌ Club.external_id все еще имеет UNIQUE constraint")
        if not test_passed:
            print(f"   ❌ Тест создания дубликатов НЕ ПРОЙДЕН")
        
        print(f"\n💡 РЕШЕНИЕ: Проверьте models.py - там не должно быть unique=True")
        return False

def show_current_models():
    """Показывает текущую структуру models.py"""
    print(f"\n{'='*80}")
    print(f"📋 ТЕКУЩАЯ СТРУКТУРА MODELS.PY")
    print(f"{'='*80}\n")
    
    with open('models.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Event
    print(f"🔍 Event.external_id:")
    for i, line in enumerate(lines, 1):
        if 'class Event' in line:
            for j in range(i-1, min(i+10, len(lines))):
                if 'external_id' in lines[j]:
                    print(f"   Строка {j+1}: {lines[j].rstrip()}")
                    if 'unique=True' in lines[j]:
                        print(f"   ❌ ПРОБЛЕМА: есть unique=True!")
                    else:
                        print(f"   ✅ OK: нет unique=True")
                    break
            break
    
    # Club
    print(f"\n🔍 Club.external_id:")
    for i, line in enumerate(lines, 1):
        if 'class Club' in line:
            for j in range(i-1, min(i+10, len(lines))):
                if 'external_id' in lines[j]:
                    print(f"   Строка {j+1}: {lines[j].rstrip()}")
                    if 'unique=True' in lines[j]:
                        print(f"   ❌ ПРОБЛЕМА: есть unique=True!")
                    else:
                        print(f"   ✅ OK: нет unique=True")
                    break
            break

if __name__ == '__main__':
    print(f"\n{'#'*80}")
    print(f"# ПРОВЕРКА СОЗДАНИЯ БД С НУЛЯ")
    print(f"{'#'*80}")
    
    # Сначала показываем models.py
    show_current_models()
    
    # Потом тестируем создание БД
    success = test_fresh_database_creation()
    
    if success:
        print(f"\n{'='*80}")
        print(f"🎉 ОТЛИЧНО! При запуске app.py БД будет создаваться правильно!")
        print(f"{'='*80}")
    else:
        print(f"\n{'='*80}")
        print(f"⚠️  Нужны доработки в models.py")
        print(f"{'='*80}")



