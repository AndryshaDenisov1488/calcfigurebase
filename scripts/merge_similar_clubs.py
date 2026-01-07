#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Интерактивное объединение клубов со схожими названиями
Позволяет выбрать название для каждой группы объединения
"""

import os
import sys
from datetime import datetime
import shutil

# Добавляем текущую директорию в путь
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app import app, db
from models import Club, Athlete
from difflib import SequenceMatcher


def normalize_club_name(name):
    """Нормализует название клуба для сравнения"""
    if not name:
        return ""
    normalized = ' '.join(name.lower().split())
    normalized = normalized.replace('"', '').replace("'", "")
    return normalized


def similarity(name1, name2):
    """Вычисляет схожесть двух названий (0.0 - 1.0)"""
    if not name1 or not name2:
        return 0.0
    
    norm1 = normalize_club_name(name1)
    norm2 = normalize_club_name(name2)
    
    if norm1 == norm2:
        return 1.0
    
    return SequenceMatcher(None, norm1, norm2).ratio()


def create_backup():
    """Создает бэкап базы данных"""
    db_path = 'instance/figure_skating.db'
    backup_dir = 'backups'
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = f'before_merge_similar_clubs_{timestamp}.db'
    backup_path = os.path.join(backup_dir, backup_file)
    
    shutil.copy2(db_path, backup_path)
    print(f"✅ Бэкап создан: {backup_path}\n")
    return backup_file


def find_similar_club_groups():
    """Находит группы схожих клубов"""
    all_clubs = Club.query.all()
    similar_groups = []
    processed = set()
    
    for i, club1 in enumerate(all_clubs):
        if club1.id in processed:
            continue
        
        similar_clubs = [club1]
        
        for club2 in all_clubs[i+1:]:
            if club2.id in processed:
                continue
            
            sim = similarity(club1.name, club2.name)
            
            if sim > 0.70:
                similar_clubs.append(club2)
                processed.add(club2.id)
        
        if len(similar_clubs) > 1:
            # Вычисляем среднюю схожесть
            total_sim = 0.0
            comparisons = 0
            for c1 in similar_clubs:
                for c2 in similar_clubs:
                    if c1.id < c2.id:
                        total_sim += similarity(c1.name, c2.name)
                        comparisons += 1
            
            avg_sim = total_sim / comparisons if comparisons > 0 else 0.0
            
            similar_groups.append({
                'clubs': similar_clubs,
                'similarity': avg_sim
            })
            
            processed.add(club1.id)
    
    return similar_groups


def merge_clubs(keep_club_id, remove_club_ids, target_name=None):
    """Объединяет клубы: переносит спортсменов и удаляет старые клубы"""
    keep_club = Club.query.get(keep_club_id)
    if not keep_club:
        return False
    
    # Обновляем название, если указано
    if target_name:
        keep_club.name = target_name
    
    total_transferred = 0
    removed_clubs = []
    
    for remove_club_id in remove_club_ids:
        remove_club = Club.query.get(remove_club_id)
        if not remove_club:
            continue
        
        # Подсчитываем спортсменов
        athletes_count = Athlete.query.filter_by(club_id=remove_club_id).count()
        
        # Переносим спортсменов
        if athletes_count > 0:
            updated = Athlete.query.filter_by(club_id=remove_club_id).update({
                'club_id': keep_club_id
            })
            total_transferred += updated
        
        # Удаляем клуб
        db.session.delete(remove_club)
        removed_clubs.append({
            'id': remove_club_id,
            'name': remove_club.name,
            'athletes_transferred': athletes_count
        })
    
    return {
        'keep_club': keep_club,
        'total_transferred': total_transferred,
        'removed_clubs': removed_clubs
    }


def merge_similar_clubs_interactive():
    """Интерактивное объединение схожих клубов"""
    
    with app.app_context():
        print("=" * 80)
        print("ОБЪЕДИНЕНИЕ КЛУБОВ СО СХОЖИМИ НАЗВАНИЯМИ")
        print("=" * 80)
        print()
        print("Критерии для объединения:")
        print("  ✅ Высокая схожесть (>90%)")
        print("  ⚠️  Средняя схожесть (80-90%)")
        print("  ❌ Исключение: группа со схожестью ~82% с 5 клубами (разные клубы)")
        print()
        
        # Находим группы схожих клубов
        print("Поиск схожих клубов...")
        all_groups = find_similar_club_groups()
        
        # Фильтруем группы: высокая схожесть (>90%) и средняя (80-90%), но не группа ~82%
        groups_to_merge = []
        excluded_groups = []
        
        for group in all_groups:
            clubs = group['clubs']
            avg_sim = group['similarity']
            
            # Исключаем группу ~82% с 5 клубами (это разные клубы)
            # Проверяем по схожести и количеству клубов
            if 0.81 <= avg_sim <= 0.83 and len(clubs) >= 5:
                excluded_groups.append(group)
                continue
            
            # Также исключаем группы со схожестью <82% с большим количеством клубов (это разные клубы)
            if avg_sim < 0.82 and len(clubs) >= 4:
                excluded_groups.append(group)
                continue
            
            # Включаем высокую и среднюю схожесть
            if avg_sim > 0.80:
                groups_to_merge.append(group)
        
        if not groups_to_merge:
            print("✅ Групп для объединения не найдено!")
            if excluded_groups:
                print(f"\nПропущено {len(excluded_groups)} групп (разные клубы)")
            return 0
        
        # Сортируем по схожести (от высокой к низкой)
        groups_to_merge.sort(key=lambda x: x['similarity'], reverse=True)
        
        print(f"Найдено групп для объединения: {len(groups_to_merge)}")
        if excluded_groups:
            print(f"Пропущено групп (разные клубы): {len(excluded_groups)}")
        print()
        
        # Показываем план объединения
        print("=" * 80)
        print("ПЛАН ОБЪЕДИНЕНИЯ:")
        print("=" * 80)
        
        merge_plan = []
        
        for group_idx, group in enumerate(groups_to_merge, 1):
            clubs = group['clubs']
            avg_sim = group['similarity']
            
            # Подсчитываем спортсменов
            total_athletes = sum(
                Athlete.query.filter_by(club_id=club.id).count() 
                for club in clubs
            )
            
            print(f"\n{'-' * 80}")
            print(f"ГРУППА #{group_idx} (схожесть: {avg_sim*100:.1f}%)")
            print(f"{'-' * 80}")
            
            club_options = []
            for i, club in enumerate(clubs, 1):
                athletes_count = Athlete.query.filter_by(club_id=club.id).count()
                external_id = club.external_id if club.external_id else "нет"
                
                print(f"\n  {i}. ID {club.id}: '{club.name}'")
                print(f"     Спортсменов: {athletes_count}")
                print(f"     External ID: {external_id}")
                
                club_options.append({
                    'club': club,
                    'athletes_count': athletes_count
                })
            
            print(f"\n  Всего спортсменов в группе: {total_athletes}")
            
            # Предлагаем выбрать название
            print(f"\n  Выберите название для объединения:")
            print(f"    • Введите номер клуба (1-{len(club_options)}) чтобы использовать его название")
            print(f"    • Или введите 'skip' чтобы пропустить эту группу")
            print(f"    • Или введите 'custom:Название' чтобы указать своё название")
            
            while True:
                choice = input(f"\n  Ваш выбор: ").strip()
                
                if choice.lower() == 'skip':
                    print("  ⏭️  Группа пропущена")
                    break
                
                # Проверяем custom название
                if choice.lower().startswith('custom:'):
                    custom_name = choice[7:].strip()
                    if custom_name:
                        # Используем первый клуб как основной, но с новым названием
                        keep_club = club_options[0]['club']
                        remove_clubs = [opt['club'].id for opt in club_options[1:]]
                        
                        merge_plan.append({
                            'group_idx': group_idx,
                            'keep_club_id': keep_club.id,
                            'remove_club_ids': remove_clubs,
                            'target_name': custom_name,
                            'similarity': avg_sim,
                            'total_athletes': total_athletes
                        })
                        print(f"  ✅ Будет использовано название: '{custom_name}'")
                        break
                    else:
                        print("  ❌ Название не может быть пустым!")
                        continue
                
                # Проверяем номер
                try:
                    option_num = int(choice)
                    if 1 <= option_num <= len(club_options):
                        selected = club_options[option_num - 1]
                        keep_club = selected['club']
                        remove_clubs = [
                            opt['club'].id 
                            for opt in club_options 
                            if opt['club'].id != keep_club.id
                        ]
                        
                        merge_plan.append({
                            'group_idx': group_idx,
                            'keep_club_id': keep_club.id,
                            'remove_club_ids': remove_clubs,
                            'target_name': None,  # Используем существующее название
                            'similarity': avg_sim,
                            'total_athletes': total_athletes
                        })
                        print(f"  ✅ Будет использовано название: '{keep_club.name}'")
                        break
                    else:
                        print(f"  ❌ Введите число от 1 до {len(club_options)}!")
                except ValueError:
                    print("  ❌ Некорректный ввод!")
        
        if not merge_plan:
            print("\n❌ Нет групп для объединения!")
            return 0
        
        # Показываем итоговый план
        print("\n" + "=" * 80)
        print("ИТОГОВЫЙ ПЛАН ОБЪЕДИНЕНИЯ:")
        print("=" * 80)
        
        total_groups = len(merge_plan)
        total_athletes_to_move = sum(plan['total_athletes'] for plan in merge_plan)
        total_clubs_to_delete = sum(len(plan['remove_club_ids']) for plan in merge_plan)
        
        for plan in merge_plan:
            keep_club = Club.query.get(plan['keep_club_id'])
            target_name = plan['target_name'] or keep_club.name
            
            print(f"\nГруппа #{plan['group_idx']}:")
            print(f"  Оставить: ID {plan['keep_club_id']} - '{target_name}'")
            print(f"  Удалить: {len(plan['remove_club_ids'])} клубов")
            print(f"  Перенести спортсменов: {plan['total_athletes']}")
        
        print(f"\nВсего:")
        print(f"  Групп к объединению: {total_groups}")
        print(f"  Клубов к удалению: {total_clubs_to_delete}")
        print(f"  Спортсменов для переноса: {total_athletes_to_move}")
        
        # Финальное подтверждение
        print("\n" + "=" * 80)
        confirm = input(f"Объединить {total_groups} групп клубов? (yes/NO): ").strip().lower()
        
        if confirm != 'yes':
            print("❌ Отменено")
            return 0
        
        # Создаем бэкап
        print("\nСоздание бэкапа...")
        backup_file = create_backup()
        
        # Выполняем объединение
        print("\nОбъединение клубов...")
        
        merged_groups = 0
        total_transferred = 0
        total_deleted = 0
        
        for plan in merge_plan:
            keep_club_id = plan['keep_club_id']
            remove_club_ids = plan['remove_club_ids']
            target_name = plan['target_name']
            
            result = merge_clubs(keep_club_id, remove_club_ids, target_name)
            
            if result:
                merged_groups += 1
                total_transferred += result['total_transferred']
                total_deleted += len(result['removed_clubs'])
                
                print(f"\n✅ Группа #{plan['group_idx']}:")
                print(f"   Объединено в: '{result['keep_club'].name}'")
                print(f"   Перенесено спортсменов: {result['total_transferred']}")
                print(f"   Удалено клубов: {len(result['removed_clubs'])}")
        
        # Сохраняем изменения
        try:
            db.session.commit()
            
            print("\n" + "=" * 80)
            print("✅ УСПЕШНО ОБЪЕДИНЕНО!")
            print("=" * 80)
            print(f"Объединено групп: {merged_groups}")
            print(f"Перенесено спортсменов: {total_transferred}")
            print(f"Удалено клубов: {total_deleted}")
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
    """Основная функция"""
    try:
        return merge_similar_clubs_interactive()
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

