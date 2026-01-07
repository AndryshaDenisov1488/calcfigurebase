#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка клубов/школ без спортсменов
Находит школы где 0 спортсменов - такие можно удалить
"""

import os
import sys

# Добавляем текущую директорию в путь
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app import app, db
from models import Club, Athlete, Participant


def check_clubs_zero_athletes():
    """Проверяет клубы без спортсменов"""
    
    with app.app_context():
        print("=" * 80)
        print("ПРОВЕРКА ШКОЛ/КЛУБОВ БЕЗ СПОРТСМЕНОВ")
        print("=" * 80)
        print()
        
        # Получаем все клубы
        all_clubs = Club.query.all()
        total_clubs = len(all_clubs)
        
        print(f"📊 Всего клубов в базе: {total_clubs}")
        print()
        
        # Находим клубы без спортсменов
        clubs_with_zero = []
        
        for club in all_clubs:
            athletes_count = Athlete.query.filter_by(club_id=club.id).count()
            
            if athletes_count == 0:
                clubs_with_zero.append(club)
        
        if not clubs_with_zero:
            print("✅ Все клубы имеют хотя бы одного спортсмена!")
            print("   Нет клубов для удаления.")
            return 0
        
        # Сортируем по ID
        clubs_with_zero.sort(key=lambda x: x.id)
        
        print(f"⚠️  Найдено клубов без спортсменов: {len(clubs_with_zero)}")
        print()
        print("=" * 80)
        print("СПИСОК КЛУБОВ БЕЗ СПОРТСМЕНОВ:")
        print("=" * 80)
        print()
        
        for club in clubs_with_zero:
            external_id = club.external_id if club.external_id else "нет"
            print(f"  ID {club.id}: '{club.name}'")
            print(f"    External ID: {external_id}")
            print()
        
        # Итоги
        print("=" * 80)
        print("ИТОГИ:")
        print("=" * 80)
        print(f"Всего клубов без спортсменов: {len(clubs_with_zero)}")
        print()
        print("💡 РЕКОМЕНДАЦИИ:")
        print("  • Эти клубы можно безопасно удалить из базы")
        print("  • Используйте скрипт delete_clubs_zero_athletes.py для удаления")
        print("=" * 80)
        
        return 0


def main():
    """Основная функция"""
    try:
        return check_clubs_zero_athletes()
    except Exception as e:
        print(f"❌ Ошибка: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())

