#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для назначения клуба "ГБУ ДО Московская академия фигурного катания на коньках" 
всем спортсменам без указанного клуба
"""

import os
import sys
from datetime import datetime

# Добавляем текущую директорию в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Athlete, Club, Participant

def assign_default_club():
    """Назначает клуб 'ГБУ ДО Московская академия фигурного катания на коньках' спортсменам без клуба"""
    with app.app_context():
        print("🔍 Поиск клуба 'ГБУ ДО Московская академия фигурного катания на коньках'...")
        
        # Ищем нужный клуб
        target_club = Club.query.filter_by(
            name="ГБУ ДО Московская академия фигурного катания на коньках"
        ).first()
        
        if not target_club:
            print("❌ Клуб 'ГБУ ДО Московская академия фигурного катания на коньках' не найден в базе!")
            print("📋 Доступные клубы:")
            clubs = Club.query.all()
            for club in clubs[:10]:  # Показываем первые 10
                print(f"   - {club.name}")
            if len(clubs) > 10:
                print(f"   ... и еще {len(clubs) - 10} клубов")
            return 1
        
        print(f"✅ Найден клуб: ID {target_club.id}")
        print(f"   Название: {target_club.name}")
        print(f"   Краткое название: {target_club.short_name}")
        print(f"   Город: {target_club.city}")
        print(f"   Страна: {target_club.country}")
        
        # Находим спортсменов без клуба
        print("\n🔍 Поиск спортсменов без указанного клуба...")
        
        athletes_without_club = Athlete.query.filter(
            Athlete.club_id.is_(None)
        ).all()
        
        if not athletes_without_club:
            print("✅ У всех спортсменов уже указаны клубы!")
            return 0
        
        print(f"📋 Найдено {len(athletes_without_club)} спортсменов без клуба")
        
        # Показываем список спортсменов, которые будут обновлены
        print("\n📝 Список спортсменов для обновления:")
        print("-" * 80)
        for i, athlete in enumerate(athletes_without_club, 1):
            birth_date_str = athlete.birth_date.strftime('%d.%m.%Y') if athlete.birth_date else 'Не указана'
            gender_str = 'Женский' if athlete.gender == 'F' else 'Мужской' if athlete.gender == 'M' else 'Не указан'
            print(f"{i:2d}. {athlete.full_name or f'{athlete.last_name} {athlete.first_name}'}")
            print(f"     ID: {athlete.id}, Дата рождения: {birth_date_str}, Пол: {gender_str}")
        
        # Подтверждение
        print(f"\n⚠️  ВНИМАНИЕ: Будет назначен клуб '{target_club.name}' для {len(athletes_without_club)} спортсменов.")
        print("Продолжить? (y/N): ", end="")
        
        # В автоматическом режиме подтверждаем
        confirm = "y"  # Для автоматического выполнения
        
        if confirm.lower() != 'y':
            print("❌ Операция отменена пользователем.")
            return 0
        
        # Обновляем спортсменов
        print(f"\n🔄 Назначение клуба...")
        
        updated_count = 0
        for i, athlete in enumerate(athletes_without_club, 1):
            athlete.club_id = target_club.id
            updated_count += 1
            
            if i % 10 == 0 or i == len(athletes_without_club):  # Показываем прогресс
                print(f"   Обработано: {i}/{len(athletes_without_club)}")
        
        try:
            print(f"\n💾 Сохранение изменений...")
            db.session.commit()
            print(f"✅ Успешно назначен клуб для {updated_count} спортсменов!")
            
            # Проверяем результат
            remaining = Athlete.query.filter(Athlete.club_id.is_(None)).count()
            
            if remaining == 0:
                print("🎉 Теперь у всех спортсменов указаны клубы!")
            else:
                print(f"⚠️  Осталось {remaining} спортсменов без клуба")
            
            # Показываем обновленную статистику
            print(f"\n📊 Обновленная статистика:")
            total_athletes = Athlete.query.count()
            athletes_with_club = Athlete.query.filter(Athlete.club_id.isnot(None)).count()
            print(f"   Всего спортсменов: {total_athletes}")
            print(f"   С клубом: {athletes_with_club}")
            print(f"   Без клуба: {remaining}")
            
            # Показываем статистику по целевому клубу
            club_athletes_count = Athlete.query.filter_by(club_id=target_club.id).count()
            print(f"\n🏫 Клуб '{target_club.name}':")
            print(f"   Всего спортсменов: {club_athletes_count}")
                
        except Exception as e:
            db.session.rollback()
            print(f"❌ Ошибка при сохранении: {e}")
            return 1
    
    return 0

def main():
    """Основная функция"""
    print("🏫 Назначение клуба спортсменам без указанной школы")
    print("="*70)
    
    try:
        return assign_default_club()
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return 1

if __name__ == "__main__":
    exit(main())
