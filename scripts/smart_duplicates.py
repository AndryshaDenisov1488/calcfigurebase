#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Умный поиск дубликатов спортсменов
Показывает только НАСТОЯЩИЕ дубликаты, исключая случайные совпадения дат
"""

from app import app, db
from models import Athlete, Participant, Event, Club
from sqlalchemy import func
from difflib import SequenceMatcher

def similarity(a, b):
    """Вычисляет схожесть двух строк (0.0 - 1.0)"""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def is_real_duplicate(athlete1, athlete2):
    """Определяет, являются ли два спортсмена реальными дубликатами"""
    
    # Получаем фамилии
    last_name1 = athlete1.last_name or ""
    last_name2 = athlete2.last_name or ""
    
    # Критерий 1: Одинаковые фамилии (или очень похожие)
    if last_name1 and last_name2:
        # Для пар/танцев фамилия может быть составной
        # Например: "Софья ГРАБЧАК / Максим ПОЛТОРА" vs "ГРАБЧАК/ПОЛТОРАК"
        
        # Проверяем прямое совпадение
        if last_name1 == last_name2:
            return True
        
        # Проверяем похожесть (>85%)
        if similarity(last_name1, last_name2) > 0.85:
            return True
        
        # Для пар: проверяем, есть ли общие части
        # Убираем слеши и пробелы
        parts1 = set(last_name1.replace('/', ' ').split())
        parts2 = set(last_name2.replace('/', ' ').split())
        
        # Если есть хотя бы одна общая значимая часть
        common = parts1 & parts2
        # Убираем короткие служебные слова
        common = {p for p in common if len(p) > 2}
        
        if common and len(common) >= len(parts1) * 0.5:
            return True
    
    # Критерий 2: Проверяем полное ФИО
    full_name1 = athlete1.full_name or ""
    full_name2 = athlete2.full_name or ""
    
    if full_name1 and full_name2:
        # Очень похожие полные имена (>90%)
        if similarity(full_name1, full_name2) > 0.90:
            return True
    
    # Если не прошли проверки - не дубликаты
    return False

def find_smart_duplicates():
    """Находит ТОЛЬКО настоящие дубликаты"""
    with app.app_context():
        print("=" * 100)
        print(" " * 25 + "🧠 УМНЫЙ ПОИСК НАСТОЯЩИХ ДУБЛИКАТОВ")
        print("=" * 100)
        print("\nКритерии:")
        print("  ✅ Одинаковая или очень похожая фамилия (>85% совпадение)")
        print("  ✅ Похожее полное ФИО (>90% совпадение)")
        print("  ✅ Для пар/танцев: общие части фамилии")
        print("  ❌ Исключаются случайные совпадения дат рождения")
        
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
        
        real_duplicates_count = 0
        total_groups = 0
        
        print("\n" + "=" * 100)
        print("СПИСОК НАСТОЯЩИХ ДУБЛИКАТОВ:")
        print("=" * 100)
        
        for birth_date, count in duplicates:
            if not birth_date:
                continue
            
            # Получаем всех спортсменов с этой датой
            athletes = Athlete.query.filter_by(birth_date=birth_date).all()
            
            # Проверяем попарно, кто из них настоящие дубликаты
            real_duplicates = []
            checked = set()
            
            for i, athlete1 in enumerate(athletes):
                for j, athlete2 in enumerate(athletes):
                    if i >= j:  # Не проверяем дважды одну и ту же пару
                        continue
                    
                    pair_key = tuple(sorted([athlete1.id, athlete2.id]))
                    if pair_key in checked:
                        continue
                    checked.add(pair_key)
                    
                    # Проверяем, настоящий ли это дубликат
                    if is_real_duplicate(athlete1, athlete2):
                        if not any(athlete1.id in group or athlete2.id in group for group in real_duplicates):
                            real_duplicates.append([athlete1, athlete2])
                        else:
                            # Добавляем к существующей группе
                            for group in real_duplicates:
                                if athlete1.id in [a.id for a in group]:
                                    if athlete2 not in group:
                                        group.append(athlete2)
                                    break
                                elif athlete2.id in [a.id for a in group]:
                                    if athlete1 not in group:
                                        group.append(athlete1)
                                    break
            
            # Если нашли настоящие дубликаты в этой группе
            if real_duplicates:
                total_groups += 1
                
                print(f"\n{'─' * 100}")
                print(f"#{total_groups}. 📅 Дата рождения: {birth_date.strftime('%d.%m.%Y')} — Настоящих дубликатов: {len(real_duplicates[0])}")
                print(f"{'─' * 100}")
                
                for group in real_duplicates:
                    for i, athlete in enumerate(group, 1):
                        # Получаем участия
                        participations = Participant.query.filter_by(athlete_id=athlete.id).all()
                        free_count = sum(1 for p in participations if p.pct_ppname == 'БЕСП')
                        paid_count = len(participations) - free_count
                        
                        # Получаем клуб
                        club = Club.query.get(athlete.club_id) if athlete.club_id else None
                        
                        # Цветовой маркер
                        marker = "🟢" if free_count > 0 else "⚪"
                        
                        print(f"\n   {marker} Спортсмен #{i}:")
                        print(f"      ID: {athlete.id}")
                        print(f"      ФИО: {athlete.full_name}")
                        print(f"      Фамилия: {athlete.last_name}")
                        print(f"      Пол: {athlete.gender or '-'}")
                        print(f"      Клуб: {club.name if club else 'Не указан'} (ID: {athlete.club_id or '-'})")
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
                    
                    # Анализ группы
                    print(f"\n   ✅ РЕКОМЕНДАЦИЯ: Объединить в одну запись")
                    print(f"      Причина: Одинаковая или похожая фамилия")
                    
                    # Определяем основного спортсмена
                    main_athlete = max(group, key=lambda a: (
                        len(a.full_name or ""),  # Чем длиннее ФИО
                        Participant.query.filter_by(athlete_id=a.id).count()  # Чем больше участий
                    ))
                    
                    print(f"      Основной: ID {main_athlete.id} ({main_athlete.full_name})")
                    
                    others = [a for a in group if a.id != main_athlete.id]
                    if others:
                        print(f"      Удалить: {', '.join([f'ID {a.id}' for a in others])}")
                    
                    real_duplicates_count += len(group) - 1
        
        print("\n" + "=" * 100)
        print("ИТОГО:")
        print("=" * 100)
        print(f"Найдено групп с настоящими дубликатами: {total_groups}")
        print(f"Можно освободить записей: {real_duplicates_count}")
        print(f"\n💡 Это только НАСТОЯЩИЕ дубликаты (одинаковые фамилии)")
        print(f"   Случайные совпадения дат (КУЗНЕЦОВ + САБАДА/АСТАХОВ) исключены!")
        print("=" * 100)
        
        return total_groups

def show_duplicate_by_date(date_str):
    """Показывает дубликаты для конкретной даты с умным анализом"""
    with app.app_context():
        from datetime import datetime
        
        try:
            birth_date = datetime.strptime(date_str, '%d.%m.%Y').date()
        except ValueError:
            print(f"❌ Неверный формат даты! Используйте: ДД.ММ.ГГГГ (например: 05.10.2012)")
            return
        
        athletes = Athlete.query.filter_by(birth_date=birth_date).all()
        
        if not athletes:
            print(f"❌ Спортсмены с датой рождения {date_str} не найдены")
            return
        
        if len(athletes) == 1:
            print(f"✅ Спортсмен с датой рождения {date_str} только один (дубликатов нет)")
            return
        
        print("=" * 100)
        print(f"🔍 АНАЛИЗ ДУБЛИКАТОВ ДЛЯ ДАТЫ: {date_str}")
        print("=" * 100)
        
        # Показываем всех
        for i, athlete in enumerate(athletes, 1):
            participations = Participant.query.filter_by(athlete_id=athlete.id).all()
            free_count = sum(1 for p in participations if p.pct_ppname == 'БЕСП')
            club = Club.query.get(athlete.club_id) if athlete.club_id else None
            
            marker = "🟢" if free_count > 0 else "⚪"
            
            print(f"\n{marker} Спортсмен #{i}:")
            print(f"  ID: {athlete.id}")
            print(f"  ФИО: {athlete.full_name}")
            print(f"  Фамилия: '{athlete.last_name}'")
            print(f"  Клуб: {club.name if club else 'Не указан'}")
            print(f"  Участий: {len(participations)} (бесплатных: {free_count})")
        
        # Умный анализ
        print("\n" + "=" * 100)
        print("🧠 УМНЫЙ АНАЛИЗ:")
        print("=" * 100)
        
        # Проверяем попарно
        found_real_duplicates = False
        
        for i, athlete1 in enumerate(athletes):
            for j, athlete2 in enumerate(athletes):
                if i >= j:
                    continue
                
                if is_real_duplicate(athlete1, athlete2):
                    found_real_duplicates = True
                    sim = similarity(athlete1.last_name or "", athlete2.last_name or "")
                    
                    print(f"\n✅ НАСТОЯЩИЙ ДУБЛИКАТ:")
                    print(f"   ID {athlete1.id} и ID {athlete2.id}")
                    print(f"   Фамилии похожи на {sim*100:.1f}%")
                    print(f"   '{athlete1.last_name}' ≈ '{athlete2.last_name}'")
                    print(f"   👉 РЕКОМЕНДУЕТСЯ ОБЪЕДИНИТЬ")
        
        if not found_real_duplicates:
            print(f"\n❌ НАСТОЯЩИХ ДУБЛИКАТОВ НЕ НАЙДЕНО")
            print(f"   Это разные люди с одинаковой датой рождения:")
            for athlete in athletes:
                print(f"   • {athlete.full_name} (ID: {athlete.id})")
            print(f"\n   ⚠️  НЕ ОБЪЕДИНЯТЬ!")
        
        print("=" * 100)

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        # Показываем умный анализ для конкретной даты
        show_duplicate_by_date(sys.argv[1])
    else:
        # Показываем все настоящие дубликаты
        find_smart_duplicates()

