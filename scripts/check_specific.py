#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка конкретных спортсменов
"""

from app import app, db
from models import Athlete, Participant
from difflib import SequenceMatcher

def similarity(a, b):
    if not a or not b:
        return 0.0
    a_clean = ' '.join(a.lower().split())
    b_clean = ' '.join(b.lower().split())
    return SequenceMatcher(None, a_clean, b_clean).ratio()

with app.app_context():
    surnames = ['ЗАНЧЕВА', 'ШУРАВИНА', 'КАЛИНИНА', 'МАЛЮТИНА']
    
    for surname in surnames:
        print("\n" + "="*100)
        print(f"Поиск: {surname}")
        print("="*100)
        
        athletes = Athlete.query.filter(
            Athlete.last_name.like(f'%{surname}%')
        ).all()
        
        if not athletes:
            print(f"Не найдено")
            continue
        
        print(f"Найдено: {len(athletes)}\n")
        
        for athlete in athletes:
            p_count = Participant.query.filter_by(athlete_id=athlete.id).count()
            f_count = Participant.query.filter_by(athlete_id=athlete.id, pct_ppname='БЕСП').count()
            
            print(f"ID {athlete.id}:")
            print(f"  ФИО: {athlete.full_name}")
            print(f"  Фамилия: '{athlete.last_name}'")
            print(f"  Дата рождения: {athlete.birth_date}")
            print(f"  Пол: {athlete.gender}")
            print(f"  Участий: {p_count} (бесплатных: {f_count})")
            print()
        
        # Если больше 1 - проверяем схожесть
        if len(athletes) > 1:
            print("АНАЛИЗ СХОЖЕСТИ:")
            for i, a1 in enumerate(athletes):
                for j, a2 in enumerate(athletes):
                    if i >= j:
                        continue
                    
                    sim = similarity(a1.full_name, a2.full_name)
                    same_date = a1.birth_date == a2.birth_date
                    
                    if same_date and sim > 0.80:
                        print(f"  ДУБЛИКАТ: ID {a1.id} и ID {a2.id}")
                        print(f"    Совпадение ФИО: {sim*100:.1f}%")
                        print(f"    Дата одинаковая: ДА")
                    else:
                        print(f"  РАЗНЫЕ: ID {a1.id} и ID {a2.id}")
                        print(f"    Совпадение ФИО: {sim*100:.1f}%")
                        print(f"    Дата одинаковая: {'ДА' if same_date else 'НЕТ'}")

