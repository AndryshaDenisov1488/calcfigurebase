#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Простой список дубликатов: Дата рождения + Фамилия
"""

from app import app, db
from models import Athlete, Participant, Event, Club
from sqlalchemy import func

def list_all_duplicates():
    """Список всех дубликатов"""
    with app.app_context():
        print("="*100)
        print("ПОИСК ДУБЛИКАТОВ: Одинаковая дата рождения + Одинаковая фамилия")
        print("="*100)
        
        # Находим дубликаты по дате рождения
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
        
        all_groups = []
        
        for birth_date, count in duplicates:
            if not birth_date:
                continue
            
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
            
            # Добавляем группы где больше 1
            for lastname, group in by_lastname.items():
                if len(group) > 1:
                    all_groups.append({
                        'birth_date': birth_date,
                        'lastname': lastname,
                        'athletes': group
                    })
        
        print(f"\nНайдено групп дубликатов: {len(all_groups)}\n")
        print("="*100)
        
        total_to_remove = 0
        
        for i, group in enumerate(all_groups, 1):
            birth_date = group['birth_date']
            lastname = group['lastname']
            athletes = group['athletes']
            
            print(f"\n{'-'*100}")
            print(f"#{i}. {birth_date.strftime('%d.%m.%Y')} | {lastname} | Дубликатов: {len(athletes)}")
            print(f"{'-'*100}")
            
            for j, athlete in enumerate(athletes, 1):
                participations = Participant.query.filter_by(athlete_id=athlete.id).all()
                free_count = sum(1 for p in participations if p.pct_ppname == 'БЕСП')
                paid_count = len(participations) - free_count
                
                club = Club.query.get(athlete.club_id) if athlete.club_id else None
                
                print(f"\n   Спортсмен #{j}:")
                print(f"      ID: {athlete.id}")
                print(f"      ФИО: {athlete.full_name}")
                print(f"      Пол: {athlete.gender or '-'}")
                print(f"      Клуб: {club.name if club else 'Не указан'}")
                print(f"      Участий: {len(participations)} (Бесплатных: {free_count}, Платных: {paid_count})")
                
                if participations:
                    for p in participations:
                        event = Event.query.get(p.event_id)
                        if event:
                            is_free = "БЕСП" if p.pct_ppname == 'БЕСП' else "ПЛАТ"
                            print(f"         [{is_free}] {event.name} ({event.begin_date.strftime('%d.%m.%Y') if event.begin_date else '-'})")
            
            # Тип дубликата
            if '/' in athletes[0].full_name:
                print(f"\n   ТИП: ПАРА/ТАНЦЫ")
            else:
                print(f"\n   ТИП: ОДИНОЧНИК")
            
            # Рекомендация
            main = max(athletes, key=lambda a: (
                len(a.full_name or ""),
                Participant.query.filter_by(athlete_id=a.id).count()
            ))
            
            others = [a for a in athletes if a.id != main.id]
            
            print(f"\n   ОБЪЕДИНЕНИЕ:")
            print(f"      Основной: ID {main.id}")
            if others:
                print(f"      Удалить: {', '.join([f'ID {a.id}' for a in others])}")
                total_to_remove += len(others)
            
            # Итог
            total_part = sum(Participant.query.filter_by(athlete_id=a.id).count() for a in athletes)
            total_free = sum(Participant.query.filter_by(athlete_id=a.id, pct_ppname='БЕСП').count() for a in athletes)
            
            print(f"      Итого после: {total_part} участий ({total_free} бесплатных)")
        
        print("\n"+"="*100)
        print("ИТОГО:")
        print("="*100)
        print(f"Групп дубликатов: {len(all_groups)}")
        print(f"Записей к удалению: {total_to_remove}")
        print(f"Всего спортсменов: {Athlete.query.count()}")
        print(f"Останется после чистки: {Athlete.query.count() - total_to_remove}")
        print("="*100)

if __name__ == '__main__':
    list_all_duplicates()

