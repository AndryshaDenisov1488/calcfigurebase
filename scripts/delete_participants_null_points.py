#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Удаление участий с NULL баллами (снятые с турнира)

Эти участники были зарегистрированы, но сняты/не участвовали,
и парсер еще не умеет их автоматически пропускать.
"""

import os
import sys
from datetime import datetime
import shutil

# Добавляем текущую директорию в путь
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app import app, db
from models import Participant, Athlete, Event, Category


def create_backup():
    """Создаем бэкап базы данных"""
    db_path = 'instance/figure_skating.db'
    backup_dir = 'backups'
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = f'before_delete_null_points_{timestamp}.db'
    backup_path = os.path.join(backup_dir, backup_file)
    
    shutil.copy2(db_path, backup_path)
    print(f"✅ Бэкап создан: {backup_path}\n")
    return backup_file


def delete_null_points_participants():
    """Удаляет все участия с NULL баллами"""
    
    with app.app_context():
        print("=" * 80)
        print("УДАЛЕНИЕ УЧАСТИЙ С NULL БАЛЛАМИ")
        print("=" * 80)
        print()
        print("Эти участники были зарегистрированы, но сняты/не участвовали.")
        print("Парсер пока не умеет их автоматически пропускать.")
        print()
        
        # Находим все участия с NULL баллами
        participants_to_delete = Participant.query.filter(
            Participant.total_points.is_(None)
        ).all()
        
        total_count = len(participants_to_delete)
        
        if total_count == 0:
            print("✅ Участий с NULL баллами не найдено!")
            return 0
        
        # Группируем по турнирам для показа
        by_event = {}
        
        for p in participants_to_delete:
            event = Event.query.get(p.event_id) if p.event_id else None
            category = Category.query.get(p.category_id) if p.category_id else None
            athlete = Athlete.query.get(p.athlete_id) if p.athlete_id else None
            
            if not event:
                event_name = "Неизвестный турнир"
            else:
                event_name = event.name
                event_date = event.begin_date.strftime('%d.%m.%Y') if event.begin_date else 'нет даты'
                event_name = f"{event_name} ({event_date})"
            
            if event_name not in by_event:
                by_event[event_name] = []
            
            athlete_name = athlete.full_name if athlete else f"ID {p.athlete_id}"
            
            by_event[event_name].append({
                'participant_id': p.id,
                'athlete_name': athlete_name,
                'category_name': category.name if category else "Неизвестная категория",
                'is_free': p.pct_ppname == 'БЕСП'
            })
        
        # Показываем что будет удалено
        print("=" * 80)
        print(f"НАЙДЕНО УЧАСТИЙ С NULL БАЛЛАМИ: {total_count}")
        print("=" * 80)
        print()
        
        event_num = 0
        for event_name, participants in sorted(by_event.items()):
            event_num += 1
            print(f"{'─' * 80}")
            print(f"#{event_num}. {event_name}")
            print(f"   Участников к удалению: {len(participants)}")
            
            # Показываем первые 5, остальные обобщенно
            for i, p in enumerate(participants[:5], 1):
                free_marker = " [БЕСП]" if p['is_free'] else ""
                print(f"   {i}. {p['athlete_name']} - {p['category_name']}{free_marker}")
            
            if len(participants) > 5:
                print(f"   ... и еще {len(participants) - 5} участников")
            print()
        
        # Подтверждение
        print("=" * 80)
        print("ВНИМАНИЕ!")
        print("=" * 80)
        print(f"Будет удалено {total_count} участий с NULL баллами.")
        print("Эти участники были сняты с турниров или не участвовали.")
        print()
        print("Будет создан бэкап базы данных перед удалением.")
        print("=" * 80)
        
        confirm = input(f"\nУдалить {total_count} участий? (yes/NO): ").strip().lower()
        
        if confirm != 'yes':
            print("❌ Отменено")
            return 0
        
        # Создаем бэкап
        print("\nСоздание бэкапа...")
        backup_file = create_backup()
        
        # Удаляем участия
        print(f"\nУдаление {total_count} участий...")
        
        deleted_count = 0
        deleted_by_event = {}
        
        for p in participants_to_delete:
            event = Event.query.get(p.event_id) if p.event_id else None
            event_name = event.name if event else "Неизвестный турнир"
            
            # Подсчитываем по турнирам
            if event_name not in deleted_by_event:
                deleted_by_event[event_name] = 0
            deleted_by_event[event_name] += 1
            
            # Удаляем участие (cascade удалит связанные Performance)
            db.session.delete(p)
            deleted_count += 1
        
        # Сохраняем изменения
        try:
            db.session.commit()
            
            print("\n" + "=" * 80)
            print("✅ УСПЕШНО УДАЛЕНО!")
            print("=" * 80)
            print(f"Удалено участий: {deleted_count}")
            print(f"Затронуто турниров: {len(deleted_by_event)}")
            print()
            print("Удалено по турнирам:")
            for event_name, count in sorted(deleted_by_event.items()):
                print(f"  • {event_name}: {count} участников")
            print()
            print(f"📦 Бэкап: backups/{backup_file}")
            print("=" * 80)
            
            return 0
            
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ ОШИБКА: {e}")
            print("Изменения отменены!")
            import traceback
            traceback.print_exc()
            return 1


def main():
    """Основная функция"""
    try:
        return delete_null_points_participants()
    except Exception as e:
        print(f"❌ Ошибка: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())

