#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Удаление клубов/школ без спортсменов
Безопасно удаляет школы где 0 спортсменов
"""

import os
import sys
import shutil
from datetime import datetime

# Добавляем текущую директорию в путь
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app import app, db
from models import Club, Athlete, Participant


def create_backup():
    """Создает бэкап базы данных"""
    db_path = 'instance/figure_skating.db'
    if not os.path.exists(db_path):
        print(f"❌ База данных не найдена: {db_path}")
        return None
    
    backup_dir = 'backups'
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = f'before_delete_clubs_zero_{timestamp}.db'
    backup_path = os.path.join(backup_dir, backup_file)
    
    try:
        shutil.copy2(db_path, backup_path)
        print(f"✅ Бэкап создан: {backup_path}")
        return backup_file
    except Exception as e:
        print(f"❌ Ошибка при создании бэкапа: {e}")
        return None


def delete_clubs_zero_athletes():
    """Удаляет клубы без спортсменов"""
    
    with app.app_context():
        print("=" * 80)
        print("УДАЛЕНИЕ ШКОЛ/КЛУБОВ БЕЗ СПОРТСМЕНОВ")
        print("=" * 80)
        print()
        
        # Получаем все клубы
        all_clubs = Club.query.all()
        total_clubs = len(all_clubs)
        
        print(f"📊 Всего клубов в базе: {total_clubs}")
        print()
        
        # Находим клубы без спортсменов
        clubs_with_zero = []
        
        for club in all_clubs:
            athletes_count = Athlete.query.filter_by(club_id=club.id).count()
            
            if athletes_count == 0:
                clubs_with_zero.append(club)
        
        if not clubs_with_zero:
            print("✅ Все клубы имеют хотя бы одного спортсмена!")
            print("   Нет клубов для удаления.")
            return 0
        
        # Сортируем по ID
        clubs_with_zero.sort(key=lambda x: x.id)
        
        print(f"⚠️  Найдено клубов без спортсменов: {len(clubs_with_zero)}")
        print()
        print("=" * 80)
        print("СПИСОК КЛУБОВ ДЛЯ УДАЛЕНИЯ:")
        print("=" * 80)
        print()
        
        for club in clubs_with_zero:
            external_id = club.external_id if club.external_id else "нет"
            print(f"  ID {club.id}: '{club.name}'")
            print(f"    External ID: {external_id}")
            print()
        
        # Подтверждение
        print("=" * 80)
        print("ПОДТВЕРЖДЕНИЕ УДАЛЕНИЯ:")
        print("=" * 80)
        print(f"Будет удалено клубов: {len(clubs_with_zero)}")
        print()
        
        confirm = input("Удалить эти клубы? (yes/NO): ").strip().lower()
        
        if confirm != 'yes':
            print("❌ Удаление отменено")
            return 0
        
        # Создаем бэкап
        print("\nСоздание бэкапа...")
        backup_file = create_backup()
        
        if not backup_file:
            print("❌ Не удалось создать бэкап. Удаление отменено.")
            return 1
        
        # Удаляем клубы
        print(f"\nУдаление {len(clubs_with_zero)} клубов...")
        
        deleted_clubs = []
        
        try:
            for club in clubs_with_zero:
                club_name = club.name
                club_id = club.id
                
                # Удаляем клуб
                db.session.delete(club)
                deleted_clubs.append({
                    'id': club_id,
                    'name': club_name
                })
            
            # Коммитим изменения
            db.session.commit()
            
            print("\n" + "=" * 80)
            print("✅ УСПЕШНО УДАЛЕНО!")
            print("=" * 80)
            print(f"Удалено клубов: {len(deleted_clubs)}")
            print()
            print("Удаленные клубы:")
            for club_info in deleted_clubs:
                print(f"  • ID {club_info['id']}: '{club_info['name']}'")
            print()
            print(f"📦 Бэкап: backups/{backup_file}")
            print("=" * 80)
            
            return 0
            
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ ОШИБКА: {e}")
            print("Изменения отменены!")
            import traceback
            traceback.print_exc()
            return 1


def main():
    """Основная функция"""
    try:
        return delete_clubs_zero_athletes()
    except KeyboardInterrupt:
        print("\n\n❌ Прервано пользователем")
        return 1
    except Exception as e:
        print(f"❌ Ошибка: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())

