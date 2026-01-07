#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для миграции данных из SQLite в PostgreSQL

Использование:
1. Установите PostgreSQL и создайте базу данных
2. Обновите DATABASE_URL в .env на PostgreSQL
3. Запустите: python scripts/migrate_sqlite_to_postgresql.py

ВАЖНО: Сделайте бэкап SQLite БД перед миграцией!
"""

import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

def migrate_database():
    """Мигрирует данные из SQLite в PostgreSQL"""
    
    # Путь к SQLite базе
    sqlite_path = os.environ.get('SQLITE_DB_PATH', 'instance/figure_skating.db')
    if not os.path.exists(sqlite_path):
        print(f"❌ SQLite база данных не найдена: {sqlite_path}")
        print("Укажите путь к SQLite БД через переменную SQLITE_DB_PATH")
        return False
    
    # URL PostgreSQL базы
    postgresql_url = os.environ.get('DATABASE_URL')
    if not postgresql_url or not postgresql_url.startswith('postgresql'):
        print("❌ DATABASE_URL должен указывать на PostgreSQL!")
        print("Пример: postgresql://user:password@localhost/dbname")
        return False
    
    print("=" * 60)
    print("МИГРАЦИЯ БАЗЫ ДАННЫХ SQLite → PostgreSQL")
    print("=" * 60)
    print(f"Источник (SQLite): {sqlite_path}")
    print(f"Назначение (PostgreSQL): {postgresql_url.split('@')[1] if '@' in postgresql_url else postgresql_url}")
    print()
    
    # Подтверждение
    confirm = input("⚠️  ВНИМАНИЕ: Это перезапишет данные в PostgreSQL БД! Продолжить? (yes/no): ")
    if confirm.lower() != 'yes':
        print("Миграция отменена.")
        return False
    
    try:
        # Подключаемся к SQLite
        sqlite_url = f'sqlite:///{sqlite_path}'
        sqlite_engine = create_engine(sqlite_url, echo=False)
        sqlite_session = sessionmaker(bind=sqlite_engine)()
        
        # Подключаемся к PostgreSQL
        postgresql_engine = create_engine(postgresql_url, echo=False)
        postgresql_session = sessionmaker(bind=postgresql_engine)()
        
        print("\n📊 Начинаем миграцию...")
        
        # Список таблиц для миграции (в правильном порядке для foreign keys)
        tables = [
            'event',
            'club',
            'category',
            'segment',
            'athlete',
            'participant',
            'performance'
        ]
        
        total_records = 0
        
        for table_name in tables:
            print(f"\n📦 Мигрируем таблицу: {table_name}")
            
            # Получаем данные из SQLite
            result = sqlite_session.execute(text(f"SELECT * FROM {table_name}"))
            rows = result.fetchall()
            columns = result.keys()
            
            if not rows:
                print(f"   ⚠️  Таблица {table_name} пуста, пропускаем")
                continue
            
            print(f"   📝 Найдено записей: {len(rows)}")
            
            # Очищаем таблицу в PostgreSQL (если нужно)
            if table_name == 'event':  # Только для первой таблицы
                postgresql_session.execute(text(f"TRUNCATE TABLE {table_name} CASCADE"))
                postgresql_session.commit()
            else:
                # Для остальных таблиц используем DELETE (TRUNCATE может не работать из-за foreign keys)
                postgresql_session.execute(text(f"DELETE FROM {table_name}"))
                postgresql_session.commit()
            
            # Вставляем данные в PostgreSQL
            inserted = 0
            for row in rows:
                try:
                    # Создаем словарь из строки
                    row_dict = dict(zip(columns, row))
                    
                    # Формируем INSERT запрос
                    columns_str = ', '.join(columns)
                    placeholders = ', '.join([f':{col}' for col in columns])
                    insert_query = text(f"""
                        INSERT INTO {table_name} ({columns_str})
                        VALUES ({placeholders})
                        ON CONFLICT DO NOTHING
                    """)
                    
                    postgresql_session.execute(insert_query, row_dict)
                    inserted += 1
                    
                    if inserted % 100 == 0:
                        print(f"   ⏳ Обработано: {inserted}/{len(rows)}")
                        postgresql_session.commit()
                        
                except Exception as e:
                    print(f"   ❌ Ошибка при вставке записи: {str(e)}")
                    postgresql_session.rollback()
                    continue
            
            # Финальный коммит для таблицы
            postgresql_session.commit()
            print(f"   ✅ Успешно мигрировано: {inserted}/{len(rows)} записей")
            total_records += inserted
        
        # Обновляем sequences для PostgreSQL (важно для auto-increment)
        print("\n🔄 Обновляем sequences...")
        for table_name in tables:
            try:
                # Получаем максимальный ID
                max_id_result = postgresql_session.execute(
                    text(f"SELECT MAX(id) FROM {table_name}")
                )
                max_id = max_id_result.scalar()
                
                if max_id:
                    # Обновляем sequence
                    postgresql_session.execute(
                        text(f"SELECT setval('{table_name}_id_seq', {max_id}, true)")
                    )
                    postgresql_session.commit()
                    print(f"   ✅ Sequence для {table_name} обновлен до {max_id}")
            except Exception as e:
                print(f"   ⚠️  Не удалось обновить sequence для {table_name}: {str(e)}")
        
        print("\n" + "=" * 60)
        print(f"✅ МИГРАЦИЯ ЗАВЕРШЕНА УСПЕШНО!")
        print(f"📊 Всего мигрировано записей: {total_records}")
        print("=" * 60)
        
        sqlite_session.close()
        postgresql_session.close()
        
        return True
        
    except Exception as e:
        print(f"\n❌ ОШИБКА МИГРАЦИИ: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = migrate_database()
    sys.exit(0 if success else 1)

