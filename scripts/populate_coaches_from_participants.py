#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для заполнения таблиц тренеров из существующих данных участников
Использование: python scripts/populate_coaches_from_participants.py
"""

import os
import sys
from datetime import datetime

# Добавляем текущую директорию в путь
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app import app, db
from models import Coach, CoachAssignment, Participant, Athlete, Event
from services.coach_registry import CoachRegistry
from utils.normalizers import normalize_string, fix_latin_to_cyrillic

def populate_coaches():
    """Заполняет таблицы тренеров из существующих данных участников"""
    with app.app_context():
        print("=" * 80)
        print("ЗАПОЛНЕНИЕ ТАБЛИЦ ТРЕНЕРОВ ИЗ СУЩЕСТВУЮЩИХ ДАННЫХ")
        print("=" * 80)
        print()
        
        coach_registry = CoachRegistry()
        
        # Получаем всех участников с тренерами, отсортированных по дате события
        participants_with_coaches = db.session.query(
            Participant, Athlete, Event
        ).join(
            Athlete, Participant.athlete_id == Athlete.id
        ).join(
            Event, Participant.event_id == Event.id
        ).filter(
            Participant.coach.isnot(None),
            Participant.coach != ''
        ).order_by(
            Event.begin_date.asc(),
            Athlete.id.asc()
        ).all()
        
        print(f"Найдено участников с тренерами: {len(participants_with_coaches)}")
        print()
        
        # Словарь для отслеживания текущих тренеров спортсменов
        athlete_current_coaches = {}  # {athlete_id: (coach_id, event_date)}
        
        processed = 0
        transitions = 0
        
        for participant, athlete, event in participants_with_coaches:
            coach_name = participant.coach.strip()
            if not coach_name:
                continue
            
            # Получаем или создаем тренера
            coach = coach_registry.get_or_create(coach_name)
            if not coach:
                continue
            
            db.session.flush()
            
            # Получаем дату события
            event_date = event.begin_date or event.end_date
            if not event_date:
                continue
            
            athlete_id = athlete.id
            coach_id = coach.id
            
            # Проверяем, есть ли уже назначение для этого спортсмена с этим тренером на это событие
            existing_assignment = CoachAssignment.query.filter_by(
                athlete_id=athlete_id,
                coach_id=coach_id,
                event_id=event.id
            ).first()
            
            if existing_assignment:
                continue  # Уже обработано
            
            # Проверяем текущего тренера спортсмена
            current_coach_info = athlete_current_coaches.get(athlete_id)
            
            if current_coach_info:
                current_coach_id, current_event_date = current_coach_info
                
                # Если тренер изменился - это переход
                if current_coach_id != coach_id:
                    # Закрываем предыдущее назначение
                    previous_assignment = CoachAssignment.query.filter_by(
                        athlete_id=athlete_id,
                        coach_id=current_coach_id,
                        is_current=True
                    ).first()
                    
                    if previous_assignment:
                        previous_assignment.end_date = event_date
                        previous_assignment.is_current = False
                        transitions += 1
                    
                    # Создаем новое назначение
                    new_assignment = CoachAssignment(
                        coach_id=coach_id,
                        athlete_id=athlete_id,
                        participant_id=participant.id,
                        event_id=event.id,
                        start_date=event_date,
                        is_current=True
                    )
                    db.session.add(new_assignment)
                    
                    # Обновляем информацию о текущем тренере
                    athlete_current_coaches[athlete_id] = (coach_id, event_date)
                # Если тренер тот же, но дата раньше - обновляем start_date
                elif event_date < current_event_date:
                    # Находим назначение с более поздней датой и обновляем
                    assignment = CoachAssignment.query.filter_by(
                        athlete_id=athlete_id,
                        coach_id=coach_id,
                        is_current=True
                    ).first()
                    
                    if assignment and assignment.start_date > event_date:
                        assignment.start_date = event_date
                        assignment.participant_id = participant.id
                        assignment.event_id = event.id
                        athlete_current_coaches[athlete_id] = (coach_id, event_date)
            else:
                # Первое назначение тренера для этого спортсмена
                new_assignment = CoachAssignment(
                    coach_id=coach_id,
                    athlete_id=athlete_id,
                    participant_id=participant.id,
                    event_id=event.id,
                    start_date=event_date,
                    is_current=True
                )
                db.session.add(new_assignment)
                athlete_current_coaches[athlete_id] = (coach_id, event_date)
            
            processed += 1
            
            if processed % 100 == 0:
                db.session.commit()
                print(f"Обработано: {processed} участников, переходов: {transitions}")
        
        db.session.commit()
        
        print()
        print("=" * 80)
        print(f"✅ Обработано участников: {processed}")
        print(f"✅ Найдено переходов: {transitions}")
        print(f"✅ Создано тренеров: {Coach.query.count()}")
        print(f"✅ Создано назначений: {CoachAssignment.query.count()}")
        print("=" * 80)

if __name__ == '__main__':
    populate_coaches()
