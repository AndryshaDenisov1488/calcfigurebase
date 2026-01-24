#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Повторный импорт турнира из XML с обновлением данных
"""

from app import app, db
from models import Event, Category, Participant, Performance, Segment, Athlete, Club
from parsers.isu_calcfs_parser import ISUCalcFSParser
from services.import_service import save_to_database
import os
import shutil
from datetime import datetime
import sys

def create_backup():
    """Создаем бэкап"""
    db_path = 'instance/figure_skating.db'
    backup_dir = 'backups'
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = f'before_reimport_{timestamp}.db'
    backup_path = os.path.join(backup_dir, backup_file)
    
    shutil.copy2(db_path, backup_path)
    print(f"Бэкап создан: {backup_path}\n")
    return backup_file

def reimport_event(xml_path, event_name_pattern):
    """Повторно импортирует турнир из XML"""
    with app.app_context():
        print("="*100)
        print("ПОВТОРНЫЙ ИМПОРТ ТУРНИРА ИЗ XML")
        print("="*100)
        
        # 1. Проверяем XML файл
        if not os.path.exists(xml_path):
            print(f"\nОшибка: XML файл не найден: {xml_path}")
            return
        
        print(f"\nXML файл: {xml_path}")
        
        # 2. Парсим XML
        print("Парсинг XML...")
        parser = ISUCalcFSParser(xml_path)
        parser.parse()
        
        # 3. Находим турнир в XML
        xml_event = None
        for event in parser.events:
            if event_name_pattern.lower() in event['name'].lower():
                xml_event = event
                break
        
        if not xml_event:
            print(f"\nТурнир '{event_name_pattern}' не найден в XML!")
            print("Доступные турниры в XML:")
            for event in parser.events:
                print(f"  - {event['name']}")
            return
        
        print(f"\nТурнир в XML: {xml_event['name']}")
        
        # 4. Находим турнир в БД
        db_event = Event.query.filter(Event.name.like(f"%{event_name_pattern}%")).first()
        
        if not db_event:
            print(f"\nТурнир '{event_name_pattern}' не найден в БД!")
            print("Используйте обычный импорт через /upload")
            return
        
        print(f"Турнир в БД: ID {db_event.id} - {db_event.name}")
        
        # 5. Показываем статистику
        categories = Category.query.filter_by(event_id=db_event.id).all()
        participants_total = 0
        for cat in categories:
            participants_total += Participant.query.filter_by(category_id=cat.id).count()
        
        print(f"\nТекущие данные в БД:")
        print(f"  Категорий: {len(categories)}")
        print(f"  Участников: {participants_total}")
        
        # Проверяем участников БЕЗ результатов
        participants_no_results = db.session.query(Participant).join(
            Category, Participant.category_id == Category.id
        ).filter(
            Category.event_id == db_event.id,
            Participant.total_place.is_(None),
            Participant.total_points.is_(None)
        ).count()
        
        print(f"  Участников БЕЗ результатов (место/баллы): {participants_no_results}")
        
        # 6. Подтверждение
        print("\n" + "="*100)
        print("ЧТО БУДЕТ СДЕЛАНО:")
        print("  1. Удалены ВСЕ данные турнира (категории, участия, выступления)")
        print("  2. Импортированы НОВЫЕ данные из XML")
        print("  3. Спортсмены и клубы НЕ будут удалены (только переиспользованы)")
        print("="*100)
        
        confirm = input("\nПродолжить? (yes/NO): ").strip().lower()
        
        if confirm != 'yes':
            print("Отменено")
            return
        
        # Создаем бэкап
        backup_file = create_backup()
        
        print("\nУдаление старых данных турнира...")
        
        # Удаляем турнир (cascade удалит категории, участия, выступления)
        db.session.delete(db_event)
        db.session.commit()
        
        print("Импорт новых данных из XML...")
        
        # Импортируем турнир заново
        try:
            save_to_database(parser)
            print("\n" + "="*100)
            print("УСПЕШНО ОБНОВЛЕНО!")
            print("="*100)
            print(f"Турнир: {xml_event['name']}")
            print(f"Категорий: {len(parser.categories)}")
            print(f"Участников: {len(parser.participants)}")
            print(f"\nБэкап: backups/{backup_file}")
            print("="*100)
        except Exception as e:
            print(f"\nОШИБКА: {e}")
            print("Восстановите из бэкапа!")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Использование:")
        print("  python reimport_event_from_xml.py <путь_к_xml> [название_турнира]")
        print()
        print("Пример:")
        print("  python reimport_event_from_xml.py /path/to/event.xml \"Рабер\"")
        sys.exit(1)
    
    xml_path = sys.argv[1]
    event_name = sys.argv[2] if len(sys.argv) > 2 else input("Введите название турнира: ").strip()
    
    reimport_event(xml_path, event_name)

