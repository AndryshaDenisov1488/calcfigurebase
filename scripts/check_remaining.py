#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка оставшихся дубликатов после merge
"""

from app import app, db
from models import Athlete
from datetime import date

with app.app_context():
    # Проверяем пару ВАСЕНЕВА/СИТЬКО
    print("Проверка ВАСЕНЕВА/СИТЬКО (05.07.2012):")
    athletes = Athlete.query.filter_by(birth_date=date(2012, 7, 5)).all()
    
    for a in athletes:
        print(f"\nID {a.id}:")
        print(f"  ФИО: {a.full_name}")
        print(f"  Фамилия: '{a.last_name}'")
        print(f"  Фамилия UPPER: '{a.last_name.upper() if a.last_name else ''}'")
        print(f"  Имя: '{a.first_name}'")
        print(f"  Пол: {a.gender}")
    
    print(f"\n{'='*80}")
    print(f"Всего найдено: {len(athletes)}")
    
    if len(athletes) > 1:
        print("\nПОЧЕМУ НЕ ОБЪЕДИНИЛИСЬ:")
        # Проверяем различия
        lastnames = set(a.last_name.upper() if a.last_name else '' for a in athletes)
        print(f"  Разных фамилий (UPPER): {len(lastnames)}")
        for ln in lastnames:
            print(f"    - '{ln}'")

