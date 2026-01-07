#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестовый скрипт для проверки фильтра по месяцам на странице турниров
"""

from app import app, db
from models import Event, Category, Participant
from datetime import datetime

def test_month_filter():
    """Тест фильтра по месяцам"""
    with app.app_context():
        print("=" * 60)
        print("Тестирование фильтра по месяцам")
        print("=" * 60)
        
        # Получаем все турниры с датами
        events_with_dates = Event.query.filter(Event.begin_date.isnot(None)).all()
        
        if not events_with_dates:
            print("❌ В базе данных нет турниров с датами!")
            return False
        
        print(f"\n✅ Найдено турниров с датами: {len(events_with_dates)}")
        
        # Собираем уникальные месяцы
        months = sorted(set(
            event.begin_date.strftime('%Y-%m') 
            for event in events_with_dates 
            if event.begin_date
        ), reverse=True)
        
        print(f"✅ Уникальных месяцев: {len(months)}")
        print("\nДоступные месяцы:")
        
        months_ru = {
            '01': 'Январь', '02': 'Февраль', '03': 'Март', '04': 'Апрель',
            '05': 'Май', '06': 'Июнь', '07': 'Июль', '08': 'Август',
            '09': 'Сентябрь', '10': 'Октябрь', '11': 'Ноябрь', '12': 'Декабрь'
        }
        
        for month in months[:10]:  # Показываем первые 10
            year, m = month.split('-')
            month_name = months_ru.get(m, m)
            
            # Подсчитываем турниры за этот месяц
            events_count = Event.query.filter(
                db.extract('year', Event.begin_date) == int(year),
                db.extract('month', Event.begin_date) == int(m)
            ).count()
            
            # Подсчитываем участников
            event_ids = [
                e.id for e in Event.query.filter(
                    db.extract('year', Event.begin_date) == int(year),
                    db.extract('month', Event.begin_date) == int(m)
                ).all()
            ]
            
            participants_count = 0
            if event_ids:
                participants_count = db.session.query(Participant.id).join(
                    Category, Participant.category_id == Category.id
                ).filter(
                    Category.event_id.in_(event_ids)
                ).count()
            
            print(f"  📅 {month_name} {year}: {events_count} турниров, {participants_count} участников")
        
        if len(months) > 10:
            print(f"  ... и еще {len(months) - 10} месяцев")
        
        print("\n" + "=" * 60)
        print("✅ Тест завершен успешно!")
        print("=" * 60)
        
        # Дополнительная статистика
        print("\n📊 Общая статистика:")
        print(f"  Всего турниров: {Event.query.count()}")
        print(f"  Всего категорий: {Category.query.count()}")
        print(f"  Всего участников: {Participant.query.count()}")
        
        return True

def test_format_month():
    """Тест функции форматирования месяцев"""
    print("\n" + "=" * 60)
    print("Тестирование функции format_month")
    print("=" * 60)
    
    from app import format_month_filter
    
    test_cases = [
        ('2024-10', 'Октябрь 2024'),
        ('2024-01', 'Январь 2024'),
        ('2023-12', 'Декабрь 2023'),
        ('', ''),
        (None, ''),
    ]
    
    all_passed = True
    for input_val, expected in test_cases:
        result = format_month_filter(input_val)
        if result == expected:
            print(f"✅ '{input_val}' -> '{result}'")
        else:
            print(f"❌ '{input_val}' -> '{result}' (ожидалось: '{expected}')")
            all_passed = False
    
    if all_passed:
        print("\n✅ Все тесты форматирования прошли успешно!")
    else:
        print("\n❌ Некоторые тесты не прошли!")
    
    return all_passed

if __name__ == '__main__':
    print("\n🧪 Запуск тестов для фильтра по месяцам\n")
    
    try:
        test1 = test_format_month()
        test2 = test_month_filter()
        
        print("\n" + "=" * 60)
        if test1 and test2:
            print("🎉 ВСЕ ТЕСТЫ ПРОШЛИ УСПЕШНО!")
        else:
            print("⚠️  Некоторые тесты не прошли")
        print("=" * 60 + "\n")
        
    except Exception as e:
        print(f"\n❌ Ошибка при выполнении тестов: {e}")
        import traceback
        traceback.print_exc()




