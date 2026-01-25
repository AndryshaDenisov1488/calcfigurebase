#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Прямая проверка данных в базе для поиска
"""
import sys
import os

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_factory import create_app
from extensions import db
from models import Athlete

app = create_app()

with app.app_context():
    print("=" * 80)
    print("ПРЯМАЯ ПРОВЕРКА ДАННЫХ В БАЗЕ")
    print("=" * 80)
    print()
    
    # Проверяем конкретные ID из логов
    test_ids = [1281, 1322, 1332]
    
    print("Проверка спортсменов из логов:")
    print("-" * 80)
    for athlete_id in test_ids:
        athlete = Athlete.query.get(athlete_id)
        if athlete:
            print(f"\nID: {athlete.id}")
            print(f"  first_name: '{athlete.first_name}' -> lower: '{athlete.first_name.lower() if athlete.first_name else None}'")
            print(f"  last_name: '{athlete.last_name}' -> lower: '{athlete.last_name.lower() if athlete.last_name else None}'")
            print(f"  patronymic: '{athlete.patronymic}' -> lower: '{athlete.patronymic.lower() if athlete.patronymic else None}'")
            print(f"  full_name_xml: '{athlete.full_name_xml}' -> lower: '{athlete.full_name_xml.lower() if athlete.full_name_xml else None}'")
            
            # Проверяем, содержит ли "ив"
            search_term = "ив"
            contains_iv = False
            where_found = []
            
            if athlete.first_name and search_term in athlete.first_name.lower():
                contains_iv = True
                where_found.append('first_name')
            if athlete.last_name and search_term in athlete.last_name.lower():
                contains_iv = True
                where_found.append('last_name')
            if athlete.patronymic and search_term in athlete.patronymic.lower():
                contains_iv = True
                where_found.append('patronymic')
            if athlete.full_name_xml and search_term in athlete.full_name_xml.lower():
                contains_iv = True
                where_found.append('full_name_xml')
            
            print(f"  Содержит '{search_term}': {contains_iv} {'(в ' + ', '.join(where_found) + ')' if where_found else ''}")
        else:
            print(f"\nID {athlete_id}: НЕ НАЙДЕН")
    
    print("\n" + "=" * 80)
    print("ПОИСК 'иван' ПРЯМЫМ SQL ЗАПРОСОМ")
    print("=" * 80)
    
    # Прямой SQL запрос
    search_term = "иван"
    
    print(f"\nПоиск '{search_term}' в first_name (через db.func.lower):")
    athletes = db.session.query(Athlete).filter(
        db.func.lower(Athlete.first_name).like(f'%{search_term}%')
    ).limit(5).all()
    print(f"Найдено: {len(athletes)}")
    for a in athletes:
        print(f"  - ID {a.id}: '{a.first_name}' '{a.last_name}'")
    
    # Альтернативный способ - через ilike (должен работать без lower)
    print(f"\nПоиск '{search_term}' в first_name (через ilike):")
    athletes = db.session.query(Athlete).filter(
        Athlete.first_name.ilike(f'%{search_term}%')
    ).limit(5).all()
    print(f"Найдено: {len(athletes)}")
    for a in athletes:
        print(f"  - ID {a.id}: '{a.first_name}' '{a.last_name}'")
    
    # Прямой поиск без преобразования регистра
    print(f"\nПоиск '{search_term}' в first_name (прямой LIKE, регистрозависимый):")
    athletes = db.session.query(Athlete).filter(
        Athlete.first_name.like(f'%{search_term}%')
    ).limit(5).all()
    print(f"Найдено: {len(athletes)}")
    for a in athletes:
        print(f"  - ID {a.id}: '{a.first_name}' '{a.last_name}'")
    
    # Поиск с заглавной буквы
    search_term_capitalized = search_term.capitalize()
    print(f"\nПоиск '{search_term_capitalized}' в first_name (с заглавной буквы):")
    athletes = db.session.query(Athlete).filter(
        Athlete.first_name.like(f'%{search_term_capitalized}%')
    ).limit(5).all()
    print(f"Найдено: {len(athletes)}")
    for a in athletes:
        print(f"  - ID {a.id}: '{a.first_name}' '{a.last_name}'")
    
    print(f"\nПоиск '{search_term}' в last_name:")
    athletes = db.session.query(Athlete).filter(
        db.func.lower(Athlete.last_name).like(f'%{search_term}%')
    ).limit(5).all()
    print(f"Найдено: {len(athletes)}")
    for a in athletes:
        print(f"  - ID {a.id}: '{a.first_name}' '{a.last_name}'")
    
    print(f"\nПоиск '{search_term}' в full_name_xml:")
    athletes = db.session.query(Athlete).filter(
        db.func.lower(Athlete.full_name_xml).like(f'%{search_term}%')
    ).limit(5).all()
    print(f"Найдено: {len(athletes)}")
    for a in athletes:
        print(f"  - ID {a.id}: '{a.full_name_xml}'")
    
    print(f"\nПоиск '{search_term}' в patronymic:")
    athletes = db.session.query(Athlete).filter(
        db.func.lower(Athlete.patronymic).like(f'%{search_term}%')
    ).limit(5).all()
    print(f"Найдено: {len(athletes)}")
    for a in athletes:
        print(f"  - ID {a.id}: '{a.patronymic}'")
    
    print("\n" + "=" * 80)
    print("ПРОВЕРКА: Почему 'ив' находит 'Оливия'?")
    print("=" * 80)
    
    # Проверяем, почему "ив" находит "Оливия"
    search_term = "ив"
    print(f"\nПоиск '{search_term}' - должен найти только имена с 'ив':")
    athletes = db.session.query(Athlete).filter(
        db.or_(
            db.func.lower(Athlete.first_name).like(f'%{search_term}%'),
            db.func.lower(Athlete.last_name).like(f'%{search_term}%'),
            db.func.lower(Athlete.full_name_xml).like(f'%{search_term}%'),
            db.func.lower(Athlete.patronymic).like(f'%{search_term}%')
        )
    ).limit(10).all()
    
    print(f"Найдено: {len(athletes)}")
    for a in athletes:
        found_in = []
        if a.first_name and search_term in a.first_name.lower():
            found_in.append(f"first_name='{a.first_name}'")
        if a.last_name and search_term in a.last_name.lower():
            found_in.append(f"last_name='{a.last_name}'")
        if a.patronymic and search_term in a.patronymic.lower():
            found_in.append(f"patronymic='{a.patronymic}'")
        if a.full_name_xml and search_term in a.full_name_xml.lower():
            found_in.append(f"full_name_xml='{a.full_name_xml}'")
        
        print(f"  - ID {a.id}: {', '.join(found_in)}")
    
    print("\n" + "=" * 80)
    print("ПРОВЕРКА ЗАВЕРШЕНА")
    print("=" * 80)
