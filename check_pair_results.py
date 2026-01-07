#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка результатов для пары КРЕМЕР/ЦЕЛКОВСКИЙ на турнире "Мемориал И.Я. Рабер"
"""

from app import app, db
from models import Athlete, Event, Category, Participant

with app.app_context():
    print("="*100)
    print("ПРОВЕРКА РЕЗУЛЬТАТОВ ПАРЫ")
    print("="*100)
    
    # 1. Находим пару
    pair = Athlete.query.filter(
        Athlete.last_name.like('%КРЕМЕР%ЦЕЛКОВСКИЙ%')
    ).first()
    
    if not pair:
        # Попробуем найти по "/" в фамилии и имени
        pair = Athlete.query.filter(
            Athlete.last_name.like('%/%')
        ).filter(
            db.or_(
                Athlete.last_name.like('%КРЕМЕР%'),
                Athlete.first_name.like('%КРЕМЕР%')
            )
        ).first()
    
    if not pair:
        print("Пара не найдена!")
    else:
        print(f"\nПАРА:")
        print(f"  ID: {pair.id}")
        print(f"  ФИО: {pair.full_name}")
        print(f"  Фамилия: {pair.last_name}")
        print(f"  Имя: {pair.first_name}")
        print(f"  Пол: {pair.gender}")
        print(f"  Дата рождения: {pair.birth_date}")
        
        # 2. Находим турнир "Мемориал И.Я. Рабер"
        event = Event.query.filter(
            Event.name.like('%Рабер%')
        ).first()
        
        if not event:
            print("\nТурнир 'Мемориал И.Я. Рабер' не найден!")
        else:
            print(f"\nТУРНИР:")
            print(f"  ID: {event.id}")
            print(f"  Название: {event.name}")
            print(f"  Дата начала: {event.begin_date}")
            print(f"  Дата окончания: {event.end_date}")
            
            # 3. Находим все категории этого турнира
            categories = Category.query.filter_by(event_id=event.id).all()
            
            print(f"\nКАТЕГОРИИ ТУРНИРА ({len(categories)} шт):")
            for cat in categories:
                print(f"  - ID {cat.id}: {cat.name} (пол: {cat.gender}, тип: {cat.category_type})")
            
            # 4. Находим участия этой пары на этом турнире
            participations = Participant.query.filter_by(
                athlete_id=pair.id
            ).join(
                Category, Participant.category_id == Category.id
            ).filter(
                Category.event_id == event.id
            ).all()
            
            print(f"\nУЧАСТИЯ ПАРЫ НА ЭТОМ ТУРНИРЕ ({len(participations)} шт):")
            
            if not participations:
                print("  НЕТ УЧАСТИЙ!")
                print("\n  Возможные причины:")
                print("    1. Данные не были импортированы из XML")
                print("    2. Пара была объединена с дубликатом, и участия остались у старого ID")
                print("    3. В XML используется другое написание фамилий")
                
                # Проверяем есть ли участия на других турнирах
                other_participations = Participant.query.filter_by(
                    athlete_id=pair.id
                ).all()
                
                print(f"\n  Всего участий у этой пары: {len(other_participations)}")
                if other_participations:
                    print("\n  ПРИМЕРЫ УЧАСТИЙ:")
                    for p in other_participations[:5]:
                        cat = Category.query.get(p.category_id)
                        evt = Event.query.get(cat.event_id) if cat else None
                        print(f"    - Турнир: {evt.name if evt else 'Unknown'}")
                        print(f"      Категория: {cat.name if cat else 'Unknown'}")
                        print(f"      Место: {p.total_place}, Баллы: {p.total_points/100 if p.total_points else 0}")
                        print(f"      Бесплатно: {p.pct_ppname}")
                        print()
            else:
                for p in participations:
                    cat = Category.query.get(p.category_id)
                    print(f"\n  Участие ID {p.id}:")
                    print(f"    Категория: {cat.name if cat else 'Unknown'} (ID {p.category_id})")
                    print(f"    Место: {p.total_place}")
                    print(f"    Баллы: {p.total_points} (= {p.total_points/100 if p.total_points else 0} баллов)")
                    print(f"    Бесплатно: {p.pct_ppname}")
                    print(f"    Статус: {p.status}")
                    
                    # Проверяем есть ли Performance для этого участия
                    from models import Performance
                    performances = Performance.query.filter_by(participant_id=p.id).all()
                    print(f"    Сегментов Performance: {len(performances)}")
                    
                    if performances:
                        print(f"    ДЕТАЛИ СЕГМЕНТОВ:")
                        for perf in performances:
                            from models import Segment
                            segment = Segment.query.get(perf.segment_id)
                            print(f"      - Сегмент: {segment.name if segment else 'Unknown'}")
                            print(f"        Баллы сегмента: {perf.total_segment_score}")
                            print(f"        Место в сегменте: {perf.rank}")
            
            print("\n" + "="*100)
            
            # 5. Проверяем все пары с фамилией КРЕМЕР
            print("\nВСЕ СПОРТСМЕНЫ С ФАМИЛИЕЙ КРЕМЕР:")
            all_kremers = Athlete.query.filter(
                db.or_(
                    Athlete.last_name.like('%КРЕМЕР%'),
                    Athlete.first_name.like('%КРЕМЕР%')
                )
            ).all()
            
            for athlete in all_kremers:
                participations_count = Participant.query.filter_by(athlete_id=athlete.id).count()
                print(f"\n  ID {athlete.id}: {athlete.full_name}")
                print(f"    Фамилия: {athlete.last_name}")
                print(f"    Пол: {athlete.gender}")
                print(f"    Участий: {participations_count}")
    
    print("\n" + "="*100)

