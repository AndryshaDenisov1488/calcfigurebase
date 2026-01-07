#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
УМНОЕ объединение дубликатов
Учитывает разные форматы записи фамилий для пар
"""

from app import app, db
from models import Athlete, Participant, Event, Club
from sqlalchemy import func
from datetime import datetime
import os
import shutil
import re

def extract_surnames_from_pair(lastname):
    """Извлекает только ЗАГЛАВНЫЕ слова (фамилии) из строки с парой"""
    if not lastname:
        return set()
    
    # Все слова в верхнем регистре
    words = lastname.upper().split()
    
    # Фильтруем: оставляем только заглавные слова длиной > 3
    # (фамилии обычно заглавные и длинные)
    surnames = set()
    for word in words:
        # Убираем слеши и пробелы
        clean_word = word.replace('/', '').strip()
        # Если слово длинное и состоит из букв
        if len(clean_word) > 3 and clean_word.isalpha():
            surnames.add(clean_word)
    
    return surnames

def are_same_pair(lastname1, lastname2):
    """Проверяет, одна ли это пара"""
    surnames1 = extract_surnames_from_pair(lastname1)
    surnames2 = extract_surnames_from_pair(lastname2)
    
    if not surnames1 or not surnames2:
        # Если не смогли извлечь - сравниваем как есть
        return lastname1.upper().strip() == lastname2.upper().strip()
    
    # Если есть хотя бы 2 общие фамилии или 1 общая и обе пары из 1 человека
    common = surnames1 & surnames2
    
    # Для пар обычно 2 фамилии, если обе совпадают - это одна пара
    if len(common) >= 2:
        return True
    
    # Если совпадает хотя бы 1 фамилия и это большая часть
    if len(common) >= 1:
        # Проверяем что это значительная часть (>60%)
        if len(common) / min(len(surnames1), len(surnames2)) > 0.6:
            return True
    
    return False

def create_backup():
    """Создает бэкап БД"""
    print("\n" + "="*100)
    print("СОЗДАНИЕ БЭКАПА")
    print("="*100)
    
    db_path = 'instance/figure_skating.db'
    backup_dir = 'backups'
    
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_filename = f'before_smart_merge_{timestamp}.db'
    backup_path = os.path.join(backup_dir, backup_filename)
    
    try:
        shutil.copy2(db_path, backup_path)
        file_size = os.path.getsize(backup_path) / (1024 * 1024)
        print(f"\nБэкап создан: {backup_path}")
        print(f"Размер: {file_size:.2f} МБ")
        return backup_filename
    except Exception as e:
        print(f"\nОШИБКА: {e}")
        return None

def find_smart_duplicate_groups():
    """Находит дубликаты с умной нормализацией фамилий"""
    
    duplicates = db.session.query(
        Athlete.birth_date,
        func.count(Athlete.id).label('count')
    ).group_by(
        Athlete.birth_date
    ).having(
        func.count(Athlete.id) > 1
    ).all()
    
    all_groups = []
    
    for birth_date, count in duplicates:
        if not birth_date:
            continue
        
        athletes = Athlete.query.filter_by(birth_date=birth_date).all()
        
        # Группируем по похожим фамилиям
        grouped = []
        processed = set()
        
        for i, athlete1 in enumerate(athletes):
            if athlete1.id in processed:
                continue
            
            # Создаем новую группу
            group = [athlete1]
            processed.add(athlete1.id)
            
            # Ищем похожих
            for athlete2 in athletes:
                if athlete2.id in processed:
                    continue
                
                # Проверяем, одна ли это пара/человек
                if are_same_pair(athlete1.last_name or "", athlete2.last_name or ""):
                    group.append(athlete2)
                    processed.add(athlete2.id)
            
            # Если в группе больше 1 - добавляем
            if len(group) > 1:
                # Используем первую фамилию как ключ
                surnames = extract_surnames_from_pair(athlete1.last_name or "")
                key = '/'.join(sorted(surnames)) if surnames else athlete1.last_name
                
                all_groups.append({
                    'birth_date': birth_date,
                    'lastname_normalized': key,
                    'athletes': group
                })
    
    return all_groups

def merge_smart_duplicates():
    """Умное объединение с нормализацией"""
    with app.app_context():
        print("\n" + "="*100)
        print("УМНОЕ ОБЪЕДИНЕНИЕ ДУБЛИКАТОВ (с нормализацией фамилий для пар)")
        print("="*100)
        
        # Находим дубликаты
        groups = find_smart_duplicate_groups()
        
        if not groups:
            print("\nДубликатов не найдено!")
            return
        
        print(f"\nНайдено групп: {len(groups)}")
        
        total_to_remove = sum(len(g['athletes']) - 1 for g in groups)
        total_athletes = Athlete.query.count()
        
        print(f"Будет удалено: {total_to_remove}")
        print(f"Всего спортсменов: {total_athletes}")
        print(f"Останется: {total_athletes - total_to_remove}")
        
        # Показываем примеры
        print("\n" + "-"*100)
        print("ПРИМЕРЫ:")
        print("-"*100)
        
        for i, group in enumerate(groups[:10], 1):
            athletes = group['athletes']
            print(f"\n{i}. {group['birth_date'].strftime('%d.%m.%Y')} | {group['lastname_normalized']} | Дубликатов: {len(athletes)}")
            for athlete in athletes:
                print(f"   ID {athlete.id}: '{athlete.last_name}' -> '{athlete.full_name}'")
        
        if len(groups) > 10:
            print(f"\n   ... и еще {len(groups) - 10} групп")
        
        # Подтверждение
        print("\n" + "="*100)
        confirm = input("\nОбъединить все группы? (yes/NO): ").strip().lower()
        
        if confirm != 'yes':
            print("\nОтменено")
            return
        
        # Бэкап
        backup_file = create_backup()
        if not backup_file:
            print("\nОШИБКА создания бэкапа! Объединение отменено.")
            return
        
        # Объединяем
        print("\n" + "="*100)
        print("ОБЪЕДИНЕНИЕ...")
        print("="*100)
        
        merged_count = 0
        removed_count = 0
        
        for i, group in enumerate(groups, 1):
            print(f"\n[{i}/{len(groups)}] {group['lastname_normalized']}...")
            
            athletes = group['athletes']
            
            # Основной = с более полным ФИО
            main = max(athletes, key=lambda a: (
                len(a.full_name or ""),
                Participant.query.filter_by(athlete_id=a.id).count()
            ))
            
            others = [a for a in athletes if a.id != main.id]
            
            for dup in others:
                # Переносим участия
                participations = Participant.query.filter_by(athlete_id=dup.id).all()
                for p in participations:
                    p.athlete_id = main.id
                    merged_count += 1
                
                # Удаляем дубликат
                db.session.delete(dup)
                removed_count += 1
                
                print(f"   ID {dup.id} -> ID {main.id} (перенесено {len(participations)} участий)")
        
        # Сохраняем
        try:
            db.session.commit()
            print("\n" + "="*100)
            print("УСПЕШНО!")
            print("="*100)
            print(f"\nУдалено дубликатов: {removed_count}")
            print(f"Перенесено участий: {merged_count}")
            print(f"Бэкап: backups/{backup_file}")
            print("\n" + "="*100)
            
        except Exception as e:
            db.session.rollback()
            print(f"\nОШИБКА: {e}")
            print("Все изменения отменены!")

if __name__ == '__main__':
    merge_smart_duplicates()

