#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Удаление турнира по названию для повторного импорта
"""

from app import app, db
from models import Event, Category, Participant, Performance, Segment
import os
import shutil
from datetime import datetime

def create_backup():
    """Создаем бэкап"""
    db_path = 'instance/figure_skating.db'
    backup_dir = 'backups'
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = f'before_delete_event_{timestamp}.db'
    backup_path = os.path.join(backup_dir, backup_file)
    
    shutil.copy2(db_path, backup_path)
    print(f"Бэкап создан: {backup_path}\n")
    return backup_file

def delete_event_by_name(event_name):
    """Удаляет турнир и все связанные данные"""
    with app.app_context():
        print("="*100)
        print("УДАЛЕНИЕ ТУРНИРА ДЛЯ ПОВТОРНОГО ИМПОРТА")
        print("="*100)
        
        # Ищем турнир
        events = Event.query.filter(Event.name.like(f'%{event_name}%')).all()
        
        if not events:
            print(f"\nТурнир '{event_name}' не найден!")
            return
        
        if len(events) > 1:
            print(f"\nНайдено несколько турниров:")
            for i, evt in enumerate(events, 1):
                print(f"  {i}. ID {evt.id}: {evt.name} ({evt.begin_date})")
            
            choice = input("\nВведите номер турнира для удаления (или 'all' для всех): ").strip()
            
            if choice.lower() == 'all':
                events_to_delete = events
            else:
                try:
                    idx = int(choice) - 1
                    events_to_delete = [events[idx]]
                except:
                    print("Неверный выбор!")
                    return
        else:
            events_to_delete = events
        
        # Показываем что будет удалено
        print("\n" + "="*100)
        print("БУДЕТ УДАЛЕНО:")
        print("="*100)
        
        total_categories = 0
        total_participants = 0
        total_performances = 0
        
        for event in events_to_delete:
            categories = Category.query.filter_by(event_id=event.id).all()
            participants_count = 0
            performances_count = 0
            
            for cat in categories:
                parts = Participant.query.filter_by(category_id=cat.id).all()
                participants_count += len(parts)
                
                for part in parts:
                    perfs = Performance.query.filter_by(participant_id=part.id).count()
                    performances_count += perfs
            
            print(f"\nТурнир ID {event.id}: {event.name}")
            print(f"  Дата: {event.begin_date} - {event.end_date}")
            print(f"  Категорий: {len(categories)}")
            print(f"  Участников: {participants_count}")
            print(f"  Выступлений: {performances_count}")
            
            total_categories += len(categories)
            total_participants += participants_count
            total_performances += performances_count
        
        print("\n" + "="*100)
        print(f"ИТОГО будет удалено:")
        print(f"  Турниров: {len(events_to_delete)}")
        print(f"  Категорий: {total_categories}")
        print(f"  Участников: {total_participants}")
        print(f"  Выступлений: {total_performances}")
        print("="*100)
        
        # Подтверждение
        confirm = input("\nУдалить? После этого импортируйте полный XML заново! (yes/NO): ").strip().lower()
        
        if confirm != 'yes':
            print("Отменено")
            return
        
        # Создаем бэкап
        backup_file = create_backup()
        
        # Удаляем
        print("\nУдаление...")
        
        for event in events_to_delete:
            # SQLAlchemy автоматически удалит связанные данные благодаря cascade
            db.session.delete(event)
        
        try:
            db.session.commit()
            
            print("\n" + "="*100)
            print("УСПЕШНО УДАЛЕНО!")
            print("="*100)
            print(f"Турниров: {len(events_to_delete)}")
            print(f"\nБэкап: backups/{backup_file}")
            print("\n" + "="*100)
            print("ТЕПЕРЬ ИМПОРТИРУЙТЕ ПОЛНЫЙ XML ЧЕРЕЗ ВЕБ-ИНТЕРФЕЙС:")
            print("  https://calc.figurebase.ru/upload")
            print("="*100)
            
        except Exception as e:
            db.session.rollback()
            print(f"\nОШИБКА: {e}")
            print("Изменения отменены!")

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        event_name = ' '.join(sys.argv[1:])
    else:
        event_name = input("Введите название турнира (или часть названия): ").strip()
    
    if event_name:
        delete_event_by_name(event_name)
    else:
        print("Название турнира не указано!")

