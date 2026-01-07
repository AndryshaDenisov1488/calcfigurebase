#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для исправления существующей БД - убираем unique constraint с external_id
"""

import sqlite3
import os
import shutil
from datetime import datetime

def fix_database():
    """Исправляет БД - убирает unique constraint с external_id"""
    print(f"\n{'='*80}")
    print(f"🔧 ИСПРАВЛЕНИЕ СУЩЕСТВУЮЩЕЙ БАЗЫ ДАННЫХ")
    print(f"{'='*80}\n")
    
    db_path = 'instance/figure_skating.db'
    
    if not os.path.exists(db_path):
        print(f"❌ База данных не найдена: {db_path}")
        return False
    
    # Создаем бэкап
    print(f"💾 Создание бэкапа...")
    backup_dir = 'backups'
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = os.path.join(backup_dir, f'before_fix_{timestamp}.db')
    shutil.copy2(db_path, backup_path)
    print(f"✅ Бэкап создан: {backup_path}")
    
    # Подключаемся к БД
    print(f"\n🔄 Исправление БД...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Проверяем текущую структуру
        print(f"\n📊 Текущая структура таблиц:")
        
        # Event
        cursor.execute("PRAGMA table_info(event)")
        event_columns = cursor.fetchall()
        print(f"\nТаблица 'event':")
        for col in event_columns:
            print(f"   {col}")
        
        # Club
        cursor.execute("PRAGMA table_info(club)")
        club_columns = cursor.fetchall()
        print(f"\nТаблица 'club':")
        for col in club_columns:
            print(f"   {col}")
        
        # Проверяем индексы
        print(f"\n📊 Индексы:")
        cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND (tbl_name='event' OR tbl_name='club')")
        indexes = cursor.fetchall()
        for idx_name, idx_sql in indexes:
            print(f"   {idx_name}: {idx_sql}")
        
        # SQLite не может изменить колонку напрямую
        # Нужно пересоздать таблицы
        print(f"\n⚠️  В SQLite нельзя просто убрать unique constraint")
        print(f"   Нужно пересоздать таблицы...")
        
        # Для Event
        print(f"\n🔄 Пересоздание таблицы 'event'...")
        
        # Сохраняем данные
        cursor.execute("SELECT * FROM event")
        event_data = cursor.fetchall()
        cursor.execute("PRAGMA table_info(event)")
        event_columns = [col[1] for col in cursor.fetchall()]
        
        print(f"   Сохранено {len(event_data)} записей")
        
        # Удаляем старую таблицу
        cursor.execute("DROP TABLE IF EXISTS event_new")
        
        # Создаем новую таблицу БЕЗ unique constraint
        cursor.execute("""
            CREATE TABLE event_new (
                id INTEGER PRIMARY KEY,
                external_id VARCHAR(50),
                name VARCHAR(200) NOT NULL,
                long_name VARCHAR(500),
                place VARCHAR(200),
                begin_date DATE,
                end_date DATE,
                venue VARCHAR(200),
                language VARCHAR(10),
                event_type VARCHAR(50),
                competition_type VARCHAR(50),
                status VARCHAR(20),
                calculation_time DATETIME,
                created_at DATETIME
            )
        """)
        
        # Копируем данные
        if event_data:
            placeholders = ','.join(['?' for _ in event_columns])
            cursor.executemany(
                f"INSERT INTO event_new ({','.join(event_columns)}) VALUES ({placeholders})",
                event_data
            )
        
        # Удаляем старую и переименовываем новую
        cursor.execute("DROP TABLE event")
        cursor.execute("ALTER TABLE event_new RENAME TO event")
        
        # Создаем индексы
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_event_external_id ON event (external_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_event_name ON event (name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_event_begin_date ON event (begin_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_event_end_date ON event (end_date)")
        
        print(f"   ✅ Таблица 'event' пересоздана")
        
        # Для Club
        print(f"\n🔄 Пересоздание таблицы 'club'...")
        
        # Сохраняем данные
        cursor.execute("SELECT * FROM club")
        club_data = cursor.fetchall()
        cursor.execute("PRAGMA table_info(club)")
        club_columns = [col[1] for col in cursor.fetchall()]
        
        print(f"   Сохранено {len(club_data)} записей")
        
        # Удаляем старую таблицу
        cursor.execute("DROP TABLE IF EXISTS club_new")
        
        # Создаем новую таблицу БЕЗ unique constraint
        cursor.execute("""
            CREATE TABLE club_new (
                id INTEGER PRIMARY KEY,
                external_id VARCHAR(50),
                name VARCHAR(200) NOT NULL,
                short_name VARCHAR(50),
                country VARCHAR(3),
                city VARCHAR(100)
            )
        """)
        
        # Копируем данные
        if club_data:
            placeholders = ','.join(['?' for _ in club_columns])
            cursor.executemany(
                f"INSERT INTO club_new ({','.join(club_columns)}) VALUES ({placeholders})",
                club_data
            )
        
        # Удаляем старую и переименовываем новую
        cursor.execute("DROP TABLE club")
        cursor.execute("ALTER TABLE club_new RENAME TO club")
        
        # Создаем индексы
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_club_external_id ON club (external_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_club_name ON club (name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_club_country ON club (country)")
        
        print(f"   ✅ Таблица 'club' пересоздана")
        
        # Сохраняем изменения
        conn.commit()
        
        print(f"\n✅ База данных успешно исправлена!")
        print(f"   - Таблица 'event': external_id больше не unique")
        print(f"   - Таблица 'club': external_id больше не unique")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        conn.rollback()
        
        # Восстанавливаем из бэкапа
        print(f"\n🔄 Восстановление из бэкапа...")
        conn.close()
        shutil.copy2(backup_path, db_path)
        print(f"✅ База данных восстановлена из бэкапа")
        
        return False
        
    finally:
        conn.close()

if __name__ == '__main__':
    success = fix_database()
    
    if success:
        print(f"\n🎉 ГОТОВО! Теперь можно запустить тесты:")
        print(f"   python test_all_fixes.py")
    else:
        print(f"\n⚠️  Исправление не удалось")



