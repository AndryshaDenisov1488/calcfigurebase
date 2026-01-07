#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для создания миграции БД после изменений в моделях
"""

from app import app, db
from flask_migrate import Migrate, init, migrate as create_migration, upgrade
import os

def setup_migrations():
    """Настраивает систему миграций"""
    print(f"\n{'='*80}")
    print(f"🔄 СОЗДАНИЕ МИГРАЦИИ БАЗЫ ДАННЫХ")
    print(f"{'='*80}\n")
    
    with app.app_context():
        # Проверяем, есть ли папка migrations
        if not os.path.exists('migrations'):
            print("📁 Инициализация системы миграций...")
            init()
            print("✅ Система миграций инициализирована!")
        else:
            print("✅ Система миграций уже инициализирована")
        
        # Создаем миграцию
        print("\n📝 Создание миграции для изменений в models.py...")
        print("   Изменения:")
        print("   - Event.external_id: unique=True → unique=False")
        print("   - Club.external_id: unique=True → unique=False")
        
        try:
            create_migration(message='remove_unique_constraint_from_external_ids')
            print("✅ Миграция создана!")
            
            # Применяем миграцию
            print("\n⏳ Применение миграции к базе данных...")
            upgrade()
            print("✅ Миграция применена!")
            
        except Exception as e:
            print(f"❌ Ошибка при создании миграции: {e}")
            print("\nВозможно, миграция уже существует или нет изменений в моделях.")

if __name__ == '__main__':
    setup_migrations()

