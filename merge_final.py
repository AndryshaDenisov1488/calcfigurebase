#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Финальное объединение дубликатов
Критерий: Дата рождения + похожее полное ФИО (>80% совпадение, без учета пробелов)
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
    # Убираем лишние пробелы и приводим к нижнему регистру
    a_clean = ' '.join(a.lower().split())
    b_clean = ' '.join(b.lower().split())
    return SequenceMatcher(None, a_clean, b_clean).ratio()

def create_backup():
    """Бэкап"""
    db_path = 'instance/figure_skating.db'
    backup_dir = 'backups'
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = f'before_final_merge_{timestamp}.db'
    backup_path = os.path.join(backup_dir, backup_file)
    
    shutil.copy2(db_path, backup_path)
    print(f"Бэкап: {backup_path}")
    return backup_file

def merge_all():
    """Объединяет всех"""
    with app.app_context():
        print("="*100)
        print("ФИНАЛЬНОЕ ОБЪЕДИНЕНИЕ ДУБЛИКАТОВ")
        print("="*100)
        print("Критерий: Дата рождения + ФИО совпадает >80%\n")
        
        # Находим даты с дубликатами
        duplicates = db.session.query(
            Athlete.birth_date,
            func.count(Athlete.id).label('count')
        ).group_by(Athlete.birth_date).having(
            func.count(Athlete.id) > 1
        ).all()
        
        all_groups = []
        
        for birth_date, count in duplicates:
            if not birth_date:
                continue
            
            athletes = Athlete.query.filter_by(birth_date=birth_date).all()
            
            # Группируем по похожему ФИО
            processed = set()
            
            for i, athlete1 in enumerate(athletes):
                if athlete1.id in processed:
                    continue
                
                group = [athlete1]
                processed.add(athlete1.id)
                
                # Ищем похожих
                for athlete2 in athletes:
                    if athlete2.id in processed:
                        continue
                    
                    # Сравниваем полное ФИО
                    sim = similarity(athlete1.full_name or "", athlete2.full_name or "")
                    
                    if sim > 0.80:  # 80% совпадение
                        group.append(athlete2)
                        processed.add(athlete2.id)
                
                if len(group) > 1:
                    all_groups.append(group)
        
        print(f"Найдено групп: {len(all_groups)}")
        print(f"Будет удалено записей: {sum(len(g)-1 for g in all_groups)}\n")
        
        # Показываем примеры
        print("-"*100)
        print("ПРИМЕРЫ (первые 10):")
        print("-"*100)
        
        for i, group in enumerate(all_groups[:10], 1):
            athlete1 = group[0]
            print(f"\n{i}. {athlete1.birth_date.strftime('%d.%m.%Y')} | Дубликатов: {len(group)}")
            for athlete in group:
                p_count = Participant.query.filter_by(athlete_id=athlete.id).count()
                print(f"   ID {athlete.id}: {athlete.full_name} (участий: {p_count})")
        
        if len(all_groups) > 10:
            print(f"\n   ... и еще {len(all_groups) - 10} групп")
        
        # Подтверждение
        print("\n" + "="*100)
        confirm = input("Объединить? (yes/NO): ").strip().lower()
        
        if confirm != 'yes':
            print("Отменено")
            return
        
        # Бэкап
        backup = create_backup()
        
        # Объединяем
        print("\n" + "="*100)
        print("ОБЪЕДИНЕНИЕ...")
        print("="*100)
        
        merged = 0
        removed = 0
        
        for i, group in enumerate(all_groups, 1):
            # Основной = с длинным ФИО
            main = max(group, key=lambda a: (
                len(a.full_name or ""),
                Participant.query.filter_by(athlete_id=a.id).count()
            ))
            
            others = [a for a in group if a.id != main.id]
            
            for dup in others:
                # Переносим участия
                for p in Participant.query.filter_by(athlete_id=dup.id).all():
                    p.athlete_id = main.id
                    merged += 1
                
                # Удаляем
                db.session.delete(dup)
                removed += 1
            
            if i % 5 == 0:
                print(f"  Обработано {i}/{len(all_groups)}...")
        
        # Сохраняем
        db.session.commit()
        
        print("\n" + "="*100)
        print("ГОТОВО!")
        print("="*100)
        print(f"Удалено: {removed}")
        print(f"Перенесено участий: {merged}")
        print(f"Бэкап: backups/{backup}")
        print("="*100)

if __name__ == '__main__':
    merge_all()

