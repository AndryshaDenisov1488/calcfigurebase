#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Объединение дубликатов по ФИО с исправлением даты рождения
"""

from app import app, db
from models import Athlete, Participant
from datetime import datetime, date
import os
import shutil

def create_backup():
    """Бэкап"""
    db_path = 'instance/figure_skating.db'
    backup_dir = 'backups'
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = f'before_fix_dates_{timestamp}.db'
    backup_path = os.path.join(backup_dir, backup_file)
    
    shutil.copy2(db_path, backup_path)
    print(f"Бэкап создан: {backup_path}\n")
    return backup_file

def fix_and_merge():
    """Исправляет даты и объединяет"""
    with app.app_context():
        print("="*100)
        print("ОБЪЕДИНЕНИЕ С ИСПРАВЛЕНИЕМ ДАТ РОЖДЕНИЯ")
        print("="*100)
        
        # Список для исправления (из вашего сообщения)
        fixes = [
            {
                'name': 'Александра Филипповна МАЛЮТИНА',
                'correct_date': date(2017, 8, 11),
                'wrong_date': date(2017, 12, 24)
            },
            {
                'name': 'Анна Николаевна КАЛИНИНА',
                'correct_date': date(2017, 6, 22),
                'wrong_date': date(2017, 6, 27)
            },
            {
                'name': 'Мария Андреевна ШУРАВИНА',
                'correct_date': date(2018, 12, 4),
                'wrong_date': date(2018, 6, 7)
            },
            {
                'name': 'София Дмитриевна ЗАНЧЕВА',
                'correct_date': date(2018, 8, 8),
                'wrong_date': date(2018, 9, 8)
            }
        ]
        
        print(f"\nСпортсменов для исправления: {len(fixes)}\n")
        
        # Показываем что будет сделано
        for i, fix in enumerate(fixes, 1):
            print(f"{i}. {fix['name']}")
            
            # Ищем спортсменов
            athletes = Athlete.query.filter(
                db.or_(
                    Athlete.birth_date == fix['correct_date'],
                    Athlete.birth_date == fix['wrong_date']
                )
            ).filter(
                db.or_(
                    Athlete.full_name_xml.like(f"%{fix['name']}%"),
                    db.and_(
                        Athlete.first_name.in_(fix['name'].split()[0:1]),
                        Athlete.last_name.in_(fix['name'].split()[-1:])
                    )
                )
            ).all()
            
            # Фильтруем по точному совпадению ФИО
            athletes = [a for a in athletes if fix['name'].lower() in (a.full_name or "").lower()]
            
            if len(athletes) == 0:
                print(f"   НЕ НАЙДЕНО!")
            elif len(athletes) == 1:
                print(f"   Только 1 запись - дубликатов нет")
            else:
                print(f"   Найдено записей: {len(athletes)}")
                for athlete in athletes:
                    p_count = Participant.query.filter_by(athlete_id=athlete.id).count()
                    print(f"      ID {athlete.id}: {athlete.birth_date.strftime('%d.%m.%Y')} ({p_count} участий)")
                
                # Определяем правильную и неправильную
                correct_athlete = next((a for a in athletes if a.birth_date == fix['correct_date']), None)
                wrong_athletes = [a for a in athletes if a.birth_date == fix['wrong_date']]
                
                if correct_athlete and wrong_athletes:
                    total_to_merge = sum(Participant.query.filter_by(athlete_id=a.id).count() for a in wrong_athletes)
                    print(f"   ПЛАН:")
                    print(f"      Основной: ID {correct_athlete.id} (дата {fix['correct_date'].strftime('%d.%m.%Y')})")
                    print(f"      Удалить: {', '.join([f'ID {a.id}' for a in wrong_athletes])}")
                    print(f"      Перенести: {total_to_merge} участий")
                elif not correct_athlete and wrong_athletes:
                    print(f"   ПЛАН: Исправить дату у ID {wrong_athletes[0].id}")
                    if len(wrong_athletes) > 1:
                        print(f"         И объединить с ID {', '.join([f'{a.id}' for a in wrong_athletes[1:]])}")
            
            print()
        
        # Подтверждение
        print("="*100)
        confirm = input("Выполнить объединение и исправление дат? (yes/NO): ").strip().lower()
        
        if confirm != 'yes':
            print("Отменено")
            return
        
        # Бэкап
        backup_file = create_backup()
        
        # Выполняем исправления
        print("="*100)
        print("ВЫПОЛНЕНИЕ...")
        print("="*100)
        
        merged_total = 0
        removed_total = 0
        
        for i, fix in enumerate(fixes, 1):
            print(f"\n[{i}/{len(fixes)}] {fix['name']}...")
            
            # Ищем спортсменов
            athletes = Athlete.query.filter(
                db.or_(
                    Athlete.birth_date == fix['correct_date'],
                    Athlete.birth_date == fix['wrong_date']
                )
            ).all()
            
            # Фильтруем по ФИО
            athletes = [a for a in athletes if fix['name'].lower() in (a.full_name or "").lower()]
            
            if len(athletes) <= 1:
                print(f"   Пропущено (дубликатов нет)")
                continue
            
            # Находим правильного и неправильных
            correct_athlete = next((a for a in athletes if a.birth_date == fix['correct_date']), None)
            wrong_athletes = [a for a in athletes if a.birth_date == fix['wrong_date']]
            
            if not correct_athlete and wrong_athletes:
                # Нет правильного - берем первого и исправляем дату
                correct_athlete = wrong_athletes[0]
                correct_athlete.birth_date = fix['correct_date']
                print(f"   Исправлена дата у ID {correct_athlete.id}: {fix['wrong_date'].strftime('%d.%m.%Y')} -> {fix['correct_date'].strftime('%d.%m.%Y')}")
                wrong_athletes = wrong_athletes[1:]
            
            if correct_athlete and wrong_athletes:
                # Переносим участия
                for wrong_athlete in wrong_athletes:
                    participations = Participant.query.filter_by(athlete_id=wrong_athlete.id).all()
                    
                    for p in participations:
                        p.athlete_id = correct_athlete.id
                        merged_total += 1
                    
                    print(f"   ID {wrong_athlete.id} -> ID {correct_athlete.id} (перенесено {len(participations)} участий)")
                    
                    # Удаляем неправильного
                    db.session.delete(wrong_athlete)
                    removed_total += 1
        
        # Сохраняем
        try:
            db.session.commit()
            
            print("\n" + "="*100)
            print("УСПЕШНО!")
            print("="*100)
            print(f"Удалено дубликатов: {removed_total}")
            print(f"Перенесено участий: {merged_total}")
            print(f"Исправлено дат: {len(fixes)}")
            print(f"\nБэкап: backups/{backup_file}")
            print("="*100)
            
        except Exception as e:
            db.session.rollback()
            print(f"\nОШИБКА: {e}")
            print("Изменения отменены!")

if __name__ == '__main__':
    fix_and_merge()

