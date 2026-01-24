#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
УМНЫЙ список дубликатов: Дата рождения + Фамилия + АНАЛИЗ ИМЕН
Отличает настоящие дубликаты от братьев/сестер
"""

from app import app, db
from models import Athlete, Participant, Event, Club
from sqlalchemy import func
from difflib import SequenceMatcher

def similarity(a, b):
    """Схожесть строк"""
    if not a or not b:
        return 0.0
    a_clean = ' '.join(a.lower().split())
    b_clean = ' '.join(b.lower().split())
    return SequenceMatcher(None, a_clean, b_clean).ratio()

def list_duplicates_smart():
    """Умный список дубликатов с анализом имен"""
    with app.app_context():
        print("="*100)
        print("УМНЫЙ ПОИСК ДУБЛИКАТОВ: Одинаковая дата рождения + Одинаковая фамилия + АНАЛИЗ ИМЕН")
        print("="*100)
        print("\nКритерии:")
        print("  ✅ Настоящий дубликат: схожесть имени >80% И схожесть полного ФИО >80%")
        print("  ❌ Братья/сестры: схожесть имени <50% (НЕ объединять!)")
        print("  ⚠️  Требует проверки: схожесть имени 50-80%")
        print("="*100)
        
        # Находим дубликаты по дате рождения и фамилии
        duplicates = db.session.query(
            Athlete.birth_date,
            Athlete.last_name,
            func.count(Athlete.id).label('count')
        ).filter(
            Athlete.birth_date.isnot(None),
            Athlete.last_name.isnot(None)
        ).group_by(
            Athlete.birth_date,
            Athlete.last_name
        ).having(
            func.count(Athlete.id) > 1
        ).order_by(
            Athlete.birth_date.desc()
        ).all()
        
        print(f"\nНайдено групп с одинаковой датой + фамилией: {len(duplicates)}\n")
        print("="*100)
        
        true_duplicates = []
        siblings = []
        needs_review = []
        
        for birth_date, lastname, count in duplicates:
            athletes = Athlete.query.filter_by(
                birth_date=birth_date,
                last_name=lastname
            ).all()
            
            # Анализируем схожесть имен внутри группы
            first_name_similarities = []
            full_name_similarities = []
            
            for i in range(len(athletes)):
                for j in range(i + 1, len(athletes)):
                    a1 = athletes[i]
                    a2 = athletes[j]
                    
                    first_sim = similarity(a1.first_name or '', a2.first_name or '')
                    full_sim = similarity(a1.full_name or '', a2.full_name or '')
                    
                    first_name_similarities.append(first_sim)
                    full_name_similarities.append(full_sim)
            
            # Определяем тип группы
            avg_first_sim = sum(first_name_similarities) / len(first_name_similarities) if first_name_similarities else 0
            avg_full_sim = sum(full_name_similarities) / len(full_name_similarities) if full_name_similarities else 0
            
            group_type = None
            if avg_first_sim > 0.8 and avg_full_sim > 0.8:
                group_type = 'duplicate'
                true_duplicates.append({
                    'birth_date': birth_date,
                    'lastname': lastname,
                    'athletes': athletes,
                    'avg_first_sim': avg_first_sim,
                    'avg_full_sim': avg_full_sim
                })
            elif avg_first_sim < 0.5:
                group_type = 'siblings'
                siblings.append({
                    'birth_date': birth_date,
                    'lastname': lastname,
                    'athletes': athletes,
                    'avg_first_sim': avg_first_sim
                })
            else:
                group_type = 'review'
                needs_review.append({
                    'birth_date': birth_date,
                    'lastname': lastname,
                    'athletes': athletes,
                    'avg_first_sim': avg_first_sim,
                    'avg_full_sim': avg_full_sim
                })
        
        # Выводим НАСТОЯЩИЕ ДУБЛИКАТЫ (можно объединять)
        print("\n" + "="*100)
        print(f"✅ НАСТОЯЩИЕ ДУБЛИКАТЫ (можно объединять): {len(true_duplicates)}")
        print("="*100)
        
        total_to_remove = 0
        duplicate_num = 0
        
        for group in true_duplicates:
            duplicate_num += 1
            birth_date = group['birth_date']
            lastname = group['lastname']
            athletes = group['athletes']
            
            print(f"\n{'-'*100}")
            print(f"#{duplicate_num}. {birth_date.strftime('%d.%m.%Y')} | {lastname} | Дубликатов: {len(athletes)}")
            print(f"   Схожесть имени: {group['avg_first_sim']*100:.1f}% | Схожесть ФИО: {group['avg_full_sim']*100:.1f}%")
            print(f"{'-'*100}")
            
            for j, athlete in enumerate(athletes, 1):
                participations = Participant.query.filter_by(athlete_id=athlete.id).all()
                free_count = sum(1 for p in participations if p.pct_ppname == 'БЕСП')
                paid_count = len(participations) - free_count
                
                club = Club.query.get(athlete.club_id) if athlete.club_id else None
                
                print(f"\n   Спортсмен #{j}:")
                print(f"      ID: {athlete.id}")
                print(f"      ФИО: {athlete.full_name}")
                print(f"      Имя: {athlete.first_name}")
                print(f"      Пол: {athlete.gender or '-'}")
                print(f"      Клуб: {club.name if club else 'Не указан'}")
                print(f"      Участий: {len(participations)} (Бесплатных: {free_count}, Платных: {paid_count})")
                
                if participations:
                    for p in participations[:5]:  # Показываем первые 5
                        event = Event.query.get(p.event_id)
                        if event:
                            is_free = "БЕСП" if p.pct_ppname == 'БЕСП' else "ПЛАТ"
                            print(f"         [{is_free}] {event.name} ({event.begin_date.strftime('%d.%m.%Y') if event.begin_date else '-'})")
                    if len(participations) > 5:
                        print(f"         ... и еще {len(participations) - 5} участий")
            
            # Тип
            if '/' in athletes[0].full_name:
                print(f"\n   ТИП: ПАРА/ТАНЦЫ")
            else:
                print(f"\n   ТИП: ОДИНОЧНИК")
            
            # Рекомендация объединения
            main = max(athletes, key=lambda a: (
                len(a.full_name or ""),
                Participant.query.filter_by(athlete_id=a.id).count()
            ))
            
            others = [a for a in athletes if a.id != main.id]
            
            print(f"\n   ✅ РЕКОМЕНДАЦИЯ: ОБЪЕДИНИТЬ")
            print(f"      Основной: ID {main.id} ({main.full_name})")
            if others:
                print(f"      Удалить: {', '.join([f'ID {a.id}' for a in others])}")
                total_to_remove += len(others)
            
            # Итог
            total_part = sum(Participant.query.filter_by(athlete_id=a.id).count() for a in athletes)
            total_free = sum(Participant.query.filter_by(athlete_id=a.id, pct_ppname='БЕСП').count() for a in athletes)
            
            print(f"      Итого после: {total_part} участий ({total_free} бесплатных)")
        
        # Выводим БРАТЬЕВ/СЕСТЕР (НЕ объединять!)
        print("\n\n" + "="*100)
        print(f"❌ БРАТЬЯ/СЕСТРЫ (НЕ объединять!): {len(siblings)}")
        print("="*100)
        
        sibling_num = 0
        for group in siblings:
            sibling_num += 1
            birth_date = group['birth_date']
            lastname = group['lastname']
            athletes = group['athletes']
            
            print(f"\n{'-'*100}")
            print(f"#{sibling_num}. {birth_date.strftime('%d.%m.%Y')} | {lastname} | Разных имен: {len(athletes)}")
            print(f"   Схожесть имени: {group['avg_first_sim']*100:.1f}% (РАЗНЫЕ ИМЕНА!)")
            print(f"{'-'*100}")
            
            for j, athlete in enumerate(athletes, 1):
                participations = Participant.query.filter_by(athlete_id=athlete.id).count()
                print(f"\n   Спортсмен #{j}:")
                print(f"      ID: {athlete.id} | {athlete.full_name}")
                print(f"      Имя: '{athlete.first_name}' | Участий: {participations}")
            
            print(f"\n   ⚠️  ВНИМАНИЕ: Это РАЗНЫЕ люди (братья/сестры)! НЕ ОБЪЕДИНЯТЬ!")
        
        # Выводим группы, требующие проверки
        if needs_review:
            print("\n\n" + "="*100)
            print(f"⚠️  ТРЕБУЮТ ПРОВЕРКИ ВРУЧНУЮ: {len(needs_review)}")
            print("="*100)
            
            review_num = 0
            for group in needs_review:
                review_num += 1
                birth_date = group['birth_date']
                lastname = group['lastname']
                athletes = group['athletes']
                
                print(f"\n{'-'*100}")
                print(f"#{review_num}. {birth_date.strftime('%d.%m.%Y')} | {lastname} | Записей: {len(athletes)}")
                print(f"   Схожесть имени: {group['avg_first_sim']*100:.1f}% | Схожесть ФИО: {group['avg_full_sim']*100:.1f}%")
                print(f"{'-'*100}")
                
                for j, athlete in enumerate(athletes, 1):
                    participations = Participant.query.filter_by(athlete_id=athlete.id).count()
                    print(f"   {j}. ID {athlete.id}: {athlete.full_name} (участий: {participations})")
                
                print(f"\n   ⚠️  Проверьте вручную перед объединением!")
        
        # Итоговая статистика
        print("\n\n" + "="*100)
        print("ИТОГО:")
        print("="*100)
        print(f"Настоящих дубликатов (можно объединять): {len(true_duplicates)}")
        print(f"Братьев/сестер (НЕ объединять): {len(siblings)}")
        print(f"Требуют проверки: {len(needs_review)}")
        print(f"\nЗаписей к удалению (только настоящие дубликаты): {total_to_remove}")
        print(f"Всего спортсменов: {Athlete.query.count()}")
        print(f"Останется после чистки: {Athlete.query.count() - total_to_remove}")
        print("\n" + "="*100)
        print("ВАЖНО:")
        print("  • Объединяйте ТОЛЬКО группы из раздела 'Настоящие дубликаты'")
        print("  • НЕ объединяйте братьев/сестер из раздела 'Братья/сестры'")
        print("  • Используйте: python merge_only_true_duplicates.py")
        print("="*100)

if __name__ == '__main__':
    list_duplicates_smart()

