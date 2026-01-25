#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для тестирования поиска спортсменов
"""
import sys
import os

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_factory import create_app
from extensions import db
from models import Athlete
from utils.search_utils import normalize_search_term, create_multi_field_search_filter

app = create_app()

with app.app_context():
    print("=" * 80)
    print("ТЕСТИРОВАНИЕ ПОИСКА СПОРТСМЕНОВ")
    print("=" * 80)
    print()
    
    # Тестовые запросы
    test_queries = ['ив', 'иван', 'иванов', 'оливия', 'ев']
    
    for search_term in test_queries:
        print(f"\n{'='*80}")
        print(f"Поиск: '{search_term}'")
        print(f"{'='*80}")
        
        normalized = normalize_search_term(search_term)
        print(f"Нормализовано: '{normalized}' (длина: {len(normalized)})")
        
        # Создаем фильтр
        search_filter = create_multi_field_search_filter(
            search_term,
            Athlete.first_name,
            Athlete.last_name,
            Athlete.full_name_xml,
            Athlete.patronymic
        )
        
        if search_filter is None:
            print("❌ Фильтр не создан")
            continue
        
        print(f"✅ Фильтр создан")
        
        # Ищем спортсменов
        athletes = db.session.query(Athlete).filter(search_filter).limit(10).all()
        
        print(f"Найдено: {len(athletes)} спортсменов")
        print()
        
        for athlete in athletes:
            print(f"  ID: {athlete.id}")
            print(f"    first_name: '{athlete.first_name}'")
            print(f"    last_name: '{athlete.last_name}'")
            print(f"    patronymic: '{athlete.patronymic}'")
            print(f"    full_name_xml: '{athlete.full_name_xml}'")
            print(f"    full_name (computed): '{athlete.full_name}'")
            
            # Проверяем, где именно найдено
            found_in = []
            if athlete.first_name and normalized in athlete.first_name.lower():
                found_in.append('first_name')
            if athlete.last_name and normalized in athlete.last_name.lower():
                found_in.append('last_name')
            if athlete.patronymic and normalized in athlete.patronymic.lower():
                found_in.append('patronymic')
            if athlete.full_name_xml and normalized in athlete.full_name_xml.lower():
                found_in.append('full_name_xml')
            
            print(f"    Найдено в: {', '.join(found_in) if found_in else 'НЕ НАЙДЕНО (ОШИБКА!)'}")
            print()
        
        # Проверяем поиск по каждому полю отдельно
        print("  Проверка по полям:")
        first_name_count = db.session.query(Athlete).filter(Athlete.first_name.ilike(f'%{normalized}%')).count()
        last_name_count = db.session.query(Athlete).filter(Athlete.last_name.ilike(f'%{normalized}%')).count()
        full_name_count = db.session.query(Athlete).filter(Athlete.full_name_xml.ilike(f'%{normalized}%')).count() if Athlete.full_name_xml else 0
        patronymic_count = db.session.query(Athlete).filter(Athlete.patronymic.ilike(f'%{normalized}%')).count() if Athlete.patronymic else 0
        
        print(f"    first_name: {first_name_count}")
        print(f"    last_name: {last_name_count}")
        print(f"    full_name_xml: {full_name_count}")
        print(f"    patronymic: {patronymic_count}")
        
        # Показываем примеры по каждому полю
        if first_name_count > 0:
            samples = db.session.query(Athlete).filter(Athlete.first_name.ilike(f'%{normalized}%')).limit(3).all()
            print(f"    Примеры по first_name:")
            for s in samples:
                print(f"      - '{s.first_name}' '{s.last_name}'")
        
        if last_name_count > 0:
            samples = db.session.query(Athlete).filter(Athlete.last_name.ilike(f'%{normalized}%')).limit(3).all()
            print(f"    Примеры по last_name:")
            for s in samples:
                print(f"      - '{s.first_name}' '{s.last_name}'")
        
        if full_name_count > 0:
            samples = db.session.query(Athlete).filter(Athlete.full_name_xml.ilike(f'%{normalized}%')).limit(3).all()
            print(f"    Примеры по full_name_xml:")
            for s in samples:
                print(f"      - '{s.full_name_xml}'")
    
    print("\n" + "=" * 80)
    print("ТЕСТ ЗАВЕРШЕН")
    print("=" * 80)
