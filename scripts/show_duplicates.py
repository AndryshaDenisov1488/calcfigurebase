#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для отображения дубликатов спортсменов в удобном формате
"""

from app import app, db
from models import Athlete, Participant, Event, Club
from sqlalchemy import func

def show_duplicates():
    """Показывает все дубликаты спортсменов"""
    with app.app_context():
        print("=" * 100)
        print(" " * 30 + "🔍 ПОИСК ДУБЛИКАТОВ СПОРТСМЕНОВ")
        print("=" * 100)
        
        # Находим все даты рождения с дубликатами
        duplicates = db.session.query(
            Athlete.birth_date,
            func.count(Athlete.id).label('count')
        ).group_by(
            Athlete.birth_date
        ).having(
            func.count(Athlete.id) > 1
        ).order_by(
            Athlete.birth_date.desc()
        ).all()
        
        total_duplicate_dates = len(duplicates)
        total_duplicate_athletes = sum(count for _, count in duplicates)
        
        print(f"\n📊 СТАТИСТИКА:")
        print(f"   Дат рождения с дубликатами: {total_duplicate_dates}")
        print(f"   Всего дублирующихся записей: {total_duplicate_athletes}")
        print(f"   Всего спортсменов в БД: {Athlete.query.count()}")
        
        print("\n" + "=" * 100)
        print("СПИСОК ДУБЛИКАТОВ:")
        print("=" * 100)
        
        for i, (birth_date, count) in enumerate(duplicates, 1):
            if not birth_date:
                continue
            
            print(f"\n{'─' * 100}")
            print(f"#{i}. 📅 Дата рождения: {birth_date.strftime('%d.%m.%Y')} — Дубликатов: {count}")
            print(f"{'─' * 100}")
            
            # Получаем всех спортсменов с этой датой
            athletes = Athlete.query.filter_by(birth_date=birth_date).all()
            
            for j, athlete in enumerate(athletes, 1):
                # Получаем участия
                participations = Participant.query.filter_by(athlete_id=athlete.id).all()
                free_count = sum(1 for p in participations if p.pct_ppname == 'БЕСП')
                paid_count = len(participations) - free_count
                
                # Получаем клуб
                club = Club.query.get(athlete.club_id) if athlete.club_id else None
                
                # Цветовой маркер
                if free_count > 0:
                    marker = "🟢"
                else:
                    marker = "⚪"
                
                print(f"\n   {marker} Спортсмен #{j}:")
                print(f"      ID базы данных: {athlete.id}")
                print(f"      ФИО: {athlete.full_name}")
                print(f"      Имя: {athlete.first_name}")
                print(f"      Фамилия: {athlete.last_name}")
                print(f"      Отчество: {athlete.patronymic or '-'}")
                print(f"      Пол: {athlete.gender or '-'}")
                print(f"      Клуб: {club.name if club else 'Не указан'} (ID: {athlete.club_id or '-'})")
                print(f"      Участий: {len(participations)} (🆓 {free_count} / 💰 {paid_count})")
                
                # Показываем турниры
                if participations:
                    print(f"      Турниры:")
                    for p in participations:
                        event = Event.query.get(p.event_id)
                        is_free = "🆓" if p.pct_ppname == 'БЕСП' else "💰"
                        event_name = event.name if event else "Неизвестно"
                        event_date = event.begin_date.strftime('%d.%m.%Y') if event and event.begin_date else '-'
                        print(f"         {is_free} {event_name} ({event_date})")
            
            # Анализ: это один человек или разные?
            print(f"\n   💡 АНАЛИЗ:")
            
            # Проверяем совпадение фамилий
            last_names = set(a.last_name for a in athletes if a.last_name)
            if len(last_names) == 1:
                print(f"      ✅ Одинаковая фамилия: {list(last_names)[0]}")
                print(f"      ⚠️  ВЕРОЯТНО ДУБЛИКАТ - один и тот же человек")
            else:
                print(f"      ❓ Разные фамилии: {', '.join(last_names)}")
                print(f"      ℹ️  Возможно разные люди с одной датой рождения")
            
            # Проверяем разные клубы
            club_ids = set(a.club_id for a in athletes if a.club_id)
            if len(club_ids) > 1:
                print(f"      ⚠️  Разные клубы: {len(club_ids)} клубов")
        
        print("\n" + "=" * 100)
        print("ИТОГО:")
        print("=" * 100)
        print(f"Найдено {total_duplicate_dates} групп дубликатов")
        print(f"Можно освободить ~{total_duplicate_athletes - total_duplicate_dates} записей путем объединения")
        print("\n💡 Для объединения конкретного дубликата используйте merge_duplicate_athletes.py")
        print("=" * 100)

def show_by_date(date_str):
    """Показывает дубликаты для конкретной даты"""
    with app.app_context():
        from datetime import datetime
        
        try:
            birth_date = datetime.strptime(date_str, '%d.%m.%Y').date()
        except ValueError:
            print(f"❌ Неверный формат даты! Используйте: ДД.ММ.ГГГГ (например: 05.10.2012)")
            return
        
        athletes = Athlete.query.filter_by(birth_date=birth_date).all()
        
        if not athletes:
            print(f"❌ Спортсмены с датой рождения {date_str} не найдены")
            return
        
        if len(athletes) == 1:
            print(f"✅ Спортсмен с датой рождения {date_str} только один (дубликатов нет)")
            return
        
        print("=" * 100)
        print(f"🔍 ДУБЛИКАТЫ ДЛЯ ДАТЫ: {date_str}")
        print("=" * 100)
        
        for i, athlete in enumerate(athletes, 1):
            participations = Participant.query.filter_by(athlete_id=athlete.id).all()
            free_count = sum(1 for p in participations if p.pct_ppname == 'БЕСП')
            club = Club.query.get(athlete.club_id) if athlete.club_id else None
            
            print(f"\nСпортсмен #{i}:")
            print(f"  ID: {athlete.id}")
            print(f"  ФИО: {athlete.full_name}")
            print(f"  Клуб: {club.name if club else 'Не указан'}")
            print(f"  Участий: {len(participations)} (бесплатных: {free_count})")
            
            if participations:
                print(f"  Турниры:")
                for p in participations:
                    event = Event.query.get(p.event_id)
                    is_free = "🆓" if p.pct_ppname == 'БЕСП' else "💰"
                    print(f"    {is_free} {event.name if event else 'Неизвестно'}")
        
        print("\n" + "=" * 100)

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        # Показываем дубликаты для конкретной даты
        show_by_date(sys.argv[1])
    else:
        # Показываем все дубликаты
        show_duplicates()



