#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для объединения дубликатов спортсменов
"""

from app import app, db
from models import Athlete, Participant
from datetime import date

def merge_vasilisa():
    """Объединяем двух Василис в одну"""
    with app.app_context():
        print("=" * 80)
        print("ОБЪЕДИНЕНИЕ ДУБЛИКАТОВ: Василиса БУРОН ЛЕБЕДЕВА")
        print("=" * 80)
        
        # ID спортсменов
        athlete1_id = 326  # Полное имя, 1 бесплатное
        athlete2_id = 807  # Короткое имя, 1 платное
        
        athlete1 = Athlete.query.get(athlete1_id)
        athlete2 = Athlete.query.get(athlete2_id)
        
        if not athlete1 or not athlete2:
            print("❌ Один из спортсменов не найден!")
            return
        
        print(f"\n📋 СПОРТСМЕН #1 (ОСНОВНОЙ):")
        print(f"  ID: {athlete1.id}")
        print(f"  ФИО: {athlete1.full_name}")
        print(f"  Клуб ID: {athlete1.club_id}")
        
        print(f"\n📋 СПОРТСМЕН #2 (ДУБЛИКАТ):")
        print(f"  ID: {athlete2.id}")
        print(f"  ФИО: {athlete2.full_name}")
        print(f"  Клуб ID: {athlete2.club_id}")
        
        # Подсчитываем участия
        participations1 = Participant.query.filter_by(athlete_id=athlete1_id).count()
        participations2 = Participant.query.filter_by(athlete_id=athlete2_id).count()
        
        print(f"\n📊 УЧАСТИЯ:")
        print(f"  Спортсмен #1: {participations1} участий")
        print(f"  Спортсмен #2: {participations2} участий")
        print(f"  Всего будет: {participations1 + participations2} участий")
        
        # Спрашиваем подтверждение
        print(f"\n⚠️  ВНИМАНИЕ! Будет выполнено:")
        print(f"  1. Все участия спортсмена #{athlete2_id} будут перенесены на #{athlete1_id}")
        print(f"  2. Спортсмен #{athlete2_id} будет удален")
        print(f"  3. Останется только #{athlete1_id} с {participations1 + participations2} участиями")
        
        confirm = input(f"\n❓ Продолжить? (yes/no): ").strip().lower()
        
        if confirm != 'yes':
            print("\n❌ Операция отменена")
            return
        
        try:
            # Переносим все участия с athlete2 на athlete1
            participants_to_update = Participant.query.filter_by(athlete_id=athlete2_id).all()
            
            print(f"\n🔄 Переношу {len(participants_to_update)} участий...")
            for p in participants_to_update:
                p.athlete_id = athlete1_id
            
            # Удаляем дубликат
            print(f"🗑️  Удаляю дубликат (ID: {athlete2_id})...")
            db.session.delete(athlete2)
            
            # Сохраняем изменения
            db.session.commit()
            
            print(f"\n✅ УСПЕШНО!")
            print(f"  Объединено: {participations1 + participations2} участий")
            print(f"  Остался спортсмен ID: {athlete1_id}")
            print(f"  Удален дубликат ID: {athlete2_id}")
            
            # Проверяем результат
            final_count = Participant.query.filter_by(athlete_id=athlete1_id).count()
            free_count = Participant.query.filter_by(athlete_id=athlete1_id, pct_ppname='БЕСП').count()
            
            print(f"\n📊 ИТОГОВАЯ СТАТИСТИКА:")
            print(f"  Всего участий: {final_count}")
            print(f"  Бесплатных: {free_count}")
            print(f"  Платных: {final_count - free_count}")
            
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ ОШИБКА: {e}")
            print("Изменения отменены")

def find_all_duplicates():
    """Ищет всех потенциальных дубликатов по дате рождения"""
    with app.app_context():
        print("\n" + "=" * 80)
        print("ПОИСК ВСЕХ ДУБЛИКАТОВ ПО ДАТЕ РОЖДЕНИЯ")
        print("=" * 80)
        
        # Получаем все даты рождения с дубликатами
        from sqlalchemy import func
        
        duplicates = db.session.query(
            Athlete.birth_date,
            func.count(Athlete.id).label('count')
        ).group_by(
            Athlete.birth_date
        ).having(
            func.count(Athlete.id) > 1
        ).all()
        
        print(f"\n✅ Найдено дат рождения с дубликатами: {len(duplicates)}")
        
        for birth_date, count in duplicates:
            if birth_date:
                print(f"\n📅 {birth_date.strftime('%d.%m.%Y')} - {count} спортсменов:")
                athletes = Athlete.query.filter_by(birth_date=birth_date).all()
                for a in athletes:
                    participations = Participant.query.filter_by(athlete_id=a.id).count()
                    print(f"  • ID {a.id}: {a.full_name} (участий: {participations})")

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--merge':
        merge_vasilisa()
    else:
        find_all_duplicates()
        print("\n" + "=" * 80)
        print("💡 Для объединения Василисы запустите:")
        print("   python merge_duplicate_athletes.py --merge")
        print("=" * 80)



