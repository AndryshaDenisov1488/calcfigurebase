#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для проверки корректности назначения клубов в БД
"""

from app import app, db
from models import Club, Athlete, Participant, Event
from sqlalchemy import func

def verify_database_integrity():
    """Проверяет целостность данных о клубах"""
    print(f"\n{'='*80}")
    print(f"🔍 ПРОВЕРКА ЦЕЛОСТНОСТИ ДАННЫХ О КЛУБАХ")
    print(f"{'='*80}\n")
    
    with app.app_context():
        # Общая статистика
        total_clubs = Club.query.count()
        total_athletes = Athlete.query.count()
        athletes_with_club = Athlete.query.filter(Athlete.club_id.isnot(None)).count()
        athletes_without_club = Athlete.query.filter(Athlete.club_id.is_(None)).count()
        total_events = Event.query.count()
        
        print(f"📊 ОБЩАЯ СТАТИСТИКА:")
        print("-" * 80)
        print(f"Всего клубов: {total_clubs}")
        print(f"Всего спортсменов: {total_athletes}")
        print(f"  - С клубом: {athletes_with_club} ({athletes_with_club/total_athletes*100:.1f}%)")
        print(f"  - Без клуба: {athletes_without_club} ({athletes_without_club/total_athletes*100:.1f}%)")
        print(f"Всего турниров: {total_events}")
        
        # Проверка конфликтующих external_id
        print(f"\n⚠️  ПРОВЕРКА КОНФЛИКТУЮЩИХ EXTERNAL_ID:")
        print("-" * 80)
        
        conflicting_ids = db.session.query(
            Club.external_id,
            func.count(Club.id).label('count')
        ).filter(
            Club.external_id.isnot(None),
            Club.external_id != ''
        ).group_by(
            Club.external_id
        ).having(
            func.count(Club.id) > 1
        ).all()
        
        if conflicting_ids:
            print(f"❌ НАЙДЕНО {len(conflicting_ids)} КОНФЛИКТУЮЩИХ EXTERNAL_ID!")
            for ext_id, count in conflicting_ids[:10]:
                print(f"\n   External ID: {ext_id} ({count} клубов)")
                clubs = Club.query.filter_by(external_id=ext_id).all()
                for club in clubs:
                    athletes_count = Athlete.query.filter_by(club_id=club.id).count()
                    print(f"      - ID {club.id:3d}: {club.name} ({athletes_count} спортсменов)")
            
            if len(conflicting_ids) > 10:
                print(f"\n   ... и еще {len(conflicting_ids) - 10} конфликтов")
        else:
            print(f"✅ Конфликтующих external_id не найдено")
        
        # Проверка дубликатов клубов по названию
        print(f"\n🔍 ПРОВЕРКА ДУБЛИКАТОВ КЛУБОВ:")
        print("-" * 80)
        
        duplicate_names = db.session.query(
            Club.name,
            func.count(Club.id).label('count')
        ).group_by(
            Club.name
        ).having(
            func.count(Club.id) > 1
        ).all()
        
        if duplicate_names:
            print(f"⚠️  НАЙДЕНО {len(duplicate_names)} ДУБЛИКАТОВ НАЗВАНИЙ!")
            for name, count in duplicate_names:
                print(f"\n   '{name}' ({count} записей)")
                clubs = Club.query.filter_by(name=name).all()
                for club in clubs:
                    athletes_count = Athlete.query.filter_by(club_id=club.id).count()
                    print(f"      - ID {club.id:3d}: external_id={club.external_id}, спортсменов={athletes_count}")
        else:
            print(f"✅ Дубликатов названий не найдено")
        
        # Топ-10 клубов по количеству спортсменов
        print(f"\n🏆 ТОП-10 КЛУБОВ ПО КОЛИЧЕСТВУ СПОРТСМЕНОВ:")
        print("-" * 80)
        
        top_clubs = db.session.query(
            Club.name,
            Club.id,
            func.count(Athlete.id).label('athlete_count')
        ).outerjoin(
            Athlete, Club.id == Athlete.club_id
        ).group_by(
            Club.id, Club.name
        ).order_by(
            func.count(Athlete.id).desc()
        ).limit(10).all()
        
        for i, (name, club_id, count) in enumerate(top_clubs, 1):
            print(f"{i:2d}. {name} - {count} спортсменов (ID: {club_id})")
        
        # Проверка спортсменов без клуба
        if athletes_without_club > 0:
            print(f"\n⚠️  СПОРТСМЕНЫ БЕЗ КЛУБА:")
            print("-" * 80)
            
            athletes_no_club = Athlete.query.filter(
                Athlete.club_id.is_(None)
            ).limit(10).all()
            
            for i, athlete in enumerate(athletes_no_club, 1):
                participations = Participant.query.filter_by(athlete_id=athlete.id).count()
                print(f"{i:2d}. {athlete.full_name} (ID: {athlete.id}, участий: {participations})")
            
            if athletes_without_club > 10:
                print(f"\n   ... и еще {athletes_without_club - 10} спортсменов")
        
        # Итоговая оценка
        print(f"\n{'='*80}")
        print(f"📊 ИТОГОВАЯ ОЦЕНКА")
        print(f"{'='*80}\n")
        
        issues = []
        
        if athletes_without_club > 0:
            issues.append(f"❌ {athletes_without_club} спортсменов без клуба")
        
        if conflicting_ids:
            issues.append(f"❌ {len(conflicting_ids)} конфликтующих external_id")
        
        if duplicate_names:
            issues.append(f"⚠️  {len(duplicate_names)} дубликатов названий клубов")
        
        if issues:
            print(f"⚠️  НАЙДЕНЫ ПРОБЛЕМЫ:")
            for issue in issues:
                print(f"   {issue}")
        else:
            print(f"✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ!")
            print(f"   База данных не содержит проблем с клубами")

if __name__ == '__main__':
    verify_database_integrity()



