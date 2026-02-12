#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Принудительное объединение двух спортсменов
Можно указать по имени или по ID
"""

import os
import sys
import shutil
from datetime import datetime

# Корень проекта (родитель папки scripts)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app import app, db
from models import Club, Athlete, Participant, CoachAssignment


def create_backup():
    """Создает бэкап базы данных"""
    db_path = 'instance/figure_skating.db'
    if not os.path.exists(db_path):
        print(f"❌ База данных не найдена: {db_path}")
        return None
    
    backup_dir = 'backups'
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = f'before_merge_athletes_{timestamp}.db'
    backup_path = os.path.join(backup_dir, backup_file)
    
    try:
        shutil.copy2(db_path, backup_path)
        print(f"✅ Бэкап создан: {backup_path}")
        return backup_file
    except Exception as e:
        print(f"❌ Ошибка при создании бэкапа: {e}")
        return None


def find_athlete_by_name(name_part):
    """Находит спортсмена по части имени"""
    with app.app_context():
        # Ищем по полному имени
        athletes = Athlete.query.filter(
            Athlete.full_name_xml.like(f'%{name_part}%')
        ).all()
        
        if not athletes:
            # Пробуем искать по фамилии и имени отдельно
            parts = name_part.split()
            if len(parts) >= 2:
                first_name = parts[0]
                last_name = parts[-1]
                athletes = Athlete.query.filter(
                    Athlete.first_name.like(f'%{first_name}%'),
                    Athlete.last_name.like(f'%{last_name}%')
                ).all()
        
        return athletes


def merge_two_athletes(keep_athlete_id, remove_athlete_id, use_full_name=None, skip_confirm=False, skip_backup=False):
    """Объединяет двух спортсменов. keep = кого оставляем, remove = кого переносим и удаляем. skip_backup=True — не создавать бэкап (для пакетного запуска)."""
    
    with app.app_context():
        print("=" * 80)
        print("ПРИНУДИТЕЛЬНОЕ ОБЪЕДИНЕНИЕ ДВУХ СПОРТСМЕНОВ")
        print("=" * 80)
        print()
        
        # Получаем спортсменов
        keep_athlete = Athlete.query.get(keep_athlete_id)
        remove_athlete = Athlete.query.get(remove_athlete_id)
        
        if not keep_athlete:
            print(f"❌ Спортсмен с ID {keep_athlete_id} не найден!")
            return 1
        
        if not remove_athlete:
            print(f"❌ Спортсмен с ID {remove_athlete_id} не найден!")
            return 1
        
        if keep_athlete_id == remove_athlete_id:
            print("❌ Нельзя объединить спортсмена сам с собой!")
            return 1
        
        # Подсчитываем участия
        keep_participations = Participant.query.filter_by(athlete_id=keep_athlete_id).count()
        remove_participations = Participant.query.filter_by(athlete_id=remove_athlete_id).count()
        
        # Показываем информацию
        print("СПОРТСМЕНЫ:")
        print(f"  ОСТАВИТЬ: ID {keep_athlete_id}")
        print(f"    ФИО: {keep_athlete.full_name_xml or 'нет'}")
        print(f"    Имя: {keep_athlete.first_name or 'нет'}")
        print(f"    Фамилия: {keep_athlete.last_name or 'нет'}")
        print(f"    Дата рождения: {keep_athlete.birth_date or 'нет'}")
        print(f"    Клуб ID: {keep_athlete.club_id or 'нет'}")
        print(f"    Участий: {keep_participations}")
        print()
        print(f"  УДАЛИТЬ: ID {remove_athlete_id}")
        print(f"    ФИО: {remove_athlete.full_name_xml or 'нет'}")
        print(f"    Имя: {remove_athlete.first_name or 'нет'}")
        print(f"    Фамилия: {remove_athlete.last_name or 'нет'}")
        print(f"    Дата рождения: {remove_athlete.birth_date or 'нет'}")
        print(f"    Клуб ID: {remove_athlete.club_id or 'нет'}")
        print(f"    Участий: {remove_participations}")
        print()
        print(f"  ИТОГО: {keep_participations + remove_participations} участий")
        print()
        
        # Проверка на конфликт UniqueConstraint (event_id, category_id, athlete_id)
        # Один спортсмен может быть только раз в одной категории одного соревнования
        if remove_participations > 0:
            remove_parts = Participant.query.filter_by(athlete_id=remove_athlete_id).all()
            conflicts = []
            for p in remove_parts:
                exists = Participant.query.filter_by(
                    athlete_id=keep_athlete_id,
                    event_id=p.event_id,
                    category_id=p.category_id
                ).first()
                if exists:
                    conflicts.append((p.event_id, p.category_id, p.id))
            if conflicts:
                print("❌ КОНФЛИКТ: оба спортсмена участвовали в одних и тех же (соревнование, категория)!")
                print("   Объединение приведёт к нарушению уникальности. Конфликты:")
                for ev, cat, pid in conflicts:
                    print(f"   — event_id={ev}, category_id={cat} (participant_id={pid})")
                print("\n   Решение: нужно вручную удалить или переназначить одно из участий.")
                return 1
        
        # Определяем полное имя для оставшегося спортсмена
        if use_full_name:
            final_full_name = use_full_name
        else:
            # Используем более полное имя
            keep_full = keep_athlete.full_name_xml or ""
            remove_full = remove_athlete.full_name_xml or ""
            if len(remove_full) > len(keep_full):
                final_full_name = remove_full
                print(f"💡 Будет использовано более полное имя: '{final_full_name}'")
            else:
                final_full_name = keep_full
        
        # Подтверждение
        print("=" * 80)
        if not skip_confirm:
            confirm = input("Объединить этих спортсменов? (yes/NO): ").strip().lower()
            if confirm != 'yes':
                print("❌ Объединение отменено")
                return 0
        else:
            print("Объединение по аргументам командной строки (без запроса подтверждения).")
        
        backup_file = None
        if not skip_backup:
            print("\nСоздание бэкапа...")
            backup_file = create_backup()
            if not backup_file:
                print("❌ Не удалось создать бэкап. Объединение отменено.")
                return 1
        else:
            print("\n(бэкап пропущен — пакетный режим)")
        
        # Объединяем
        print(f"\nПеренос {remove_participations} участий...")
        
        try:
            # Обновляем полное имя, если указано
            if use_full_name and keep_athlete.full_name_xml != use_full_name:
                keep_athlete.full_name_xml = use_full_name
                print(f"Обновлено полное имя на: '{use_full_name}'")
            
            # Переносим все участия
            if remove_participations > 0:
                Participant.query.filter_by(athlete_id=remove_athlete_id).update({
                    'athlete_id': keep_athlete_id
                })
            
            # Переносим привязки тренеров (coach_assignment)
            ca_count = CoachAssignment.query.filter_by(athlete_id=remove_athlete_id).count()
            if ca_count > 0:
                CoachAssignment.query.filter_by(athlete_id=remove_athlete_id).update({
                    'athlete_id': keep_athlete_id
                })
                print(f"Перенос {ca_count} записей coach_assignment...")
            
            # Удаляем дубликат
            db.session.delete(remove_athlete)
            
            # Коммитим изменения
            db.session.commit()
            
            # Проверяем результат
            final_count = Participant.query.filter_by(athlete_id=keep_athlete_id).count()
            
            print("\n" + "=" * 80)
            print("✅ УСПЕШНО ОБЪЕДИНЕНО!")
            print("=" * 80)
            print(f"Объединено в: ID {keep_athlete_id}")
            print(f"  ФИО: {keep_athlete.full_name_xml or 'нет'}")
            print(f"Удален спортсмен: ID {remove_athlete_id}")
            print(f"Перенесено участий: {remove_participations}")
            print(f"\n✅ Итоговое количество участий: {final_count}")
            if backup_file:
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


def main():
    """Основная функция. Можно вызвать: python merge_two_athletes.py KEEP_ID REMOVE_ID"""
    # Вызов с двумя ID: оставить KEEP_ID, перенести и удалить REMOVE_ID
    if len(sys.argv) >= 3:
        try:
            keep_id = int(sys.argv[1])
            remove_id = int(sys.argv[2])
            print("=" * 80)
            print("ПРИНУДИТЕЛЬНОЕ ОБЪЕДИНЕНИЕ ДВУХ СПОРТСМЕНОВ (по ID)")
            print("=" * 80)
            print(f"  Оставить: ID {keep_id}")
            print(f"  Удалить (перенести участия): ID {remove_id}")
            print()
            return merge_two_athletes(keep_id, remove_id, skip_confirm=True)
        except ValueError:
            print("Ошибка: оба аргумента должны быть числовыми ID.", file=sys.stderr)
            return 1

    print("=" * 80)
    print("ПРИНУДИТЕЛЬНОЕ ОБЪЕДИНЕНИЕ ДВУХ СПОРТСМЕНОВ")
    print("=" * 80)
    print()
    print("Можно искать по имени или указать ID напрямую. Либо: python merge_two_athletes.py ОСТАВИТЬ_ID УДАЛИТЬ_ID")
    print()
    
    # Ищем первого спортсмена
    name1 = input("Введите имя первого спортсмена (или ID): ").strip()
    
    with app.app_context():
        athlete1 = None
        try:
            athlete1_id = int(name1)
            athlete1 = Athlete.query.get(athlete1_id)
        except ValueError:
            # Ищем по имени
            athletes = find_athlete_by_name(name1)
            if len(athletes) == 1:
                athlete1 = athletes[0]
            elif len(athletes) > 1:
                print(f"\nНайдено {len(athletes)} спортсменов с таким именем:")
                for i, a in enumerate(athletes, 1):
                    print(f"  {i}. ID {a.id}: {a.full_name_xml or 'нет ФИО'} (Имя: {a.first_name}, Фамилия: {a.last_name})")
                choice = input("\nВыберите номер (1, 2, ...): ").strip()
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(athletes):
                        athlete1 = athletes[idx]
                    else:
                        print("❌ Некорректный номер!")
                        return 1
                except ValueError:
                    print("❌ Некорректный ввод!")
                    return 1
        
        if not athlete1:
            print(f"❌ Спортсмен '{name1}' не найден!")
            return 1
        
        # Ищем второго спортсмена
        name2 = input("Введите имя второго спортсмена (или ID): ").strip()
        
        athlete2 = None
        try:
            athlete2_id = int(name2)
            athlete2 = Athlete.query.get(athlete2_id)
        except ValueError:
            # Ищем по имени
            athletes = find_athlete_by_name(name2)
            if len(athletes) == 1:
                athlete2 = athletes[0]
            elif len(athletes) > 1:
                print(f"\nНайдено {len(athletes)} спортсменов с таким именем:")
                for i, a in enumerate(athletes, 1):
                    print(f"  {i}. ID {a.id}: {a.full_name_xml or 'нет ФИО'} (Имя: {a.first_name}, Фамилия: {a.last_name})")
                choice = input("\nВыберите номер (1, 2, ...): ").strip()
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(athletes):
                        athlete2 = athletes[idx]
                    else:
                        print("❌ Некорректный номер!")
                        return 1
                except ValueError:
                    print("❌ Некорректный ввод!")
                    return 1
        
        if not athlete2:
            print(f"❌ Спортсмен '{name2}' не найден!")
            return 1
        
        # Показываем информацию и спрашиваем, какой оставить
        print("\n" + "=" * 80)
        print("НАЙДЕННЫЕ СПОРТСМЕНЫ:")
        print("=" * 80)
        print(f"\nСпортсмен 1:")
        print(f"  ID: {athlete1.id}")
        print(f"  ФИО: {athlete1.full_name_xml or 'нет'}")
        print(f"  Имя: {athlete1.first_name}")
        print(f"  Фамилия: {athlete1.last_name}")
        
        print(f"\nСпортсмен 2:")
        print(f"  ID: {athlete2.id}")
        print(f"  ФИО: {athlete2.full_name_xml or 'нет'}")
        print(f"  Имя: {athlete2.first_name}")
        print(f"  Фамилия: {athlete2.last_name}")
        print()
        
        # Определяем, какой оставить
        part1 = Participant.query.filter_by(athlete_id=athlete1.id).count()
        part2 = Participant.query.filter_by(athlete_id=athlete2.id).count()
        
        # Рекомендация - оставляем того, у кого более полное имя или больше участий
        keep_full = athlete1.full_name_xml or ""
        remove_full = athlete2.full_name_xml or ""
        
        if len(remove_full) > len(keep_full):
            default = '2'
            print(f"💡 Рекомендация: оставить спортсмена 2 (более полное имя)")
        elif part2 > part1:
            default = '2'
            print(f"💡 Рекомендация: оставить спортсмена 2 (больше участий)")
        else:
            default = '1'
            print(f"💡 Рекомендация: оставить спортсмена 1")
        
        choice = input(f"Какого спортсмена оставить? (1/2, Enter для '{default}'): ").strip()
        
        if not choice:
            choice = default
        
        # Используем более полное имя из двух (независимо от выбора)
        if len(remove_full) > len(keep_full):
            final_full_name = remove_full
        else:
            final_full_name = keep_full
        
        if choice == '1':
            keep_id = athlete1.id
            remove_id = athlete2.id
        elif choice == '2':
            keep_id = athlete2.id
            remove_id = athlete1.id
        else:
            print("❌ Некорректный выбор!")
            return 1
        
        # Можно указать финальное полное имя
        print()
        custom_name = input(f"Полное имя для оставшегося спортсмена (Enter для '{final_full_name}'): ").strip()
        if custom_name:
            final_full_name = custom_name
        
        return merge_two_athletes(keep_id, remove_id, final_full_name if final_full_name else None)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n❌ Прервано пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Ошибка: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

