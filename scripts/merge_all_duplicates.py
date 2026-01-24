#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для автоматического объединения всех дубликатов
ВНИМАНИЕ: Перед запуском автоматически создается бэкап БД!
"""

from app import app, db
from models import Athlete, Participant, Event, Club
from sqlalchemy import func
from datetime import datetime
import os
import shutil

def create_backup():
    """Создает бэкап БД перед объединением"""
    print("\n" + "="*100)
    print("СОЗДАНИЕ БЭКАПА БАЗЫ ДАННЫХ")
    print("="*100)
    
    db_path = 'instance/figure_skating.db'
    backup_dir = 'backups'
    
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_filename = f'before_merge_{timestamp}.db'
    backup_path = os.path.join(backup_dir, backup_filename)
    
    try:
        shutil.copy2(db_path, backup_path)
        file_size = os.path.getsize(backup_path) / (1024 * 1024)
        print(f"\nБэкап создан: {backup_path}")
        print(f"Размер: {file_size:.2f} МБ")
        print("\nВ случае проблем можно восстановить из этого бэкапа!")
        return True
    except Exception as e:
        print(f"\nОШИБКА создания бэкапа: {e}")
        print("ОБЪЕДИНЕНИЕ ОТМЕНЕНО!")
        return False

def find_duplicate_groups():
    """Находит группы дубликатов"""
    duplicates = db.session.query(
        Athlete.birth_date,
        func.count(Athlete.id).label('count')
    ).group_by(
        Athlete.birth_date
    ).having(
        func.count(Athlete.id) > 1
    ).order_by(
        Athlete.birth_date.desc()
    ).all()
    
    all_groups = []
    
    for birth_date, count in duplicates:
        if not birth_date:
            continue
        
        athletes = Athlete.query.filter_by(birth_date=birth_date).all()
        
        # Группируем по фамилиям
        by_lastname = {}
        for athlete in athletes:
            lastname = (athlete.last_name or "").strip().upper()
            if not lastname:
                continue
            
            if lastname not in by_lastname:
                by_lastname[lastname] = []
            by_lastname[lastname].append(athlete)
        
        # Добавляем группы где больше 1
        for lastname, group in by_lastname.items():
            if len(group) > 1:
                all_groups.append({
                    'birth_date': birth_date,
                    'lastname': lastname,
                    'athletes': group
                })
    
    return all_groups

def merge_duplicate_group(athletes):
    """Объединяет группу дубликатов в одну запись"""
    
    # Выбираем основного (с более полным ФИО и большим количеством участий)
    main_athlete = max(athletes, key=lambda a: (
        len(a.full_name or ""),
        Participant.query.filter_by(athlete_id=a.id).count()
    ))
    
    duplicates = [a for a in athletes if a.id != main_athlete.id]
    
    merged_participations = 0
    
    for duplicate in duplicates:
        # Переносим все участия на основного
        participations = Participant.query.filter_by(athlete_id=duplicate.id).all()
        
        for participation in participations:
            participation.athlete_id = main_athlete.id
            merged_participations += 1
        
        # Удаляем дубликат
        db.session.delete(duplicate)
    
    return {
        'main_id': main_athlete.id,
        'main_name': main_athlete.full_name,
        'removed_ids': [d.id for d in duplicates],
        'merged_participations': merged_participations
    }

def merge_all_duplicates(auto_confirm=False):
    """Объединяет все найденные дубликаты"""
    with app.app_context():
        print("\n" + "="*100)
        print("АВТОМАТИЧЕСКОЕ ОБЪЕДИНЕНИЕ ДУБЛИКАТОВ")
        print("="*100)
        
        # Находим дубликаты
        groups = find_duplicate_groups()
        
        if not groups:
            print("\nДубликатов не найдено!")
            return
        
        print(f"\nНайдено групп для объединения: {len(groups)}")
        
        total_to_remove = sum(len(g['athletes']) - 1 for g in groups)
        total_athletes = Athlete.query.count()
        
        print(f"Будет удалено записей: {total_to_remove}")
        print(f"Всего спортсменов: {total_athletes}")
        print(f"Останется после чистки: {total_athletes - total_to_remove}")
        
        # Показываем первые 5 групп для примера
        print("\n" + "-"*100)
        print("ПРИМЕРЫ (первые 5 групп):")
        print("-"*100)
        
        for i, group in enumerate(groups[:5], 1):
            athletes = group['athletes']
            print(f"\n{i}. {group['birth_date'].strftime('%d.%m.%Y')} | {group['lastname']}")
            for athlete in athletes:
                participations = Participant.query.filter_by(athlete_id=athlete.id).count()
                print(f"   ID {athlete.id}: {athlete.full_name} (участий: {participations})")
        
        if len(groups) > 5:
            print(f"\n   ... и еще {len(groups) - 5} групп")
        
        # Подтверждение
        if not auto_confirm:
            print("\n" + "="*100)
            print("ВНИМАНИЕ! Будет выполнено:")
            print("  1. Создание бэкапа БД")
            print("  2. Объединение всех дубликатов")
            print("  3. Удаление лишних записей")
            print("="*100)
            
            confirm = input("\nПродолжить? (yes/NO): ").strip().lower()
            
            if confirm != 'yes':
                print("\nОперация отменена пользователем")
                return
        
        # Создаем бэкап
        if not create_backup():
            return
        
        # Объединяем
        print("\n" + "="*100)
        print("НАЧАЛО ОБЪЕДИНЕНИЯ")
        print("="*100)
        
        results = []
        
        for i, group in enumerate(groups, 1):
            print(f"\n[{i}/{len(groups)}] Обработка: {group['lastname']} ({group['birth_date'].strftime('%d.%m.%Y')})")
            
            try:
                result = merge_duplicate_group(group['athletes'])
                results.append(result)
                
                print(f"   OK: Основной ID {result['main_id']}, удалено {len(result['removed_ids'])}, перенесено {result['merged_participations']} участий")
                
            except Exception as e:
                print(f"   ОШИБКА: {e}")
                db.session.rollback()
                print("   Откат изменений для этой группы")
        
        # Сохраняем изменения
        try:
            print("\n" + "="*100)
            print("СОХРАНЕНИЕ ИЗМЕНЕНИЙ В БАЗУ ДАННЫХ...")
            print("="*100)
            
            db.session.commit()
            
            print("\nУСПЕШНО!")
            
        except Exception as e:
            print(f"\nОШИБКА при сохранении: {e}")
            db.session.rollback()
            print("ВСЕ ИЗМЕНЕНИЯ ОТМЕНЕНЫ!")
            return
        
        # Отчет
        print("\n" + "="*100)
        print("ОТЧЕТ О ПРОДЕЛАННОЙ РАБОТЕ")
        print("="*100)
        
        total_removed = sum(len(r['removed_ids']) for r in results)
        total_merged = sum(r['merged_participations'] for r in results)
        
        print(f"\nОбработано групп: {len(results)}")
        print(f"Удалено дубликатов: {total_removed}")
        print(f"Перенесено участий: {total_merged}")
        print(f"\nСпортсменов было: {total_athletes}")
        print(f"Спортсменов стало: {Athlete.query.count()}")
        print(f"Освобождено записей: {total_athletes - Athlete.query.count()}")
        
        print("\n" + "="*100)
        print("ПРИМЕРЫ ОБЪЕДИНЕННЫХ СПОРТСМЕНОВ:")
        print("="*100)
        
        for i, result in enumerate(results[:10], 1):
            athlete = Athlete.query.get(result['main_id'])
            if athlete:
                participations = Participant.query.filter_by(athlete_id=athlete.id).count()
                free_count = Participant.query.filter_by(athlete_id=athlete.id, pct_ppname='БЕСП').count()
                
                print(f"\n{i}. ID {result['main_id']}: {result['main_name']}")
                print(f"   Удалены: {', '.join([f'ID {x}' for x in result['removed_ids']])}")
                print(f"   Итого участий: {participations} (бесплатных: {free_count})")
        
        if len(results) > 10:
            print(f"\n   ... и еще {len(results) - 10} групп")
        
        print("\n" + "="*100)
        print("ГОТОВО! Все дубликаты объединены!")
        print("="*100)
        print(f"\nБэкап сохранен в: backups/before_merge_{timestamp}.db")
        print("В случае проблем можно восстановить!")
        print("="*100)

if __name__ == '__main__':
    import sys
    
    # Проверяем флаг --auto для автоматического режима
    auto = '--auto' in sys.argv or '--yes' in sys.argv
    
    merge_all_duplicates(auto_confirm=auto)

