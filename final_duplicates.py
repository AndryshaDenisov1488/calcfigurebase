#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ПРОСТОЙ ПОИСК ДУБЛИКАТОВ
Критерий: Дата рождения + Фамилия
"""

from app import app, db
from models import Athlete, Participant, Event, Club
from sqlalchemy import func

def find_all_duplicates():
    """Находит всех дубликатов по дате рождения + фамилии"""
    with app.app_context():
        print("=" * 100)
        print(" " * 30 + "ПОИСК ДУБЛИКАТОВ")
        print("=" * 100)
        print("\nКритерий: Одинаковая дата рождения + Одинаковая фамилия\n")
        
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
        
        duplicate_groups = []
        
        for birth_date, count in duplicates:
            if not birth_date:
                continue
            
            # Получаем всех спортсменов с этой датой
            athletes = Athlete.query.filter_by(birth_date=birth_date).all()
            
            # Группируем по фамилиям
            by_lastname = {}
            for athlete in athletes:
                lastname = (athlete.last_name or "").strip().upper()
                if not lastname:
                    continue
                
                if lastname not in by_lastname:
                    by_lastname[lastname] = []
                by_lastname[lastname].append(athlete)
            
            # Смотрим, где больше 1 человека с одной фамилией
            for lastname, group in by_lastname.items():
                if len(group) > 1:
                    duplicate_groups.append({
                        'birth_date': birth_date,
                        'lastname': lastname,
                        'athletes': group
                    })
        
        # Выводим результаты
        print("=" * 100)
        print("НАЙДЕННЫЕ ДУБЛИКАТЫ:")
        print("=" * 100)
        
        total_to_remove = 0
        
        for i, dup_group in enumerate(duplicate_groups, 1):
            birth_date = dup_group['birth_date']
            lastname = dup_group['lastname']
            athletes = dup_group['athletes']
            
            print(f"\n{'-' * 100}")
            print(f"#{i}. Дата: {birth_date.strftime('%d.%m.%Y')} | Фамилия: {lastname} | Дубликатов: {len(athletes)}")
            print(f"{'-' * 100}")
            
            for j, athlete in enumerate(athletes, 1):
                participations = Participant.query.filter_by(athlete_id=athlete.id).all()
                free_count = sum(1 for p in participations if p.pct_ppname == 'БЕСП')
                paid_count = len(participations) - free_count
                
                club = Club.query.get(athlete.club_id) if athlete.club_id else None
                
                marker = "[БЕСП]" if free_count > 0 else "[ПЛАТ]"
                
                print(f"\n   {marker} Спортсмен #{j}:")
                print(f"      ID: {athlete.id}")
                print(f"      ФИО: {athlete.full_name}")
                print(f"      Имя: {athlete.first_name}")
                print(f"      Фамилия: {athlete.last_name}")
                print(f"      Пол: {athlete.gender or '-'}")
                print(f"      Клуб: {club.name if club else 'Не указан'}")
                print(f"      Участий: {len(participations)} (Бесп: {free_count} / Плат: {paid_count})")
                
                if participations:
                    print(f"      Турниры:")
                    for p in participations:
                        event = Event.query.get(p.event_id)
                        is_free = "[БЕСПЛАТНО]" if p.pct_ppname == 'БЕСП' else "[ПЛАТНО]"
                        event_name = event.name if event else "Неизвестно"
                        event_date = event.begin_date.strftime('%d.%m.%Y') if event and event.begin_date else '-'
                        print(f"         {is_free} {event_name} ({event_date})")
            
            # Определяем тип
            if '/' in athletes[0].full_name:
                dup_type = "ПАРА/ТАНЦЫ"
            else:
                dup_type = "ОДИНОЧНИК"
            
            print(f"\n   ТИП: {dup_type}")
            
            # Определяем основного
            main_athlete = max(athletes, key=lambda a: (
                len(a.full_name or ""),
                Participant.query.filter_by(athlete_id=a.id).count()
            ))
            
            others = [a for a in athletes if a.id != main_athlete.id]
            
            print(f"\n   РЕКОМЕНДАЦИЯ:")
            print(f"      Основной: ID {main_athlete.id} - {main_athlete.full_name}")
            
            if others:
                total_participations = sum(
                    Participant.query.filter_by(athlete_id=a.id).count() 
                    for a in others
                )
                print(f"      Удалить: {', '.join([f'ID {a.id}' for a in others])}")
                print(f"      Перенесется участий: {total_participations}")
                
                total_to_remove += len(others)
            
            # Итоговая статистика после объединения
            total_part = sum(
                Participant.query.filter_by(athlete_id=a.id).count() 
                for a in athletes
            )
            total_free = sum(
                Participant.query.filter_by(athlete_id=a.id, pct_ppname='БЕСП').count() 
                for a in athletes
            )
            
            print(f"      После объединения: {total_part} участий ({total_free} бесплатных)")
        
        print("\n" + "=" * 100)
        print("ИТОГО:")
        print("=" * 100)
        print(f"Найдено групп дубликатов: {len(duplicate_groups)}")
        print(f"Можно удалить записей: {total_to_remove}")
        print(f"Останется уникальных: {Athlete.query.count() - total_to_remove}")
        print(f"\nКритерий: Одинаковая фамилия + Одинаковая дата рождения")
        print(f"Пол не учитывается (может быть ошибочным)")
        print("=" * 100)
        
        return duplicate_groups

if __name__ == '__main__':
    find_all_duplicates()

