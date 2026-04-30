#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Объединение двух конкретных клубов по ID.
Поддерживает интерактивный и неинтерактивный режимы.
"""

import os
import sys
import shutil
import argparse
from datetime import datetime

# Добавляем корень проекта (родитель папки scripts) в путь
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app import app, db
from models import Club, Athlete


def create_backup():
    """Создает бэкап базы данных"""
    db_path = 'instance/figure_skating.db'
    if not os.path.exists(db_path):
        print(f"❌ База данных не найдена: {db_path}")
        return None
    
    backup_dir = 'backups'
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = f'before_merge_clubs_{timestamp}.db'
    backup_path = os.path.join(backup_dir, backup_file)
    
    try:
        shutil.copy2(db_path, backup_path)
        print(f"✅ Бэкап создан: {backup_path}")
        return backup_file
    except Exception as e:
        print(f"❌ Ошибка при создании бэкапа: {e}")
        return None


def _is_positive_confirmation(value):
    """Позитивные варианты подтверждения."""
    normalized = (value or '').strip().lower()
    return normalized in {'yes', 'y', 'да', 'д'}


def merge_two_clubs(keep_club_id, remove_club_id, skip_confirm=False):
    """Объединяет два клуба"""
    
    with app.app_context():
        print("=" * 80)
        print("ОБЪЕДИНЕНИЕ ДВУХ КЛУБОВ")
        print("=" * 80)
        print()
        
        # Получаем клубы
        keep_club = db.session.get(Club, keep_club_id)
        remove_club = db.session.get(Club, remove_club_id)
        
        if not keep_club:
            print(f"❌ Клуб с ID {keep_club_id} не найден!")
            return 1
        
        if not remove_club:
            print(f"❌ Клуб с ID {remove_club_id} не найден!")
            return 1
        
        if keep_club_id == remove_club_id:
            print("❌ Нельзя объединить клуб сам с собой!")
            return 1
        
        # Подсчитываем спортсменов
        keep_athletes_count = Athlete.query.filter_by(club_id=keep_club_id).count()
        remove_athletes_count = Athlete.query.filter_by(club_id=remove_club_id).count()
        
        # Показываем информацию
        print("КЛУБЫ:")
        print(f"  ОСТАВИТЬ: ID {keep_club_id} - '{keep_club.name}'")
        print(f"    Спортсменов: {keep_athletes_count}")
        print(f"    External ID: {keep_club.external_id if keep_club.external_id else 'нет'}")
        print()
        print(f"  УДАЛИТЬ: ID {remove_club_id} - '{remove_club.name}'")
        print(f"    Спортсменов: {remove_athletes_count}")
        print(f"    External ID: {remove_club.external_id if remove_club.external_id else 'нет'}")
        print()
        print(f"  ИТОГО: {keep_athletes_count + remove_athletes_count} спортсменов в '{keep_club.name}'")
        print()
        
        # Подтверждение
        if not skip_confirm:
            confirm = input("Объединить эти клубы? (yes/y/да/д, иначе NO): ").strip()
            if not _is_positive_confirmation(confirm):
                print("❌ Объединение отменено")
                return 0
        else:
            print("Подтверждение пропущено (--yes)")
        
        # Создаем бэкап
        print("\nСоздание бэкапа...")
        backup_file = create_backup()
        
        if not backup_file:
            print("❌ Не удалось создать бэкап. Объединение отменено.")
            return 1
        
        # Объединяем
        print(f"\nПеренос {remove_athletes_count} спортсменов...")
        
        try:
            # Переносим спортсменов
            if remove_athletes_count > 0:
                Athlete.query.filter_by(club_id=remove_club_id).update({
                    'club_id': keep_club_id
                })
            
            # Удаляем клуб
            db.session.delete(remove_club)
            
            # Коммитим изменения
            db.session.commit()
            
            # Проверяем результат
            final_count = Athlete.query.filter_by(club_id=keep_club_id).count()
            
            print("\n" + "=" * 80)
            print("✅ УСПЕШНО ОБЪЕДИНЕНО!")
            print("=" * 80)
            print(f"Объединено в: '{keep_club.name}' (ID {keep_club_id})")
            print(f"Удален клуб: '{remove_club.name}' (ID {remove_club_id})")
            print(f"Перенесено спортсменов: {remove_athletes_count}")
            print(f"\n✅ Итоговое количество спортсменов: {final_count}")
            print(f"\n📦 Бэкап: backups/{backup_file}")
            print("=" * 80)
            
            return 0
            
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ ОШИБКА: {e}")
            print("Изменения отменены!")
            import traceback
            traceback.print_exc()
            return 1


def _build_arg_parser():
    parser = argparse.ArgumentParser(
        description='Объединение двух клубов по ID с переносом спортсменов',
    )
    parser.add_argument('id1', type=int, help='ID первого клуба')
    parser.add_argument('id2', type=int, help='ID второго клуба')
    parser.add_argument(
        '--yes',
        action='store_true',
        help='пропустить подтверждение и выполнить объединение сразу',
    )
    parser.add_argument(
        '--keep-id',
        type=int,
        help='какой ID клуба оставить (должен быть одним из id1/id2)',
    )
    return parser


def main():
    """Основная функция"""
    parser = _build_arg_parser()
    args = parser.parse_args()
    club_id1 = args.id1
    club_id2 = args.id2
    
    # Определяем какой клуб оставить
    with app.app_context():
        club1 = db.session.get(Club, club_id1)
        club2 = db.session.get(Club, club_id2)
        
        if not club1:
            print(f"❌ Клуб с ID {club_id1} не найден!")
            return 1
        
        if not club2:
            print(f"❌ Клуб с ID {club_id2} не найден!")
            return 1
        
        athletes1 = Athlete.query.filter_by(club_id=club_id1).count()
        athletes2 = Athlete.query.filter_by(club_id=club_id2).count()
        
        print("\n" + "=" * 80)
        print("ИНФОРМАЦИЯ О КЛУБАХ:")
        print("=" * 80)
        print(f"\nКлуб 1:")
        print(f"  ID: {club_id1}")
        print(f"  Название: '{club1.name}'")
        print(f"  Спортсменов: {athletes1}")
        print(f"\nКлуб 2:")
        print(f"  ID: {club_id2}")
        print(f"  Название: '{club2.name}'")
        print(f"  Спортсменов: {athletes2}")
        print()
        
        # Рекомендация
        if athletes1 >= athletes2:
            default = '1'
            print(f"💡 Рекомендация: оставить клуб 1 (больше спортсменов)")
        else:
            default = '2'
            print(f"💡 Рекомендация: оставить клуб 2 (больше спортсменов)")
        
        if args.keep_id is not None:
            if args.keep_id not in (club_id1, club_id2):
                print(f"❌ Ошибка: --keep-id={args.keep_id} должен быть равен {club_id1} или {club_id2}")
                return 1
            keep_id = args.keep_id
            remove_id = club_id2 if keep_id == club_id1 else club_id1
            print(f"Выбран клуб для сохранения через --keep-id: {keep_id}")
        else:
            choice = input(f"Какой клуб оставить? (1/2, Enter для '{default}'): ").strip()

            if not choice:
                choice = default

            if choice == '1':
                keep_id = club_id1
                remove_id = club_id2
            elif choice == '2':
                keep_id = club_id2
                remove_id = club_id1
            else:
                print("❌ Некорректный выбор! Используется рекомендация.")
                if athletes1 >= athletes2:
                    keep_id = club_id1
                    remove_id = club_id2
                else:
                    keep_id = club_id2
                    remove_id = club_id1
    
    try:
        return merge_two_clubs(keep_id, remove_id, skip_confirm=args.yes)
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

