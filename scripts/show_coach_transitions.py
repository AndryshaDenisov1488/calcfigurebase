#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для отображения переходов спортсменов между тренерами
Использование: python scripts/show_coach_transitions.py
"""

import os
import sys
from datetime import datetime
from collections import defaultdict

# Добавляем текущую директорию в путь
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app import app, db
from models import Athlete, Coach, CoachAssignment, Event, Participant

def show_coach_transitions():
    """Показывает все переходы спортсменов между тренерами"""
    with app.app_context():
        print("=" * 100)
        print("ПЕРЕХОДЫ СПОРТСМЕНОВ МЕЖДУ ТРЕНЕРАМИ")
        print("=" * 100)
        print()
        
        # Получаем все назначения, отсортированные по спортсмену и дате
        all_assignments = db.session.query(
            CoachAssignment, Athlete, Coach, Event
        ).join(
            Athlete, CoachAssignment.athlete_id == Athlete.id
        ).join(
            Coach, CoachAssignment.coach_id == Coach.id
        ).outerjoin(
            Event, CoachAssignment.event_id == Event.id
        ).order_by(
            Athlete.id,
            CoachAssignment.start_date.asc()
        ).all()
        
        if not all_assignments:
            print("❌ Переходов не найдено. Возможно, данные о тренерах еще не были импортированы.")
            return
        
        # Группируем по спортсменам
        athlete_transitions = defaultdict(list)
        for assignment, athlete, coach, event in all_assignments:
            athlete_transitions[athlete.id].append({
                'assignment': assignment,
                'athlete': athlete,
                'coach': coach,
                'event': event
            })
        
        # Сортируем спортсменов по количеству переходов (больше переходов - выше)
        athletes_with_transitions = []
        for athlete_id, transitions in athlete_transitions.items():
            if len(transitions) > 1:  # Только те, у кого был хотя бы один переход
                athletes_with_transitions.append((athlete_id, transitions))
        
        athletes_with_transitions.sort(key=lambda x: len(x[1]), reverse=True)
        
        if not athletes_with_transitions:
            print("✅ Переходов между тренерами не найдено.")
            print("   Все спортсмены работают с одним тренером.")
            return
        
        print(f"📊 Найдено спортсменов с переходами: {len(athletes_with_transitions)}")
        print()
        
        # Выводим информацию о переходах
        for athlete_id, transitions in athletes_with_transitions:
            athlete = transitions[0]['athlete']
            print(f"{'=' * 100}")
            print(f"👤 СПОРТСМЕН: {athlete.full_name}")
            print(f"   ID: {athlete.id}")
            if athlete.birth_date:
                print(f"   Дата рождения: {athlete.birth_date.strftime('%d.%m.%Y')}")
            print()
            
            # Сортируем переходы по дате
            transitions_sorted = sorted(transitions, key=lambda x: x['assignment'].start_date or datetime.min)
            
            for i, transition in enumerate(transitions_sorted):
                assignment = transition['assignment']
                coach = transition['coach']
                event = transition['event']
                
                status = "✅ Текущий" if assignment.is_current else "❌ Завершено"
                start_date = assignment.start_date.strftime('%d.%m.%Y') if assignment.start_date else "неизвестно"
                end_date = assignment.end_date.strftime('%d.%m.%Y') if assignment.end_date else "-"
                
                event_name = event.name if event else "неизвестно"
                
                print(f"   {i+1}. Тренер: {coach.name}")
                print(f"      Статус: {status}")
                print(f"      Период: с {start_date} по {end_date}")
                print(f"      Турнир: {event_name}")
                
                # Показываем переход, если есть следующий
                if i < len(transitions_sorted) - 1:
                    next_coach = transitions_sorted[i+1]['coach']
                    next_start = transitions_sorted[i+1]['assignment'].start_date
                    next_start_str = next_start.strftime('%d.%m.%Y') if next_start else "неизвестно"
                    print(f"      ➡️  Перешел к тренеру: {next_coach.name} ({next_start_str})")
                
                print()
            
            print()
        
        # Статистика
        print("=" * 100)
        print("📈 СТАТИСТИКА")
        print("=" * 100)
        
        total_transitions = sum(len(transitions) - 1 for _, transitions in athletes_with_transitions)
        print(f"Всего переходов: {total_transitions}")
        print(f"Спортсменов с переходами: {len(athletes_with_transitions)}")
        
        # Топ спортсменов по количеству переходов
        print()
        print("🏆 Топ-10 спортсменов по количеству переходов:")
        top_athletes = sorted(athletes_with_transitions, key=lambda x: len(x[1]), reverse=True)[:10]
        for i, (athlete_id, transitions) in enumerate(top_athletes, 1):
            athlete = transitions[0]['athlete']
            print(f"   {i}. {athlete.full_name} - {len(transitions) - 1} переходов")
        
        # Статистика по тренерам (кто больше всего теряет/получает спортсменов)
        print()
        print("📊 Статистика по тренерам:")
        
        coach_stats = defaultdict(lambda: {'gained': 0, 'lost': 0})
        
        for athlete_id, transitions in athletes_with_transitions:
            transitions_sorted = sorted(transitions, key=lambda x: x['assignment'].start_date or datetime.min)
            
            for i, transition in enumerate(transitions_sorted):
                coach = transition['coach']
                
                # Если это не первое назначение - тренер получил спортсмена
                if i > 0:
                    coach_stats[coach.name]['gained'] += 1
                
                # Если есть следующее назначение - тренер потерял спортсмена
                if i < len(transitions_sorted) - 1:
                    coach_stats[coach.name]['lost'] += 1
        
        # Сортируем по общему количеству переходов
        coach_stats_sorted = sorted(
            coach_stats.items(),
            key=lambda x: x[1]['gained'] + x[1]['lost'],
            reverse=True
        )[:10]
        
        for coach_name, stats in coach_stats_sorted:
            print(f"   {coach_name}:")
            print(f"      Получил спортсменов: {stats['gained']}")
            print(f"      Потерял спортсменов: {stats['lost']}")
        
        print()
        print("=" * 100)

if __name__ == '__main__':
    show_coach_transitions()
