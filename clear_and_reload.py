#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для полной очистки базы данных и перезагрузки данных
"""

from app import app, db
from models import Event, Category, Segment, Club, Athlete, Participant, Performance

def clear_database():
    """Полностью очищает базу данных"""
    with app.app_context():
        print("=== Очистка базы данных ===")
        
        # Удаляем все данные в правильном порядке (с учетом внешних ключей)
        print("Удаление выступлений...")
        Performance.query.delete()
        
        print("Удаление участников...")
        Participant.query.delete()
        
        print("Удаление спортсменов...")
        Athlete.query.delete()
        
        print("Удаление сегментов...")
        Segment.query.delete()
        
        print("Удаление категорий...")
        Category.query.delete()
        
        print("Удаление клубов...")
        Club.query.delete()
        
        print("Удаление событий...")
        Event.query.delete()
        
        # Сохраняем изменения
        db.session.commit()
        
        print("✅ База данных полностью очищена")

def check_database_status():
    """Проверяет статус базы данных"""
    with app.app_context():
        print("\n=== Статус базы данных ===")
        
        events_count = Event.query.count()
        categories_count = Category.query.count()
        athletes_count = Athlete.query.count()
        participants_count = Participant.query.count()
        
        print(f"События: {events_count}")
        print(f"Категории: {categories_count}")
        print(f"Спортсмены: {athletes_count}")
        print(f"Участники: {participants_count}")
        
        # Проверяем на наличие "Другой"
        drugoy_categories = Category.query.filter(Category.normalized_name.like('Другой%')).count()
        print(f"Категории с 'Другой': {drugoy_categories}")
        
        if drugoy_categories > 0:
            print("❌ В базе данных есть категории с 'Другой'")
            categories = Category.query.filter(Category.normalized_name.like('Другой%')).all()
            for cat in categories:
                print(f"   - {cat.name} -> {cat.normalized_name}")
        else:
            print("✅ Категорий с 'Другой' не найдено")

if __name__ == "__main__":
    print("ВНИМАНИЕ: Этот скрипт полностью очистит базу данных!")
    response = input("Продолжить? (y/N): ")
    
    if response.lower() == 'y':
        clear_database()
        check_database_status()
        print("\n✅ Готово! Теперь загрузите XML файлы через новый процесс нормализации.")
    else:
        print("Операция отменена.")
