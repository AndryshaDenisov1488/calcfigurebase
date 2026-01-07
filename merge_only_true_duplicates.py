#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Объединение ТОЛЬКО истинных дубликатов
Игнорирует братьев/сестер (разные имена)
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

def normalize_name(name):
    """Нормализует имя: заменяет ё на е, убирает лишние пробелы"""
    if not name:
        return ""
    # Заменяем ё на е
    normalized = name.lower().replace('ё', 'е').replace('Ё', 'е')
    # Убираем лишние пробелы
    normalized = ' '.join(normalized.split())
    return normalized

def is_name_variant(name1, name2):
    """Проверяет, являются ли два имени вариантами одного имени"""
    if not name1 or not name2:
        return False
    
    # Нормализуем оба имени
    norm1 = normalize_name(name1)
    norm2 = normalize_name(name2)
    
    # Если одно имя полностью содержится в другом - это вариант
    # Например: "василиса" в "василиса кристиан екатерина"
    if norm1 in norm2 or norm2 in norm1:
        return True
    
    # Проверяем схожесть после нормализации
    sim = similarity(norm1, norm2)
    # Для имен достаточно 90% схожести (учитываем опечатки)
    return sim >= 0.90

def is_duplicate_pair(athlete1, athlete2):
    """Определяет, являются ли два спортсмена дубликатами"""
    # Проверяем имена - должны быть вариантами одного имени
    name1 = athlete1.first_name or ""
    name2 = athlete2.first_name or ""
    
    if not is_name_variant(name1, name2):
        return False
    
    # Проверяем полное ФИО
    full1 = normalize_name(athlete1.full_name or "")
    full2 = normalize_name(athlete2.full_name or "")
    
    # Если одно полное ФИО содержится в другом - это дубликат
    # Например: "василиса бурон лебедева" в "василиса кристиан екатерина бурон лебедева"
    if full1 in full2 or full2 in full1:
        return True
    
    # Или очень высокая схожесть полного ФИО
    full_sim = similarity(full1, full2)
    if full_sim >= 0.85:
        return True
    
    return False

def create_backup():
    """Бэкап"""
    db_path = 'instance/figure_skating.db'
    backup_dir = 'backups'
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = f'before_merge_true_duplicates_{timestamp}.db'
    backup_path = os.path.join(backup_dir, backup_file)
    
    shutil.copy2(db_path, backup_path)
    print(f"Бэкап: {backup_path}\n")
    return backup_file

def merge_athlete(keep_id, remove_ids):
    """Объединяет дубликатов в одного"""
    for remove_id in remove_ids:
        # Переносим все участия
        participations = Participant.query.filter_by(athlete_id=remove_id).all()
        for p in participations:
            p.athlete_id = keep_id
        
        # Удаляем дубликат
        athlete_to_remove = Athlete.query.get(remove_id)
        if athlete_to_remove:
            db.session.delete(athlete_to_remove)

