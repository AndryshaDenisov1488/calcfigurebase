#!/usr/bin/env python3
"""
Небольшой скрипт для проверки спортсменов без стартов.

Пример запуска на сервере:

    cd /var/www/calc.figurebase.ru
    source venv/bin/activate
    python check_athletes_without_starts.py
"""

from __future__ import annotations

import os
import sys

# Добавляем текущую директорию в путь
if __name__ == '__main__':
    project_root = os.path.dirname(os.path.abspath(__file__))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

from app import app, db
from models import Athlete, Participant


def check_athletes_without_starts():
    """Показывает спортсменов, у которых нет стартов в таблице participants."""
    
    with app.app_context():
        print("=" * 72)
        print("ПРОВЕРКА СПОРТСМЕНОВ БЕЗ СТАРТОВ")
        print("=" * 72)
        print()
        
        # Получаем всех спортсменов
        all_athletes = Athlete.query.all()
        
        # Находим спортсменов без участий
        athletes_without_starts = []
        
        for athlete in all_athletes:
            participations_count = Participant.query.filter_by(athlete_id=athlete.id).count()
            if participations_count == 0:
                athletes_without_starts.append(athlete)
        
        total_count = len(all_athletes)
        without_starts_count = len(athletes_without_starts)
        
        print(f"Всего спортсменов в базе: {total_count}")
        print(f"Спортсменов без стартов: {without_starts_count}")
        print()
        
        if without_starts_count == 0:
            print("✅ Все спортсмены имеют хотя бы одно участие!")
            return 0
        
        print("-" * 72)
        print(f"{'ID':<6} | {'ФИО':<40} | {'Дата создания'}")
        print("-" * 72)
        
        # Сортируем по ID (по убыванию - последние добавленные)
        athletes_without_starts.sort(key=lambda a: a.id, reverse=True)
        
        for athlete in athletes_without_starts:
            full_name = athlete.full_name or "(без имени)"
            # Урезаем длинные имена
            if len(full_name) > 40:
                full_name = full_name[:37] + "..."
            
            # Проверяем есть ли поле created_at в модели
            created_display = "-"
            # В модели Athlete нет поля created_at, поэтому показываем "-"
            
            print(f"{athlete.id:<6} | {full_name:<40} | {created_display}")
        
        print("-" * 72)
        print()
        print(f"💡 Найдено {without_starts_count} спортсменов без участий в турнирах.")
        print("   Это могут быть:")
        print("   • Ошибочно добавленные записи")
        print("   • Спортсмены, данные о которых были удалены, но записи остались")
        print("   • Тестовые записи")
        print()
        print("   Вы можете удалить эти записи вручную через SQL или создать скрипт очистки.")
        
        return 0


def main():
    """Основная функция"""
    try:
        return check_athletes_without_starts()
    except Exception as e:
        print(f"❌ Ошибка: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

