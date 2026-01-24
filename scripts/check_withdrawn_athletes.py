#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка спортсменов, которые снимались с турниров
Показывает для каждого спортсмена количество снятий и список турниров, с которых он снимался
"""

import os
import sys
from collections import defaultdict
from datetime import datetime

# Добавляем текущую директорию в путь
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app import app, db
from models import Athlete, Participant, Event, Category, Club


def check_withdrawn_athletes():
    """Проверяет спортсменов, которые снимались с турниров"""
    
    with app.app_context():
        print("=" * 80)
        print("АНАЛИЗ СПОРТСМЕНОВ, СНИМАВШИХСЯ С ТУРНИРОВ")
        print("=" * 80)
        print()
        
        # Получаем всех участников со статусом 'R' (Retired/Reserved) или 'W' (Withdrawn)
        withdrawn_participants = db.session.query(
            Participant,
            Athlete,
            Event,
            Category,
            Club
        ).join(
            Athlete, Participant.athlete_id == Athlete.id
        ).join(
            Event, Participant.event_id == Event.id
        ).join(
            Category, Participant.category_id == Category.id
        ).outerjoin(
            Club, Athlete.club_id == Club.id
        ).filter(
            Participant.status.in_(['R', 'W'])
        ).order_by(
            Event.begin_date.desc(),
            Athlete.last_name,
            Athlete.first_name
        ).all()
        
        if not withdrawn_participants:
            print("✅ Нет спортсменов, которые снимались с турниров!")
            return 0
        
        # Группируем по спортсменам
        athletes_withdrawals = defaultdict(list)
        
        for participant, athlete, event, category, club in withdrawn_participants:
            athlete_id = athlete.id
            athletes_withdrawals[athlete_id].append({
                'athlete': athlete,
                'club': club,
                'event': event,
                'category': category,
                'participant': participant,
                'status': participant.status
            })
        
        # Сортируем спортсменов по количеству снятий (от большего к меньшему)
        sorted_athletes = sorted(
            athletes_withdrawals.items(),
            key=lambda x: len(x[1]),
            reverse=True
        )
        
        total_athletes = len(sorted_athletes)
        total_withdrawals = len(withdrawn_participants)
        
        print(f"📊 Всего спортсменов, которые снимались: {total_athletes}")
        print(f"📊 Всего случаев снятия: {total_withdrawals}")
        print()
        print("=" * 80)
        print("ДЕТАЛЬНАЯ ИНФОРМАЦИЯ ПО КАЖДОМУ СПОРТСМЕНУ:")
        print("=" * 80)
        print()
        
        for athlete_id, withdrawals in sorted_athletes:
            athlete = withdrawals[0]['athlete']
            club = withdrawals[0]['club']
            withdrawal_count = len(withdrawals)
            
            # Получаем полное имя спортсмена
            athlete_name = athlete.full_name if hasattr(athlete, 'full_name') else (
                athlete.full_name_xml or f"{athlete.last_name} {athlete.first_name}"
            )
            
            club_name = club.name if club else "Не указан"
            birth_date = athlete.birth_date.strftime('%d.%m.%Y') if athlete.birth_date else "Не указана"
            
            print(f"🏃 {athlete_name}")
            print(f"   ID спортсмена: {athlete_id}")
            print(f"   Дата рождения: {birth_date}")
            print(f"   Клуб: {club_name}")
            print(f"   Количество снятий: {withdrawal_count}")
            print()
            print("   📋 Список турниров, с которых снимался:")
            
            # Сортируем снятия по дате турнира (от новых к старым)
            withdrawals_sorted = sorted(
                withdrawals,
                key=lambda x: x['event'].begin_date if x['event'].begin_date else datetime.min,
                reverse=True
            )
            
            for idx, withdrawal in enumerate(withdrawals_sorted, 1):
                event = withdrawal['event']
                category = withdrawal['category']
                participant = withdrawal['participant']
                status = withdrawal['status']
                
                event_date = event.begin_date.strftime('%d.%m.%Y') if event.begin_date else "Дата не указана"
                event_name = event.name or "Название не указано"
                category_name = category.name if category else "Категория не указана"
                status_label = "R (Retired/Reserved)" if status == 'R' else "W (Withdrawn)"
                
                print(f"   {idx}. {event_name}")
                print(f"      Дата: {event_date}")
                print(f"      Категория: {category_name}")
                print(f"      Статус: {status_label}")
                if participant.total_place:
                    print(f"      Место до снятия: {participant.total_place}")
                if participant.total_points:
                    print(f"      Баллы до снятия: {participant.total_points}")
                print()
            
            print("-" * 80)
            print()
        
        # Статистика
        print("=" * 80)
        print("СТАТИСТИКА:")
        print("=" * 80)
        print()
        
        # Распределение по количеству снятий
        withdrawal_counts = defaultdict(int)
        for athlete_id, withdrawals in sorted_athletes:
            count = len(withdrawals)
            withdrawal_counts[count] += 1
        
        print("Распределение по количеству снятий:")
        for count in sorted(withdrawal_counts.keys(), reverse=True):
            athletes_count = withdrawal_counts[count]
            print(f"  {count} снятие(ий): {athletes_count} спортсмен(ов)")
        print()
        
        # Распределение по статусам
        status_counts = defaultdict(int)
        for participant, athlete, event, category, club in withdrawn_participants:
            status_counts[participant.status] += 1
        
        print("Распределение по статусам:")
        for status in sorted(status_counts.keys()):
            status_label = "R (Retired/Reserved)" if status == 'R' else "W (Withdrawn)" if status == 'W' else status
            count = status_counts[status]
            print(f"  {status_label}: {count} случаев")
        print()
        
        # Топ-10 спортсменов по количеству снятий
        print("Топ-10 спортсменов по количеству снятий:")
        for idx, (athlete_id, withdrawals) in enumerate(sorted_athletes[:10], 1):
            athlete = withdrawals[0]['athlete']
            athlete_name = athlete.full_name if hasattr(athlete, 'full_name') else (
                athlete.full_name_xml or f"{athlete.last_name} {athlete.first_name}"
            )
            print(f"  {idx}. {athlete_name}: {len(withdrawals)} снятий")
        print()
        
        print("=" * 80)
        print("ИТОГИ:")
        print("=" * 80)
        print(f"Всего спортсменов, которые снимались: {total_athletes}")
        print(f"Всего случаев снятия: {total_withdrawals}")
        if total_athletes > 0:
            avg_withdrawals = total_withdrawals / total_athletes
            print(f"Среднее количество снятий на спортсмена: {avg_withdrawals:.2f}")
        print("=" * 80)
        
        return 0


def main():
    """Основная функция"""
    try:
        return check_withdrawn_athletes()
    except Exception as e:
        print(f"❌ Ошибка: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
