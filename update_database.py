<<<<<<< HEAD
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для обновления базы данных на сервере
"""

import os
import sys
from datetime import datetime

# Добавляем текущую директорию в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Event

def main():
    """Основная функция"""
    with app.app_context():
        print("🔍 Поиск турниров без даты начала...")
        
        # Находим турниры без даты начала, но с датой окончания
        events_to_fix = Event.query.filter(
            Event.begin_date.is_(None),
            Event.end_date.isnot(None)
        ).all()
        
        if not events_to_fix:
            print("✅ Все турниры уже имеют даты начала!")
            return
        
        print(f"📋 Найдено {len(events_to_fix)} турниров для исправления:")
        
        for i, event in enumerate(events_to_fix, 1):
            print(f"{i}. {event.name}")
            print(f"   Дата окончания: {event.end_date}")
            event.begin_date = event.end_date
            print(f"   ✅ Установлена дата начала: {event.begin_date}")
        
        try:
            print(f"\n💾 Сохранение изменений...")
            db.session.commit()
            print(f"✅ Успешно исправлено {len(events_to_fix)} турниров!")
            
            # Проверяем результат
            remaining = Event.query.filter(
                Event.begin_date.is_(None),
                Event.end_date.isnot(None)
            ).count()
            
            if remaining == 0:
                print("🎉 Все турниры теперь имеют даты начала!")
            else:
                print(f"⚠️  Осталось {remaining} турниров без даты начала")
                
        except Exception as e:
            db.session.rollback()
            print(f"❌ Ошибка при сохранении: {e}")
            return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
=======
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для обновления базы данных на сервере
"""

import os
import sys
from datetime import datetime

# Добавляем текущую директорию в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Event

def main():
    """Основная функция"""
    with app.app_context():
        print("🔍 Поиск турниров без даты начала...")
        
        # Находим турниры без даты начала, но с датой окончания
        events_to_fix = Event.query.filter(
            Event.begin_date.is_(None),
            Event.end_date.isnot(None)
        ).all()
        
        if not events_to_fix:
            print("✅ Все турниры уже имеют даты начала!")
            return
        
        print(f"📋 Найдено {len(events_to_fix)} турниров для исправления:")
        
        for i, event in enumerate(events_to_fix, 1):
            print(f"{i}. {event.name}")
            print(f"   Дата окончания: {event.end_date}")
            event.begin_date = event.end_date
            print(f"   ✅ Установлена дата начала: {event.begin_date}")
        
        try:
            print(f"\n💾 Сохранение изменений...")
            db.session.commit()
            print(f"✅ Успешно исправлено {len(events_to_fix)} турниров!")
            
            # Проверяем результат
            remaining = Event.query.filter(
                Event.begin_date.is_(None),
                Event.end_date.isnot(None)
            ).count()
            
            if remaining == 0:
                print("🎉 Все турниры теперь имеют даты начала!")
            else:
                print(f"⚠️  Осталось {remaining} турниров без даты начала")
                
        except Exception as e:
            db.session.rollback()
            print(f"❌ Ошибка при сохранении: {e}")
            return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
>>>>>>> 0ad5c8fdbf27d11e9354e3c0f7d3e79ec45ba482
