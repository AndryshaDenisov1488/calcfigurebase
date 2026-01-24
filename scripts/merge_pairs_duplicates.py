#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Объединение дубликатов ПАР с разными форматами записи фамилий
Критерий: Дата рождения + Полное ФИО >95%
"""

from app import app, db
from models import Athlete, Participant
from sqlalchemy import func
from datetime import datetime
from difflib import SequenceMatcher
import os
import shutil

def similarity(a, b):
    """Схожесть строк"""
    if not a or not b:
        return 0.0
    a_clean = ' '.join(a.lower().split())
    b_clean = ' '.join(b.lower().split())
    return SequenceMatcher(None, a_clean, b_clean).ratio()

def create_backup():
    """Бэкап"""
    db_path = 'instance/figure_skating.db'
    backup_dir = 'backups'
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = f'before_merge_pairs_{timestamp}.db'
    backup_path = os.path.join(backup_dir, backup_file)
    
    shutil.copy2(db_path, backup_path)
    print(f"Бэкап: {backup_path}\n")
    return backup_file

def merge_pairs():
    """Объединяет дубликаты пар"""
    with app.app_context():
        print("="*100)
        print("ОБЪЕДИНЕНИЕ ДУБЛИКАТОВ ПАР")
        print("="*100)
        print("Критерий: Дата рождения + Полное ФИО >95%")
        print("Для пар с разными форматами фамилий (КРЕМЕР/ЦЕЛКОВСКИЙ vs Алиса КРЕМЕР / Илья)")
        print("="*100)
        print()
        
        # Находим всех пар (по "/" в фамилии)
        all_pairs = Athlete.query.filter(
            Athlete.last_name.like('%/%')
        ).all()
        
        print(f"Всего пар в БД: {len(all_pairs)}\n")
        
        # Группируем по дате рождения
        pairs_by_date = {}
        for pair in all_pairs:
            if pair.birth_date:
                date_key = pair.birth_date
                if date_key not in pairs_by_date:
                    pairs_by_date[date_key] = []
                pairs_by_date[date_key].append(pair)
        
        # Находим дубликатов
        groups_to_merge = []
        
        for birth_date, pairs in pairs_by_date.items():
            if len(pairs) < 2:
                continue
            
            # Группируем по схожести полного ФИО
            merged_groups = []
            
            for pair in pairs:
                found_group = False
                
                for group in merged_groups:
                    # Сравниваем полное ФИО с первым в группе
                    first_in_group = group[0]
                    full_name_sim = similarity(
                        pair.full_name or '', 
                        first_in_group.full_name or ''
                    )
                    
                    # Если полное ФИО схоже >95% - это дубликат
                    if full_name_sim > 0.95:
                        group.append(pair)
                        found_group = True
                        break
                
                if not found_group:
                    merged_groups.append([pair])
            
            # Добавляем только группы с дубликатами
            for group in merged_groups:
                if len(group) > 1:
                    groups_to_merge.append({
                        'athletes': group,
                        'birth_date': birth_date
                    })
        
        # Показываем что будет объединено
        print("БУДЕТ ОБЪЕДИНЕНО:")
        print("="*100)
        
        if not groups_to_merge:
            print("Дубликатов пар не найдено!")
            return
        
        for i, group in enumerate(groups_to_merge, 1):
            athletes = group['athletes']
            
            print(f"\n{i}. {athletes[0].full_name}")
            print(f"   Дата рождения: {group['birth_date'].strftime('%d.%m.%Y')}")
            print(f"   Найдено записей: {len(athletes)}")
            
            # Определяем кого оставить (с наибольшим количеством участий)
            athletes_with_stats = []
            for athlete in athletes:
                p_count = Participant.query.filter_by(athlete_id=athlete.id).count()
                athletes_with_stats.append((athlete, p_count))
            
            athletes_with_stats.sort(key=lambda x: x[1], reverse=True)
            keep = athletes_with_stats[0][0]
            
            print(f"\n   ОСТАВИТЬ: ID {keep.id}")
            print(f"     last_name: {keep.last_name}")
            print(f"     first_name: {keep.first_name}")
            print(f"     Пол: {keep.gender}")
            print(f"     Участий: {athletes_with_stats[0][1]}")
            
            for athlete, p_count in athletes_with_stats[1:]:
                print(f"\n   УДАЛИТЬ: ID {athlete.id}")
                print(f"     last_name: {athlete.last_name}")
                print(f"     first_name: {athlete.first_name}")
                print(f"     Пол: {athlete.gender}")
                print(f"     Участий: {p_count}")
        
        # Подтверждение
        print("\n" + "="*100)
        confirm = input(f"\nОбъединить {len(groups_to_merge)} пар? (yes/NO): ").strip().lower()
        
        if confirm != 'yes':
            print("Отменено")
            return
        
        # Создаем бэкап
        backup_file = create_backup()
        
        # Объединяем
        print("Объединение...")
        merged_count = 0
        removed_count = 0
        
        for group in groups_to_merge:
            athletes = group['athletes']
            
            # Определяем кого оставить
            athletes_with_stats = []
            for athlete in athletes:
                p_count = Participant.query.filter_by(athlete_id=athlete.id).count()
                athletes_with_stats.append((athlete, p_count))
            
            athletes_with_stats.sort(key=lambda x: x[1], reverse=True)
            keep = athletes_with_stats[0][0]
            remove = [a[0] for a in athletes_with_stats[1:]]
            
            # Переносим участия
            for remove_athlete in remove:
                participations = Participant.query.filter_by(athlete_id=remove_athlete.id).all()
                for p in participations:
                    p.athlete_id = keep.id
                
                # Удаляем дубликат
                db.session.delete(remove_athlete)
                removed_count += 1
            
            merged_count += 1
        
        # Сохраняем
        try:
            db.session.commit()
            
            print("\n" + "="*100)
            print("УСПЕШНО!")
            print("="*100)
            print(f"Объединено пар: {merged_count}")
            print(f"Удалено дубликатов: {removed_count}")
            print(f"\nБэкап: backups/{backup_file}")
            print("="*100)
            
        except Exception as e:
            db.session.rollback()
            print(f"\nОШИБКА: {e}")
            print("Изменения отменены!")

if __name__ == '__main__':
    merge_pairs()







