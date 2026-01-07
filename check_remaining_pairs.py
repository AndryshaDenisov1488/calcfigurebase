#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка оставшихся дубликатов пар
"""

from app import app, db
from models import Athlete, Participant
from sqlalchemy import func

with app.app_context():
    print("="*100)
    print("ПРОВЕРКА ОСТАВШИХСЯ ДУБЛИКАТОВ ПАР")
    print("="*100)
    
    # Ищем всех с "/" в фамилии (пары)
    all_pairs = Athlete.query.filter(
        Athlete.last_name.like('%/%')
    ).order_by(Athlete.last_name).all()
    
    print(f"\nВсего пар в БД: {len(all_pairs)}\n")
    
    # Группируем по дате рождения для поиска дубликатов
    pairs_by_date = {}
    for pair in all_pairs:
        if pair.birth_date:
            date_key = pair.birth_date.strftime('%Y-%m-%d')
            if date_key not in pairs_by_date:
                pairs_by_date[date_key] = []
            pairs_by_date[date_key].append(pair)
    
    # Ищем дубликаты
    duplicates_found = []
    
    for date, pairs in pairs_by_date.items():
        if len(pairs) > 1:
            duplicates_found.append((date, pairs))
    
    if not duplicates_found:
        print("ДУБЛИКАТОВ ПАР НЕ НАЙДЕНО!")
    else:
        print(f"НАЙДЕНО ГРУПП С ДУБЛИКАТАМИ: {len(duplicates_found)}\n")
        print("="*100)
        
        for i, (date, pairs) in enumerate(duplicates_found, 1):
            print(f"\nГРУППА {i}: Дата рождения {date} ({len(pairs)} записей)")
            print("-"*100)
            
            for j, pair in enumerate(pairs, 1):
                p_count = Participant.query.filter_by(athlete_id=pair.id).count()
                free_count = Participant.query.filter_by(athlete_id=pair.id, pct_ppname='БЕСП').count()
                
                print(f"\n  {j}. ID {pair.id}:")
                print(f"     Полное ФИО: {pair.full_name}")
                print(f"     Фамилия (last_name): {pair.last_name}")
                print(f"     Имя (first_name): {pair.first_name}")
                print(f"     Пол: {pair.gender}")
                print(f"     Участий: {p_count} (бесплатных: {free_count})")
            
            print()
    
    print("="*100)
    print("\nДЛЯ ОБЪЕДИНЕНИЯ ИСПОЛЬЗУЙТЕ:")
    print("  python merge_only_true_duplicates.py")
    print("="*100)







