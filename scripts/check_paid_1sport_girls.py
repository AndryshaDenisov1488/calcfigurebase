#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для поиска спортсменов с платными участиями в разряде "1 Спортивный, Девочки".

Пример запуска:
    cd /path/to/project
    source venv/bin/activate
    python scripts/check_paid_1sport_girls.py
"""

import os
import sys

# Добавляем текущую директорию в путь
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app import app, db
from models import Participant, Athlete, Event, Category, Club


def check_paid_1sport_girls():
    """Находит спортсменов с платными участиями в разряде '1 Спортивный, Девочки'"""
    
    with app.app_context():
        print("=" * 80)
        print("ПОИСК СПОРТСМЕНОВ С ПЛАТНЫМИ УЧАСТИЯМИ В РАЗРЯДЕ '1 Спортивный, Девочки'")
        print("=" * 80)
        print()
        
        # Ищем всех участников с разрядом "1 Спортивный, Девочки" и платным участием
        participants_query = db.session.query(
            Participant.id.label('participant_id'),
            Participant.athlete_id,
            Participant.pct_ppname,
            Participant.total_place,
            Participant.total_points,
            Participant.event_id,
            Athlete.id,
            Athlete.first_name,
            Athlete.last_name,
            Athlete.full_name_xml,
            Athlete.birth_date,
            Athlete.gender,
            Club.name.label('club_name'),
            Category.normalized_name.label('rank'),
            Category.name.label('category_name'),
            Event.name.label('event_name'),
            Event.begin_date.label('event_date')
        ).join(
            Athlete, Participant.athlete_id == Athlete.id
        ).join(
            Category, Participant.category_id == Category.id
        ).join(
            Event, Participant.event_id == Event.id
        ).outerjoin(
            Club, Athlete.club_id == Club.id
        ).filter(
            Category.normalized_name == '1 Спортивный, Девочки'
        ).filter(
            db.or_(
                Participant.pct_ppname.is_(None),
                Participant.pct_ppname != 'БЕСП'
            )
        ).all()
        
        if not participants_query:
            print("✅ Не найдено платных участий в разряде '1 Спортивный, Девочки'")
            return 0
        
        # Группируем по спортсменам
        athletes_dict = {}
        
        for row in participants_query:
            athlete_id = row.athlete_id
            
            if athlete_id not in athletes_dict:
                full_name = row.full_name_xml or f"{row.last_name} {row.first_name}"
                athletes_dict[athlete_id] = {
                    'athlete_id': athlete_id,
                    'name': full_name,
                    'first_name': row.first_name,
                    'last_name': row.last_name,
                    'birth_date': row.birth_date.strftime('%d.%m.%Y') if row.birth_date else 'Не указана',
                    'gender': 'Ж' if row.gender == 'F' else 'М' if row.gender == 'M' else 'Пара' if row.gender == 'P' else '-',
                    'club': row.club_name or 'Не указан',
                    'participations': []
                }
            
            # Добавляем информацию об участии
            event_date_str = row.event_date.strftime('%d.%m.%Y') if row.event_date else 'нет даты'
            athletes_dict[athlete_id]['participations'].append({
                'participant_id': row.participant_id,
                'event_name': row.event_name,
                'event_date': event_date_str,
                'event_id': row.event_id,
                'category_name': row.category_name,
                'place': row.total_place,
                'points': row.total_points,
                'pct_ppname': row.pct_ppname,
                'status': 'ПЛАТНОЕ' if row.pct_ppname != 'БЕСП' else 'БЕСПЛАТНОЕ'
            })
        
        # Выводим результаты
        print(f"📊 НАЙДЕНО СПОРТСМЕНОВ С ПЛАТНЫМИ УЧАСТИЯМИ: {len(athletes_dict)}")
        print()
        print("=" * 80)
        print("ДЕТАЛЬНАЯ ИНФОРМАЦИЯ:")
        print("=" * 80)
        print()
        
        for idx, (athlete_id, athlete_data) in enumerate(athletes_dict.items(), 1):
            print(f"{'─' * 80}")
            print(f"#{idx}. СПОРТСМЕН")
            print(f"{'─' * 80}")
            print(f"   ID: {athlete_id}")
            print(f"   ФИО: {athlete_data['name']}")
            print(f"   Дата рождения: {athlete_data['birth_date']}")
            print(f"   Пол: {athlete_data['gender']}")
            print(f"   Клуб: {athlete_data['club']}")
            print(f"   Количество платных участий: {len(athlete_data['participations'])}")
            print()
            
            print(f"   УЧАСТИЯ:")
            for part_idx, participation in enumerate(athlete_data['participations'], 1):
                print(f"      {part_idx}. {participation['event_name']} ({participation['event_date']})")
                print(f"         ID участия: {participation['participant_id']}")
                print(f"         ID турнира: {participation['event_id']}")
                print(f"         Категория: {participation['category_name']}")
                print(f"         Место: {participation['place'] if participation['place'] is not None else 'не указано'}")
                print(f"         Баллы: {participation['points'] if participation['points'] is not None else 'не указано'}")
                print(f"         Статус оплаты: {participation['pct_ppname']} ({participation['status']})")
                print()
            
            print()
        
        # Итоговая статистика
        total_participations = sum(len(a['participations']) for a in athletes_dict.values())
        
        print("=" * 80)
        print("ИТОГОВАЯ СТАТИСТИКА:")
        print("=" * 80)
        print(f"   Всего спортсменов с платными участиями: {len(athletes_dict)}")
        print(f"   Всего платных участий: {total_participations}")
        print()
        
        # Проверяем, есть ли у этих спортсменов также бесплатные участия в этом разряде
        print("=" * 80)
        print("ПРОВЕРКА НАЛИЧИЯ БЕСПЛАТНЫХ УЧАСТИЙ У ЭТИХ СПОРТСМЕНОВ:")
        print("=" * 80)
        print()
        
        for athlete_id, athlete_data in athletes_dict.items():
            # Ищем бесплатные участия этого спортсмена в том же разряде
            free_participations = db.session.query(
                Participant.id,
                Event.name.label('event_name'),
                Event.begin_date.label('event_date')
            ).join(
                Category, Participant.category_id == Category.id
            ).join(
                Event, Participant.event_id == Event.id
            ).filter(
                Participant.athlete_id == athlete_id,
                Category.normalized_name == '1 Спортивный, Девочки',
                Participant.pct_ppname == 'БЕСП'
            ).all()
            
            if free_participations:
                print(f"   {athlete_data['name']} (ID: {athlete_id}):")
                print(f"      Платных участий: {len(athlete_data['participations'])}")
                print(f"      Бесплатных участий: {len(free_participations)}")
                for free_part in free_participations:
                    event_date_str = free_part.event_date.strftime('%d.%m.%Y') if free_part.event_date else 'нет даты'
                    print(f"         - {free_part.event_name} ({event_date_str})")
                print()
        
        print("=" * 80)
        print("💡 ВОЗМОЖНЫЕ ПРИЧИНЫ:")
        print("   • Ошибка при импорте данных (неправильно указан статус оплаты)")
        print("   • Данные были изменены вручную")
        print("   • Особый случай участия (например, вне конкурса)")
        print("=" * 80)
        
        return 0


def main():
    """Основная функция"""
    try:
        return check_paid_1sport_girls()
    except Exception as e:
        print(f"❌ Ошибка: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

