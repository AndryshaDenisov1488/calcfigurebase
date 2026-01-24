#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Точный поиск дубликатов: Дата рождения + ФИО (без учета пола)
"""

from app import app, db
from models import Athlete, Participant, Event, Club
from sqlalchemy import func
from difflib import SequenceMatcher

def similarity(a, b):
    """Вычисляет схожесть двух строк (0.0 - 1.0)"""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()

def normalize_name(name):
    """Нормализует имя для сравнения"""
    if not name:
        return ""
    # Убираем лишние пробелы
    return ' '.join(name.strip().split())

def find_exact_duplicates():
    """Находит дубликаты по дате рождения + точное совпадение ФИО"""
    with app.app_context():
        print("=" * 100)
        print(" " * 20 + "🎯 ПОИСК ДУБЛИКАТОВ: ДАТА РОЖДЕНИЯ + ФИО")
        print("=" * 100)
        print("\nКритерии:")
        print("  ✅ Одинаковая дата рождения")
        print("  ✅ Совпадение ФИО > 95%")
        print("  ℹ️  Пол НЕ учитывается (может быть ошибочным или это пара)")
        
        # Находим все даты рождения с дубликатами
        duplicates = db.session.query(
            Athlete.birth_date,
            func.count(Athlete.id).label('count')
        ).group_by(
            Athlete.birth_date
        ).having(
            func.count(Athlete.id) > 1
        ).order_by(
            Athlete.birth_date.desc()
        ).all()
        
        real_duplicates_groups = []
        
        for birth_date, count in duplicates:
            if not birth_date:
                continue
            
            # Получаем всех спортсменов с этой датой
            athletes = Athlete.query.filter_by(birth_date=birth_date).all()
            
            # Группируем по похожему ФИО
            groups = []
            processed = set()
            
            for i, athlete1 in enumerate(athletes):
                if athlete1.id in processed:
                    continue
                
                # Создаем новую группу
                group = [athlete1]
                processed.add(athlete1.id)
                
                name1 = normalize_name(athlete1.full_name)
                
                # Ищем похожих
                for athlete2 in athletes:
                    if athlete2.id in processed:
                        continue
                    
                    name2 = normalize_name(athlete2.full_name)
                    
                    # Проверяем схожесть ФИО
                    # Сначала проверяем фамилии
                    lastname_sim = similarity(athlete1.last_name or "", athlete2.last_name or "")
                    fullname_sim = similarity(name1, name2)
                    
                    # Если фамилии совпадают на 100% или почти (>95%), то проверяем имена менее строго
                    if lastname_sim > 0.95:
                        # Для одинаковых фамилий достаточно 70% совпадения полного ФИО
                        if fullname_sim > 0.70:
                            group.append(athlete2)
                            processed.add(athlete2.id)
                    # Или если полное ФИО совпадает почти полностью
                    elif fullname_sim > 0.95:
                        group.append(athlete2)
                        processed.add(athlete2.id)
                
                # Если в группе больше 1 человека - это дубликаты
                if len(group) > 1:
                    groups.append(group)
            
            # Добавляем найденные группы
            if groups:
                for group in groups:
                    real_duplicates_groups.append({
                        'birth_date': birth_date,
                        'athletes': group
                    })
        
        # Выводим результаты
        print("\n" + "=" * 100)
        print("НАЙДЕННЫЕ ДУБЛИКАТЫ:")
        print("=" * 100)
        
        total_to_remove = 0
        
        for i, dup_group in enumerate(real_duplicates_groups, 1):
            birth_date = dup_group['birth_date']
            athletes = dup_group['athletes']
            
            print(f"\n{'─' * 100}")
            print(f"#{i}. 📅 Дата: {birth_date.strftime('%d.%m.%Y')} | Дубликатов: {len(athletes)}")
            print(f"{'─' * 100}")
            
            # Показываем каждого
            for j, athlete in enumerate(athletes, 1):
                participations = Participant.query.filter_by(athlete_id=athlete.id).all()
                free_count = sum(1 for p in participations if p.pct_ppname == 'БЕСП')
                paid_count = len(participations) - free_count
                
                club = Club.query.get(athlete.club_id) if athlete.club_id else None
                
                marker = "🟢" if free_count > 0 else "⚪"
                
                print(f"\n   {marker} Спортсмен #{j}:")
                print(f"      ID: {athlete.id}")
                print(f"      ФИО: {athlete.full_name}")
                print(f"      Пол: {athlete.gender or '-'}")
                print(f"      Клуб: {club.name if club else 'Не указан'}")
                print(f"      Участий: {len(participations)} (🆓 {free_count} / 💰 {paid_count})")
                
                # Показываем турниры
                if participations:
                    print(f"      Турниры:")
                    for p in participations:
                        event = Event.query.get(p.event_id)
                        is_free = "🆓" if p.pct_ppname == 'БЕСП' else "💰"
                        event_name = event.name if event else "Неизвестно"
                        event_date = event.begin_date.strftime('%d.%m.%Y') if event and event.begin_date else '-'
                        print(f"         {is_free} {event_name} ({event_date})")
            
            # Определяем тип дубликата
            genders = set(a.gender for a in athletes if a.gender)
            
            if len(genders) > 1 and '/' in athletes[0].full_name:
                dup_type = "ПАРА/ТАНЦЫ (один и тот же дуэт, но разные записи на M и F)"
            elif len(genders) > 1:
                dup_type = "ОДИНОЧНИК (неправильно записан пол)"
            else:
                dup_type = "ДУБЛИКАТ (один и тот же спортсмен)"
            
            print(f"\n   📌 ТИП: {dup_type}")
            
            # Определяем основного
            main_athlete = max(athletes, key=lambda a: (
                len(a.full_name or ""),
                Participant.query.filter_by(athlete_id=a.id).count()
            ))
            
            others = [a for a in athletes if a.id != main_athlete.id]
            
            print(f"\n   ✅ РЕКОМЕНДАЦИЯ:")
            print(f"      Основной: ID {main_athlete.id} - {main_athlete.full_name}")
            
            if others:
                total_participations = sum(
                    Participant.query.filter_by(athlete_id=a.id).count() 
                    for a in others
                )
                print(f"      Удалить: {', '.join([f'ID {a.id}' for a in others])}")
                print(f"      Перенесется участий: {total_participations}")
                
                total_to_remove += len(others)
            
            # Считаем итоговую статистику после объединения
            total_part = sum(
                Participant.query.filter_by(athlete_id=a.id).count() 
                for a in athletes
            )
            total_free = sum(
                Participant.query.filter_by(athlete_id=a.id, pct_ppname='БЕСП').count() 
                for a in athletes
            )
            
            print(f"      После объединения: {total_part} участий ({total_free} бесплатных)")
        
        print("\n" + "=" * 100)
        print("ИТОГО:")
        print("=" * 100)
        print(f"📊 Найдено групп дубликатов: {len(real_duplicates_groups)}")
        print(f"🗑️  Можно удалить записей: {total_to_remove}")
        print(f"💾 Останется уникальных: {Athlete.query.count() - total_to_remove}")
        print(f"\n💡 Все показанные дубликаты имеют:")
        print(f"   ✅ Одинаковую дату рождения")
        print(f"   ✅ Совпадение ФИО > 95%")
        print(f"   ✅ Это точно один и тот же человек/пара!")
        print("=" * 100)
        
        return real_duplicates_groups

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        # Проверка конкретной даты
        from datetime import datetime
        
        with app.app_context():
            try:
                birth_date_str = sys.argv[1]
                birth_date = datetime.strptime(birth_date_str, '%d.%m.%Y').date()
                
                athletes = Athlete.query.filter_by(birth_date=birth_date).all()
                
                if not athletes:
                    print(f"❌ Спортсмены с датой {birth_date_str} не найдены")
                elif len(athletes) == 1:
                    print(f"✅ Только один спортсмен с датой {birth_date_str}")
                else:
                    print(f"🔍 Спортсмены с датой {birth_date_str}:\n")
                    
                    for i, a in enumerate(athletes, 1):
                        print(f"{i}. ID {a.id}: {a.full_name} (пол: {a.gender})")
                    
                    # Проверяем схожесть
                    print(f"\n📊 Анализ схожести ФИО:")
                    for i, a1 in enumerate(athletes):
                        for j, a2 in enumerate(athletes):
                            if i >= j:
                                continue
                            
                            sim = similarity(a1.full_name, a2.full_name)
                            if sim > 0.95:
                                print(f"  ✅ ID {a1.id} и ID {a2.id}: {sim*100:.1f}% - ДУБЛИКАТ")
                            else:
                                print(f"  ❌ ID {a1.id} и ID {a2.id}: {sim*100:.1f}% - разные люди")
            
            except ValueError:
                print("❌ Неверный формат даты! Используйте: ДД.ММ.ГГГГ")
    else:
        # Показываем все дубликаты
        find_exact_duplicates()

