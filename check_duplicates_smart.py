#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Умная проверка дубликатов с анализом ИМЕНИ
Помогает избежать объединения братьев/сестер
"""

from app import app, db
from models import Athlete, Participant
from sqlalchemy import func
from difflib import SequenceMatcher

def similarity(a, b):
    """Схожесть строк"""
    if not a or not b:
        return 0.0
    a_clean = ' '.join(a.lower().split())
    b_clean = ' '.join(b.lower().split())
    return SequenceMatcher(None, a_clean, b_clean).ratio()

def check_duplicates():
    """Проверяет дубликаты с детальным анализом"""
    with app.app_context():
        print("="*100)
        print("УМНАЯ ПРОВЕРКА ДУБЛИКАТОВ")
        print("="*100)
        print("Критерий: Одинаковая дата рождения + Одинаковая фамилия")
        print("Анализ: Проверяем схожесть ИМЕНИ чтобы не объединить братьев/сестер")
        print("="*100)
        print()
        
        # Находим даты рождения с дубликатами
        duplicates = db.session.query(
            Athlete.birth_date,
            Athlete.last_name,
            func.count(Athlete.id).label('count')
        ).filter(
            Athlete.birth_date.isnot(None),
            Athlete.last_name.isnot(None)
        ).group_by(
            Athlete.birth_date,
            Athlete.last_name
        ).having(
            func.count(Athlete.id) > 1
        ).all()
        
        print(f"Найдено групп с потенциальными дубликатами: {len(duplicates)}\n")
        
        if not duplicates:
            print("Дубликатов не найдено!")
            return
        
        # Анализируем каждую группу
        group_num = 0
        true_duplicates = 0
        possible_siblings = 0
        
        for birth_date, lastname, count in duplicates:
            # Получаем всех спортсменов с этой датой и фамилией
            athletes = Athlete.query.filter_by(
                birth_date=birth_date,
                last_name=lastname
            ).all()
            
            group_num += 1
            print("="*100)
            print(f"ГРУППА {group_num}: {lastname}, {birth_date.strftime('%d.%m.%Y')} ({len(athletes)} записей)")
            print("="*100)
            
            # Показываем всех в группе
            for i, athlete in enumerate(athletes, 1):
                participations = Participant.query.filter_by(athlete_id=athlete.id).count()
                free = Participant.query.filter_by(athlete_id=athlete.id, pct_ppname='БЕСП').count()
                
                print(f"\n{i}. ID {athlete.id}:")
                print(f"   Полное ФИО: {athlete.full_name}")
                print(f"   Имя: {athlete.first_name}")
                print(f"   Фамилия: {athlete.last_name}")
                print(f"   Отчество: {athlete.patronymic}")
                print(f"   Пол: {athlete.gender}")
                print(f"   Участий: {participations} (бесплатных: {free})")
            
            # Анализируем схожесть ИМЕН
            print("\n" + "-"*100)
            print("АНАЛИЗ СХОЖЕСТИ:")
            print("-"*100)
            
            is_duplicate = True
            
            for i in range(len(athletes)):
                for j in range(i + 1, len(athletes)):
                    a1 = athletes[i]
                    a2 = athletes[j]
                    
                    # Сравниваем полное ФИО
                    full_name_similarity = similarity(a1.full_name or '', a2.full_name or '')
                    
                    # Сравниваем только ИМЕНА
                    first_name_similarity = similarity(a1.first_name or '', a2.first_name or '')
                    
                    # Сравниваем отчества
                    patronymic_similarity = similarity(a1.patronymic or '', a2.patronymic or '')
                    
                    print(f"\nСравнение ID {a1.id} и ID {a2.id}:")
                    print(f"  Полное ФИО: {full_name_similarity*100:.1f}%")
                    print(f"  Имя: {first_name_similarity*100:.1f}%")
                    print(f"  Отчество: {patronymic_similarity*100:.1f}%")
                    
                    # Логика определения
                    if full_name_similarity > 0.8 and first_name_similarity > 0.8:
                        print(f"  >>> ВЕРОЯТНО ДУБЛИКАТ (можно объединить)")
                        true_duplicates += 1
                    elif first_name_similarity < 0.5:
                        print(f"  >>> РАЗНЫЕ ИМЕНА - возможно БРАТЬЯ/СЕСТРЫ (НЕ объединять!)")
                        is_duplicate = False
                        possible_siblings += 1
                    else:
                        print(f"  >>> НЕОДНОЗНАЧНО - проверьте вручную")
            
            print()
        
        # Итоги
        print("\n" + "="*100)
        print("ИТОГИ:")
        print("="*100)
        print(f"Групп с дубликатами: {group_num}")
        print(f"Истинных дубликатов (можно объединять): {true_duplicates}")
        print(f"Возможных братьев/сестер (НЕ объединять): {possible_siblings}")
        print("="*100)
        print("\nВНИМАНИЕ! Перед объединением проверьте каждую группу вручную!")
        print("Особенно группы где схожесть ИМЕНИ < 80%")
        print("="*100)

if __name__ == '__main__':
    check_duplicates()