def merge_true_duplicates():
    """Объединяет ТОЛЬКО истинные дубликаты (игнорирует братьев/сестер)"""
    with app.app_context():
        print("="*100)
        print("ОБЪЕДИНЕНИЕ ТОЛЬКО ИСТИННЫХ ДУБЛИКАТОВ")
        print("="*100)
        print("Критерий: Дата + Фамилия + вариант одного имени")
        print("  - Нормализует имена (ё→е): 'Алена' и 'Алёна' - одно имя")
        print("  - Одно имя содержится в другом: 'Василиса' в 'Василиса Кристиан Екатерина'")
        print("  - Высокая схожесть полного ФИО (>85%)")
        print("Игнорируются: Братья/сестры (разные имена)")
        print("="*100)
        print()
        
        # Находим группы с дубликатами
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
        
        groups_to_merge = []
        groups_skipped = []
        
        for birth_date, lastname, count in duplicates:
            athletes = Athlete.query.filter_by(
                birth_date=birth_date,
                last_name=lastname
            ).order_by(Athlete.id).all()
            
            # Группируем по схожести имени (улучшенная логика)
            merged_groups = []
            
            for athlete in athletes:
                found_group = False
                
                for group in merged_groups:
                    # Проверяем каждого в группе (не только первого)
                    for existing_athlete in group:
                        if is_duplicate_pair(athlete, existing_athlete):
                            group.append(athlete)
                            found_group = True
                            break
                    
                    if found_group:
                        break
                
                if not found_group:
                    merged_groups.append([athlete])
            
            # Добавляем группы для объединения (только если >1 в группе)
            has_merges = False
            for group in merged_groups:
                if len(group) > 1:
                    groups_to_merge.append({
                        'athletes': group,
                        'birth_date': birth_date,
                        'lastname': lastname
                    })
                    has_merges = True
            
            # Если есть несколько подгрупп И не все были объединены - это братья/сестры
            # Добавляем в пропущенные только один раз
            if len(merged_groups) > 1 and not has_merges:
                # Все подгруппы по одному - это точно братья/сестры
                groups_skipped.append({
                    'athletes': athletes,
                    'birth_date': birth_date,
                    'lastname': lastname,
                    'reason': 'Разные имена (братья/сестры)'
                })
            elif len(merged_groups) > 1 and has_merges:
                # Некоторые объединились, но остались одиночки - показываем только одиночек
                single_athletes = []
                merged_ids = set()
                for group in merged_groups:
                    if len(group) > 1:
                        merged_ids.update(a.id for a in group)
                
                for athlete in athletes:
                    if athlete.id not in merged_ids:
                        single_athletes.append(athlete)
                
                if single_athletes:
                    groups_skipped.append({
                        'athletes': single_athletes,
                        'birth_date': birth_date,
                        'lastname': lastname,
                        'reason': 'Разные имена (братья/сестры, не объединены)'
                    })
        
        # Показываем что будет объединено
        print("БУДЕТ ОБЪЕДИНЕНО:")
        print("="*100)
        
        if not groups_to_merge:
            print("Нет групп для объединения!")
        else:
            for i, group in enumerate(groups_to_merge, 1):
                athletes = group['athletes']
                print(f"\n{i}. {group['lastname']}, {group['birth_date'].strftime('%d.%m.%Y')}:")
                
                # Определяем кого оставить (с наибольшим количеством участий)
                athletes_with_stats = []
                for athlete in athletes:
                    p_count = Participant.query.filter_by(athlete_id=athlete.id).count()
                    athletes_with_stats.append((athlete, p_count))
                
                athletes_with_stats.sort(key=lambda x: x[1], reverse=True)
                keep = athletes_with_stats[0][0]
                remove = [a[0] for a in athletes_with_stats[1:]]
                
                print(f"   ОСТАВИТЬ: ID {keep.id} - {keep.full_name} (пол: {keep.gender}, участий: {athletes_with_stats[0][1]})")
                for athlete, p_count in athletes_with_stats[1:]:
                    print(f"   УДАЛИТЬ:  ID {athlete.id} - {athlete.full_name} (пол: {athlete.gender}, участий: {p_count})")
        
        # Показываем что пропущено
        if groups_skipped:
            print("\n" + "="*100)
            print("ПРОПУЩЕНО (НЕ объединяются):")
            print("="*100)
            
            for i, group in enumerate(groups_skipped, 1):
                athletes = group['athletes']
                print(f"\n{i}. {group['lastname']}, {group['birth_date'].strftime('%d.%m.%Y')} - {group['reason']}:")
                for athlete in athletes:
                    p_count = Participant.query.filter_by(athlete_id=athlete.id).count()
                    print(f"   - ID {athlete.id}: {athlete.first_name} {athlete.last_name} (пол: {athlete.gender}, участий: {p_count})")
        
        # Подтверждение
        print("\n" + "="*100)
        if not groups_to_merge:
            print("Нечего объединять!")
            return
        
        confirm = input(f"\nОбъединить {len(groups_to_merge)} групп дубликатов? (yes/NO): ").strip().lower()
        
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
            
            # Объединяем
            merge_athlete(keep.id, [a.id for a in remove])
            merged_count += 1
            removed_count += len(remove)
        
        # Сохраняем
        try:
            db.session.commit()
            
            print("\n" + "="*100)
            print("УСПЕШНО!")
            print("="*100)
            print(f"Объединено групп: {merged_count}")
            print(f"Удалено дубликатов: {removed_count}")
            print(f"Пропущено (братья/сестры): {len(groups_skipped)}")
            print(f"\nБэкап: backups/{backup_file}")
            print("="*100)
            
        except Exception as e:
            db.session.rollback()
            print(f"\nОШИБКА: {e}")
            print("Изменения отменены!")

if __name__ == '__main__':
    merge_true_duplicates()







