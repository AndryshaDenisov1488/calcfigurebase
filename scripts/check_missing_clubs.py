#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для проверки спортсменов без указанных школ/клубов
"""

import os
import sys
from datetime import datetime

# Добавляем текущую директорию в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Athlete, Club, Participant

def check_missing_clubs():
    """Проверяет спортсменов без указанных клубов"""
    with app.app_context():
        print("🔍 Проверка спортсменов без указанных школ/клубов...")
        
        # Находим спортсменов без клуба
        athletes_without_club = Athlete.query.filter(
            Athlete.club_id.is_(None)
        ).all()
        
        print(f"\n📊 Статистика:")
        print(f"Всего спортсменов в базе: {Athlete.query.count()}")
        print(f"Спортсменов без клуба: {len(athletes_without_club)}")
        print(f"Спортсменов с клубом: {Athlete.query.filter(Athlete.club_id.isnot(None)).count()}")
        
        if not athletes_without_club:
            print("\n✅ У всех спортсменов указаны клубы!")
            return
        
        print(f"\n📋 Список спортсменов без клуба ({len(athletes_without_club)}):")
        print("-" * 80)
        
        for i, athlete in enumerate(athletes_without_club, 1):
            # Получаем количество участий
            participations_count = Participant.query.filter_by(athlete_id=athlete.id).count()
            
            print(f"{i:3d}. {athlete.full_name}")
            print(f"     ID: {athlete.id}")
            print(f"     Дата рождения: {athlete.birth_date or 'Не указана'}")
            print(f"     Пол: {athlete.gender or 'Не указан'}")
            print(f"     Участий: {participations_count}")
            print(f"     Клуб ID: {athlete.club_id}")
            print()
        
        # Дополнительная статистика
        print("📈 Дополнительная статистика:")
        
        # Спортсмены без клуба с участиями
        athletes_without_club_with_participations = [
            a for a in athletes_without_club 
            if Participant.query.filter_by(athlete_id=a.id).count() > 0
        ]
        
        print(f"Спортсменов без клуба с участиями: {len(athletes_without_club_with_participations)}")
        
        # Топ-10 спортсменов без клуба по количеству участий
        athletes_with_participations = []
        for athlete in athletes_without_club:
            count = Participant.query.filter_by(athlete_id=athlete.id).count()
            if count > 0:
                athletes_with_participations.append((athlete, count))
        
        athletes_with_participations.sort(key=lambda x: x[1], reverse=True)
        
        if athletes_with_participations:
            print(f"\n🏆 Топ-10 спортсменов без клуба по количеству участий:")
            print("-" * 60)
            for i, (athlete, count) in enumerate(athletes_with_participations[:10], 1):
                print(f"{i:2d}. {athlete.full_name} - {count} участий")

def check_club_statistics():
    """Показывает статистику по клубам"""
    with app.app_context():
        print("\n" + "="*80)
        print("🏫 СТАТИСТИКА ПО КЛУБАМ")
        print("="*80)
        
        # Общая статистика по клубам
        total_clubs = Club.query.count()
        print(f"Всего клубов в базе: {total_clubs}")
        
        # Клубы с количеством спортсменов
        club_stats = db.session.query(
            Club.name,
            Club.id,
            db.func.count(Athlete.id).label('athlete_count')
        ).outerjoin(Athlete, Club.id == Athlete.club_id).group_by(
            Club.id, Club.name
        ).order_by(db.func.count(Athlete.id).desc()).all()
        
        print(f"\n📊 Топ-10 клубов по количеству спортсменов:")
        print("-" * 60)
        for i, (club_name, club_id, count) in enumerate(club_stats[:10], 1):
            print(f"{i:2d}. {club_name} - {count} спортсменов")

def main():
    """Основная функция"""
    try:
        check_missing_clubs()
        check_club_statistics()
        
        print("\n" + "="*80)
        print("✅ Проверка завершена!")
        print("="*80)
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
