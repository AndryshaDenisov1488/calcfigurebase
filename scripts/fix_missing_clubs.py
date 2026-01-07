#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для исправления спортсменов без указанных школ/клубов
"""

import os
import sys
from datetime import datetime

# Добавляем текущую директорию в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Athlete, Club, Participant

def create_default_club():
    """Создает клуб по умолчанию для спортсменов без клуба"""
    with app.app_context():
        # Ищем или создаем клуб по умолчанию
        default_club = Club.query.filter_by(name="Не указан").first()
        
        if not default_club:
            print("🏫 Создание клуба по умолчанию...")
            default_club = Club(
                name="Не указан",
                short_name="Не указан",
                country="RUS",
                city="Не указан"
            )
            db.session.add(default_club)
            db.session.flush()  # Получаем ID
            print(f"✅ Создан клуб по умолчанию: ID {default_club.id}")
        else:
            print(f"✅ Клуб по умолчанию уже существует: ID {default_club.id}")
        
        return default_club

def fix_missing_clubs():
    """Исправляет спортсменов без указанных клубов"""
    with app.app_context():
        print("🔍 Поиск спортсменов без указанных клубов...")
        
        # Находим спортсменов без клуба
        athletes_without_club = Athlete.query.filter(
            Athlete.club_id.is_(None)
        ).all()
        
        if not athletes_without_club:
            print("✅ У всех спортсменов указаны клубы!")
            return
        
        print(f"📋 Найдено {len(athletes_without_club)} спортсменов без клуба")
        
        # Создаем или находим клуб по умолчанию
        default_club = create_default_club()
        
        # Обновляем спортсменов
        print(f"🔄 Назначение клуба по умолчанию...")
        
        for i, athlete in enumerate(athletes_without_club, 1):
            athlete.club_id = default_club.id
            if i % 100 == 0:  # Показываем прогресс каждые 100 записей
                print(f"   Обработано: {i}/{len(athletes_without_club)}")
        
        try:
            print(f"💾 Сохранение изменений...")
            db.session.commit()
            print(f"✅ Успешно назначен клуб по умолчанию для {len(athletes_without_club)} спортсменов!")
            
            # Проверяем результат
            remaining = Athlete.query.filter(Athlete.club_id.is_(None)).count()
            
            if remaining == 0:
                print("🎉 Теперь у всех спортсменов указаны клубы!")
            else:
                print(f"⚠️  Осталось {remaining} спортсменов без клуба")
                
        except Exception as e:
            db.session.rollback()
            print(f"❌ Ошибка при сохранении: {e}")
            return 1
    
    return 0

def main():
    """Основная функция"""
    print("🏫 Исправление спортсменов без указанных клубов")
    print("="*60)
    
    try:
        return fix_missing_clubs()
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return 1

if __name__ == "__main__":
    exit(main())
