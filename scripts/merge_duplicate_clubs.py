#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Автоматическое объединение дубликатов клубов с одинаковыми нормализованными названиями
Использование: python scripts/merge_duplicate_clubs.py
"""

import os
import sys
import shutil
from datetime import datetime
from collections import defaultdict

# Добавляем текущую директорию в путь
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app import app, db
from models import Club, Athlete
from utils.normalizers import normalize_string, fix_latin_to_cyrillic
from difflib import SequenceMatcher


def create_backup():
    """Создает бэкап базы данных"""
    db_path = 'instance/figure_skating.db'
    if not os.path.exists(db_path):
        # Пробуем найти в корне проекта
        db_path = 'figure_skating.db'
        if not os.path.exists(db_path):
            print(f"❌ База данных не найдена")
            return None
    
    backup_dir = 'backups'
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = f'before_merge_duplicate_clubs_{timestamp}.db'
    backup_path = os.path.join(backup_dir, backup_file)
    
    try:
        shutil.copy2(db_path, backup_path)
        print(f"✅ Бэкап создан: {backup_path}")
        return backup_file
    except Exception as e:
        print(f"❌ Ошибка при создании бэкапа: {e}")
        return None


def _calculate_similarity(name1, name2):
    """Вычисляет схожесть двух названий клубов (0.0 - 1.0)"""
    if not name1 or not name2:
        return 0.0
    
    # Нормализуем оба названия
    norm1 = normalize_string(fix_latin_to_cyrillic(name1)).lower()
    norm2 = normalize_string(fix_latin_to_cyrillic(name2)).lower()
    
    # Точное совпадение
    if norm1 == norm2:
        return 1.0
    
    # Проверка на вхождение одного названия в другое
    if norm1 in norm2 or norm2 in norm1:
        shorter = min(len(norm1), len(norm2))
        longer = max(len(norm1), len(norm2))
        if longer > 0 and shorter / longer >= 0.70 and shorter >= 10:
            return 0.95
    
    # Используем SequenceMatcher для вычисления общей схожести
    similarity_ratio = SequenceMatcher(None, norm1, norm2).ratio()
    return similarity_ratio


def find_duplicate_clubs():
    """Находит группы клубов с одинаковыми или похожими названиями"""
    all_clubs = Club.query.all()
    
    # Сначала группируем по точному совпадению нормализованных названий
    exact_groups = defaultdict(list)
    for club in all_clubs:
        if not club.name:
            continue
        normalized_name = normalize_string(fix_latin_to_cyrillic(club.name))
        if normalized_name:
            exact_groups[normalized_name].append(club)
    
    # Оставляем только группы с дубликатами
    duplicate_groups = {
        name: clubs for name, clubs in exact_groups.items() 
        if len(clubs) > 1
    }
    
    # Теперь ищем похожие клубы с помощью fuzzy matching
    processed_clubs = set()
    similarity_threshold = 0.85  # Порог схожести 85%
    
    for i, club1 in enumerate(all_clubs):
        if not club1.name or club1.id in processed_clubs:
            continue
        
        similar_clubs = [club1]
        norm1 = normalize_string(fix_latin_to_cyrillic(club1.name))
        
        for club2 in all_clubs[i+1:]:
            if not club2.name or club2.id in processed_clubs:
                continue
            
            # Проверяем схожесть
            similarity = _calculate_similarity(club1.name, club2.name)
            if similarity >= similarity_threshold:
                similar_clubs.append(club2)
                processed_clubs.add(club2.id)
        
        if len(similar_clubs) > 1:
            # Создаем ключ для группы
            group_key = norm1 or club1.name
            if group_key not in duplicate_groups:
                duplicate_groups[group_key] = []
            # Добавляем клубы, которых еще нет в группе
            existing_ids = {c.id for c in duplicate_groups[group_key]}
            for club in similar_clubs:
                if club.id not in existing_ids:
                    duplicate_groups[group_key].append(club)
            processed_clubs.add(club1.id)
    
    return duplicate_groups


def merge_club_group(clubs):
    """Объединяет группу клубов в один"""
    if len(clubs) < 2:
        return None
    
    # Выбираем клуб для сохранения: тот, у которого больше спортсменов
    # Если одинаково - выбираем тот, у которого есть external_id или более полное название
    clubs_with_counts = []
    for club in clubs:
        athlete_count = Athlete.query.filter_by(club_id=club.id).count()
        clubs_with_counts.append((club, athlete_count))
    
    # Сортируем: больше спортсменов -> более длинное название
    clubs_with_counts.sort(
        key=lambda x: (
            -x[1],  # Больше спортсменов
            -len(x[0].name or '')  # Более длинное название
        )
    )
    
    keep_club = clubs_with_counts[0][0]
    remove_clubs = [club for club, _ in clubs_with_counts[1:]]
    
    return keep_club, remove_clubs


def merge_duplicate_clubs():
    """Объединяет все дубликаты клубов"""
    with app.app_context():
        print("=" * 80)
        print("ОБЪЕДИНЕНИЕ ДУБЛИКАТОВ КЛУБОВ")
        print("=" * 80)
        print()
        
        # Находим дубликаты
        duplicate_groups = find_duplicate_clubs()
        
        if not duplicate_groups:
            print("✅ Дубликатов клубов не найдено!")
            return
        
        print(f"📋 Найдено групп дубликатов: {len(duplicate_groups)}")
        print()
        
        # Показываем найденные дубликаты
        total_to_merge = 0
        for normalized_name, clubs in sorted(duplicate_groups.items()):
            print(f"Группа: '{normalized_name}' ({len(clubs)} клубов)")
            for club in clubs:
                athlete_count = Athlete.query.filter_by(club_id=club.id).count()
                print(f"  - ID {club.id:3d}: '{club.name}' (спортсменов: {athlete_count})")
            total_to_merge += len(clubs) - 1
            print()
        
        print(f"📊 Всего будет объединено: {total_to_merge} клубов")
        print()
        
        # Подтверждение
        confirm = input("Объединить все дубликаты? (yes/NO): ").strip().lower()
        if confirm != 'yes':
            print("\n❌ Отменено")
            return
        
        # Создаем бэкап
        backup_file = create_backup()
        if not backup_file:
            print("\n❌ Не удалось создать бэкап. Операция отменена.")
            return
        
        print()
        print("🔄 Начинаем объединение...")
        print()
        
        merged_count = 0
        errors = []
        
        # Объединяем каждую группу
        for normalized_name, clubs in sorted(duplicate_groups.items()):
            try:
                keep_club, remove_clubs = merge_club_group(clubs)
                
                print(f"Объединяем группу: '{normalized_name}'")
                print(f"  Сохраняем: ID {keep_club.id} - '{keep_club.name}'")
                
                for remove_club in remove_clubs:
                    athlete_count = Athlete.query.filter_by(club_id=remove_club.id).count()
                    print(f"  Удаляем: ID {remove_club.id} - '{remove_club.name}' ({athlete_count} спортсменов)")
                    
                    # Переносим спортсменов
                    Athlete.query.filter_by(club_id=remove_club.id).update({
                        'club_id': keep_club.id
                    })
                    
                    # Обновляем данные клуба, если нужно
                    if not keep_club.country and remove_club.country:
                        keep_club.country = remove_club.country
                    if not keep_club.city and remove_club.city:
                        keep_club.city = remove_club.city
                    
                    # Удаляем дубликат
                    db.session.delete(remove_club)
                    merged_count += 1
                
                db.session.commit()
                print(f"  ✅ Группа объединена")
                print()
                
            except Exception as e:
                db.session.rollback()
                error_msg = f"Ошибка при объединении группы '{normalized_name}': {e}"
                print(f"  ❌ {error_msg}")
                errors.append(error_msg)
                print()
        
        print("=" * 80)
        if errors:
            print(f"⚠️  Объединено: {merged_count} клубов")
            print(f"❌ Ошибок: {len(errors)}")
            for error in errors:
                print(f"   - {error}")
        else:
            print(f"✅ Успешно объединено: {merged_count} клубов")
        print(f"💾 Бэкап: {backup_file}")
        print("=" * 80)


if __name__ == '__main__':
    merge_duplicate_clubs()
