#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Обновление пола для пар и танцев: M/F → P (Пара)
"""

from app import app, db
from models import Athlete
import os
import shutil
from datetime import datetime

def create_backup():
    """Создаем бэкап базы данных перед изменениями"""
    db_path = 'instance/figure_skating.db'
    backup_dir = 'backups'
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = f'before_pairs_gender_update_{timestamp}.db'
    backup_path = os.path.join(backup_dir, backup_file)
    
    shutil.copy2(db_path, backup_path)
    print(f"Бэкап создан: {backup_path}\n")
    return backup_file

def update_pairs_gender():
    """Обновляет пол для всех пар и танцев"""
    with app.app_context():
        print("="*100)
        print("ОБНОВЛЕНИЕ ПОЛА ДЛЯ ПАР И ТАНЦЕВ")
        print("="*100)
        print()
        
        # Ищем всех спортсменов, у которых в фамилии есть "/" (пары)
        # Это признак пары: "Иванов/Петрова", "VASILIEVA/SIDOROV" и т.д.
        pairs = Athlete.query.filter(
            Athlete.last_name.like('%/%')
        ).all()
        
        print(f"Найдено пар/танцев по признаку '/' в фамилии: {len(pairs)}\n")
        
        # Показываем первые 10 для проверки
        print("Примеры (первые 10):")
        for i, athlete in enumerate(pairs[:10], 1):
            print(f"  {i}. ID {athlete.id}: {athlete.full_name} (пол: {athlete.gender})")
        
        if len(pairs) > 10:
            print(f"  ... и еще {len(pairs) - 10} пар")
        print()
        
        # Подтверждение
        print("="*100)
        confirm = input(f"Обновить пол на 'P' для {len(pairs)} пар/танцев? (yes/NO): ").strip().lower()
        
        if confirm != 'yes':
            print("Отменено")
            return
        
        # Создаем бэкап
        backup_file = create_backup()
        
        # Обновляем
        print("="*100)
        print("ОБНОВЛЕНИЕ...")
        print("="*100)
        
        updated_count = 0
        gender_stats = {'M': 0, 'F': 0, 'P': 0, None: 0}
        
        for athlete in pairs:
            old_gender = athlete.gender
            athlete.gender = 'P'
            
            if old_gender:
                gender_stats[old_gender] = gender_stats.get(old_gender, 0) + 1
            else:
                gender_stats[None] += 1
            
            updated_count += 1
        
        # Сохраняем изменения
        try:
            db.session.commit()
            
            print()
            print("="*100)
            print("УСПЕШНО!")
            print("="*100)
            print(f"Обновлено: {updated_count} спортсменов")
            print()
            print("Статистика по старому полу:")
            print(f"  М (мужчины):  {gender_stats.get('M', 0)}")
            print(f"  Ж (женщины):  {gender_stats.get('F', 0)}")
            print(f"  P (уже пара): {gender_stats.get('P', 0)}")
            print(f"  NULL:         {gender_stats.get(None, 0)}")
            print()
            print(f"Теперь все {updated_count} имеют пол 'P' (Пара)")
            print()
            print(f"Бэкап: backups/{backup_file}")
            print("="*100)
            
        except Exception as e:
            db.session.rollback()
            print(f"\nОШИБКА: {e}")
            print("Изменения отменены!")

if __name__ == '__main__':
    update_pairs_gender()

