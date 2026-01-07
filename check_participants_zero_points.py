#!/usr/bin/env python3
"""
Скрипт для проверки участников с нулевыми или null баллами.

Пример запуска на сервере:

    cd /var/www/calc.figurebase.ru
    source venv/bin/activate
    python check_participants_zero_points.py
"""

import os
import sys

# Добавляем текущую директорию в путь
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app import app, db
from models import Participant, Athlete, Event, Category


def check_participants_zero_points():
    """Проверяет участников с нулевыми или null баллами"""
    
    with app.app_context():
        print("=" * 80)
        print("ПРОВЕРКА УЧАСТНИКОВ С НУЛЕВЫМИ ИЛИ NULL БАЛЛАМИ")
        print("=" * 80)
        print()
        
        # Находим участников с null баллами
        participants_null = Participant.query.filter(
            Participant.total_points.is_(None)
        ).all()
        
        # Находим участников с нулевыми баллами
        participants_zero = Participant.query.filter(
            Participant.total_points == 0.0
        ).all()
        
        # Общая статистика
        total_participants = Participant.query.count()
        null_count = len(participants_null)
        zero_count = len(participants_zero)
        
        print(f"📊 СТАТИСТИКА:")
        print(f"   Всего участников в базе: {total_participants}")
        print(f"   Участников с NULL баллами: {null_count}")
        print(f"   Участников с нулевыми баллами (0.0): {zero_count}")
        print(f"   Всего проблемных: {null_count + zero_count}")
        print()
        
        if null_count == 0 and zero_count == 0:
            print("✅ Все участники имеют баллы!")
            return 0
        
        # Группируем по турнирам
        all_problematic = list(participants_null) + list(participants_zero)
        by_event = {}
        
        for p in all_problematic:
            event = Event.query.get(p.event_id) if p.event_id else None
            category = Category.query.get(p.category_id) if p.category_id else None
            
            if not event:
                event_name = "Неизвестный турнир"
            else:
                event_name = event.name
                event_date = event.begin_date.strftime('%d.%m.%Y') if event.begin_date else 'нет даты'
                event_name = f"{event_name} ({event_date})"
            
            if event_name not in by_event:
                by_event[event_name] = []
            
            athlete = Athlete.query.get(p.athlete_id) if p.athlete_id else None
            athlete_name = athlete.full_name if athlete else f"ID {p.athlete_id}"
            
            by_event[event_name].append({
                'participant_id': p.id,
                'athlete_id': p.athlete_id,
                'athlete_name': athlete_name,
                'category_name': category.name if category else "Неизвестная категория",
                'place': p.total_place,
                'points': p.total_points,
                'status': p.status,
                'is_free': p.pct_ppname == 'БЕСП'
            })
        
        # Выводим результаты
        print("=" * 80)
        print("СПИСОК УЧАСТНИКОВ С ПРОБЛЕМАМИ:")
        print("=" * 80)
        print()
        
        event_num = 0
        for event_name, participants in sorted(by_event.items()):
            event_num += 1
            print(f"{'─' * 80}")
            print(f"#{event_num}. {event_name}")
            print(f"   Участников с проблемами: {len(participants)}")
            print(f"{'─' * 80}")
            
            for i, p in enumerate(participants, 1):
                points_display = "NULL" if p['points'] is None else "0.0"
                free_marker = " [БЕСП]" if p['is_free'] else ""
                
                print(f"\n   {i}. ID участника: {p['participant_id']}")
                print(f"      Спортсмен: {p['athlete_name']} (ID: {p['athlete_id']})")
                print(f"      Категория: {p['category_name']}")
                print(f"      Место: {p['place'] if p['place'] is not None else 'не указано'}")
                print(f"      Баллы: {points_display}")
                print(f"      Статус: {p['status'] if p['status'] else 'не указан'}{free_marker}")
            
            print()
        
        # Итоги
        print("=" * 80)
        print("ИТОГИ:")
        print("=" * 80)
        print(f"Всего турниров с проблемами: {len(by_event)}")
        print(f"Всего участников с NULL баллами: {null_count}")
        print(f"Всего участников с нулевыми баллами: {zero_count}")
        print()
        print("💡 ВОЗМОЖНЫЕ ПРИЧИНЫ:")
        print("   • Участник не завершил соревнование")
        print("   • Данные не были импортированы из XML")
        print("   • Ошибка при импорте данных")
        print("   • Участник был дисквалифицирован")
        print()
        print("📝 РЕКОМЕНДАЦИИ:")
        print("   • Проверьте XML файлы соответствующих турниров")
        print("   • При необходимости переимпортируйте турниры через reimport_event_from_xml.py")
        print("   • Или проверьте данные вручную в базе данных")
        print("=" * 80)
        
        return 0


def main():
    """Основная функция"""
    try:
        return check_participants_zero_points()
    except Exception as e:
        print(f"❌ Ошибка: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

