#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Интерактивное объединение одной школы с похожими
Вводите ID школы, видите похожие, выбираете для объединения
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

# Словарь расшифровок распространенных аббревиатур
ABBREVIATIONS = {
    'кфк': 'клуб фигурного катания',
    'сшор': 'специализированная школа олимпийского резерва',
    'дюсш': 'детско-юношеская спортивная школа',
    'сдюсшор': 'специализированная детско-юношеская школа олимпийского резерва',
    'цска': 'центральный спортивный клуб армии',
    'афу': 'автономное физкультурно-спортивное учреждение',
    'мо': 'министерство обороны',
    'рф': 'российская федерация',
    'гбу': 'государственное бюджетное учреждение',
    'до': 'дополнительного образования',
}


def expand_abbreviations(text):
    """Расшифровывает аббревиатуры в тексте"""
    words = text.split()
    expanded_words = []
    
    for word in words:
        word_lower = word.lower()
        # Проверяем, есть ли эта аббревиатура в словаре
        if word_lower in ABBREVIATIONS:
            # Заменяем аббревиатуру на расшифровку
            expanded_words.extend(ABBREVIATIONS[word_lower].split())
        else:
            expanded_words.append(word)
    
    return ' '.join(expanded_words)


def extract_key_words(name):
    """Извлекает ключевые слова из названия (исключая служебные)"""
    # Служебные слова, которые не несут смысла
    stop_words = {'ооо', 'оао', 'зао', 'ип', 'ао', 'и', 'в', 'по', 'им', 'имени', 'для', 'на', 'с'}
    
    words = name.split()
    key_words = []
    
    for word in words:
        word_clean = word.lower().strip('.,;:!?()[]{}')
        # Пропускаем очень короткие слова (1-2 символа) и служебные
        if len(word_clean) > 2 and word_clean not in stop_words:
            key_words.append(word_clean)
    
    return set(key_words)  # Возвращаем множество для сравнения


def normalize_club_name(name):
    """Нормализует название клуба для сравнения"""
    if not name:
        return ""
    # Приводим к нижнему регистру, убираем лишние пробелы
    normalized = ' '.join(name.lower().split())
    # Убираем кавычки
    normalized = normalized.replace('"', '').replace("'", "")
    # Убираем точки в конце и в середине
    normalized = normalized.replace('.', ' ').replace(',', ' ')
    normalized = ' '.join(normalized.split())  # Убираем лишние пробелы
    # Расшифровываем аббревиатуры
    normalized = expand_abbreviations(normalized)
    return normalized


def similarity(name1, name2):
    """Вычисляет схожесть двух названий (0.0 - 1.0)
    
    Учитывает:
    - Точное совпадение (после нормализации)
    - Вхождение одного названия в другое (например: "ИП Орлов" в "ИП Орлов Роман")
    - Совпадение ключевых слов
    - Схожесть по SequenceMatcher
    """
    if not name1 or not name2:
        return 0.0
    
    norm1 = normalize_club_name(name1)
    norm2 = normalize_club_name(name2)
    
    # Прямое сравнение
    if norm1 == norm2:
        return 1.0
    
    # Проверка на вхождение одного названия в другое
    # Если короткое название содержится в длинном, это очень высокая схожесть
    # Например: "ИП Орлов" в "ИП Орлов Роман"
    if norm1 in norm2 or norm2 in norm1:
        # Вычисляем соотношение длины короткого к длинному
        shorter = min(len(norm1), len(norm2))
        longer = max(len(norm1), len(norm2))
        # Если короткое составляет >70% длинного, считаем очень похожим
        if shorter / longer >= 0.70:
            # Дополнительно проверяем, что короткое - это не слишком маленькая часть
            # Минимум 5 символов для такого совпадения
            if shorter >= 5:
                return 0.95  # Очень высокая схожесть
    
    # Извлекаем ключевые слова
    key_words1 = extract_key_words(norm1)
    key_words2 = extract_key_words(norm2)
    
    # Если есть ключевые слова, проверяем их пересечение
    if key_words1 and key_words2:
        intersection = key_words1 & key_words2  # Пересечение множеств
        union = key_words1 | key_words2  # Объединение множеств
        
        if intersection:
            # Проверка: если все ключевые слова одного названия содержатся в другом
            # Это может означать, что одно является подразделением другого
            if key_words1.issubset(key_words2) or key_words2.issubset(key_words1):
                # Если хотя бы 2 ключевых слова совпадают, это очень похоже
                if len(intersection) >= 2:
                    return 0.93  # Очень высокая схожесть (подразделение)
            
            # Коэффициент Жаккара (пересечение / объединение)
            jaccard = len(intersection) / len(union) if union else 0.0
            
            # Если большинство ключевых слов совпадает
            if jaccard >= 0.7:
                return 0.95  # Очень высокая схожесть
            elif jaccard >= 0.5:
                return 0.88  # Высокая схожесть
            elif jaccard >= 0.3 or len(intersection) >= 2:
                # Если есть хотя бы 30% совпадений или 2+ общих слова
                # Дополнительно проверяем SequenceMatcher
                seq_sim = SequenceMatcher(None, norm1, norm2).ratio()
                # Повышаем схожесть, если есть общие ключевые слова
                if len(intersection) >= 2:
                    return max(0.82, seq_sim * 1.1)  # Немного увеличиваем схожесть
                return max(0.80, seq_sim)
    
    # Также проверяем начало названий - часто различаются только окончания
    # Например: "ИП Орлов" и "ИП Орлов Роман"
    words1 = norm1.split()
    words2 = norm2.split()
    
    if len(words1) >= 2 and len(words2) >= 2:
        # Сравниваем первые два слова
        prefix1 = ' '.join(words1[:2])
        prefix2 = ' '.join(words2[:2])
        if prefix1 == prefix2:
            # Если первые два слова совпадают, это очень похоже
            return 0.92
    
    # Используем SequenceMatcher для вычисления общей схожести
    return SequenceMatcher(None, norm1, norm2).ratio()


def create_backup():
    """Создает бэкап базы данных"""
    db_path = 'instance/figure_skating.db'
    backup_dir = 'backups'
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = f'before_merge_club_{timestamp}.db'
    backup_path = os.path.join(backup_dir, backup_file)
    
    shutil.copy2(db_path, backup_path)
    print(f"✅ Бэкап создан: {backup_path}\n")
    return backup_file


def merge_clubs(keep_club_id, remove_club_id, target_name=None):
    """Объединяет два клуба"""
    keep_club = Club.query.get(keep_club_id)
    remove_club = Club.query.get(remove_club_id)
    
    if not keep_club or not remove_club:
        return False
    
    # Обновляем название, если указано
    if target_name:
        keep_club.name = target_name
    
    # Подсчитываем спортсменов
    athletes_count = Athlete.query.filter_by(club_id=remove_club_id).count()
    
    # Переносим спортсменов
    if athletes_count > 0:
        Athlete.query.filter_by(club_id=remove_club_id).update({
            'club_id': keep_club_id
        })
    
    # Сохраняем информацию об удаляемом клубе
    removed_club_name = remove_club.name
    
    # Удаляем клуб
    db.session.delete(remove_club)
    
    return {
        'keep_club': keep_club,
        'removed_club_name': removed_club_name,
        'athletes_transferred': athletes_count
    }


def find_similar_clubs(club_id, min_similarity=0.65):
    """Находит похожие клубы для указанного клуба"""
    target_club = Club.query.get(club_id)
    if not target_club:
        return None, []
    
    all_clubs = Club.query.filter(Club.id != club_id).all()
    similar = []
    
    for club in all_clubs:
        sim = similarity(target_club.name, club.name)
        if sim >= min_similarity:
            athletes_count = Athlete.query.filter_by(club_id=club.id).count()
            similar.append({
                'club': club,
                'similarity': sim,
                'athletes_count': athletes_count
            })
    
    # Сортируем по схожести (от высокой к низкой)
    similar.sort(key=lambda x: x['similarity'], reverse=True)
    
    return target_club, similar


def interactive_merge_club():
    """Интерактивное объединение клуба"""
    
    with app.app_context():
        print("=" * 80)
        print("ИНТЕРАКТИВНОЕ ОБЪЕДИНЕНИЕ ШКОЛ/КЛУБОВ")
        print("=" * 80)
        print()
        print("Как использовать:")
        print("  1. Введите ID школы/клуба")
        print("  2. Увидите список похожих школ с процентами схожести")
        print("  3. Выберите номер или ID школы для объединения")
        print("  4. Выберите, какой клуб оставить (A или B)")
        print("  5. Все спортсмены будут перенесены, старый клуб удален")
        print()
        print("Для выхода введите 'exit' или 'quit'")
        print("Для пропуска текущего клуба введите 'skip'")
        print("=" * 80)
        print()
        
        while True:
            # Запрашиваем ID клуба
            club_id_input = input("Введите ID школы/клуба (или 'exit' для выхода): ").strip()
            
            if club_id_input.lower() in ['exit', 'quit', 'q']:
                print("Выход...")
                break
            
            try:
                club_id = int(club_id_input)
            except ValueError:
                print("❌ Введите числовой ID или 'exit' для выхода!")
                print()
                continue
            
            # Находим клуб
            target_club, similar_clubs = find_similar_clubs(club_id)
            
            if not target_club:
                print(f"❌ Клуб с ID {club_id} не найден!")
                print()
                continue
            
            # Показываем информацию о клубе
            athletes_count = Athlete.query.filter_by(club_id=club_id).count()
            
            print("\n" + "=" * 80)
            print(f"НАЙДЕН КЛУБ:")
            print("=" * 80)
            print(f"  ID: {target_club.id}")
            print(f"  Название: '{target_club.name}'")
            print(f"  Спортсменов: {athletes_count}")
            print(f"  External ID: {target_club.external_id if target_club.external_id else 'нет'}")
            print()
            
            if not similar_clubs:
                print("❌ Похожих клубов не найдено (схожесть < 65%)")
                print()
                continue
            
            # Показываем похожие клубы
            print("=" * 80)
            print(f"ПОХОЖИЕ КЛУБЫ (схожесть >= 65%):")
            print("=" * 80)
            print()
            
            for i, item in enumerate(similar_clubs, 1):
                club = item['club']
                sim = item['similarity']
                count = item['athletes_count']
                
                similarity_label = ""
                if sim >= 0.90:
                    similarity_label = " [ОЧЕНЬ ВЫСОКАЯ]"
                elif sim >= 0.80:
                    similarity_label = " [ВЫСОКАЯ]"
                else:
                    similarity_label = " [СРЕДНЯЯ]"
                
                print(f"  {i}. ID {club.id}: '{club.name}'")
                print(f"     Схожесть: {sim*100:.1f}%{similarity_label}")
                print(f"     Спортсменов: {count}")
                print(f"     External ID: {club.external_id if club.external_id else 'нет'}")
                print()
            
            # Предлагаем выбрать клуб для объединения
            print("=" * 80)
            print("ВАРИАНТЫ:")
            print("  • Введите номер (1, 2, 3...) - объединить с этим клубом")
            print("  • Введите ID клуба напрямую - объединить с этим ID")
            print("  • Введите 'skip' - пропустить и выбрать другой клуб")
            print()
            
            choice = input("Ваш выбор: ").strip()
            
            if choice.lower() == 'skip':
                print("⏭️  Пропущено")
                print()
                continue
            
            merge_with_id = None
            
            # Проверяем номер из списка
            if choice.isdigit() and 1 <= int(choice) <= len(similar_clubs):
                merge_with_id = similar_clubs[int(choice) - 1]['club'].id
            
            # Проверяем ID напрямую
            elif choice.isdigit():
                merge_with_id = int(choice)
                # Проверяем что клуб существует
                test_club = Club.query.get(merge_with_id)
                if not test_club:
                    print(f"❌ Клуб с ID {merge_with_id} не существует!")
                    print()
                    continue
            else:
                print("❌ Некорректный ввод! Введите номер, ID или 'skip'")
                print()
                continue
            
            if not merge_with_id:
                print("❌ Не указан клуб для объединения!")
                print()
                continue
            
            # Проверяем что клуб существует
            merge_club = Club.query.get(merge_with_id)
            if not merge_club:
                print(f"❌ Клуб с ID {merge_with_id} не найден!")
                print()
                continue
            
            # Определяем какой клуб остается, какой удаляется
            current_athletes = Athlete.query.filter_by(club_id=club_id).count()
            merge_athletes = Athlete.query.filter_by(club_id=merge_with_id).count()
            
            # Показываем информацию о клубах для выбора
            print("\n" + "=" * 80)
            print("ВЫБЕРИТЕ, КАКОЙ КЛУБ ОСТАВИТЬ:")
            print("=" * 80)
            print(f"  A. ID {club_id}: '{target_club.name}'")
            print(f"     Спортсменов: {current_athletes}")
            print()
            print(f"  B. ID {merge_with_id}: '{merge_club.name}'")
            print(f"     Спортсменов: {merge_athletes}")
            print()
            
            # Предлагаем выбор
            if current_athletes >= merge_athletes:
                default_choice = 'A'
                print(f"💡 Рекомендация: оставить A (больше спортсменов)")
            else:
                default_choice = 'B'
                print(f"💡 Рекомендация: оставить B (больше спортсменов)")
            
            choice_keep = input(f"Какой клуб оставить? (A/B, Enter для '{default_choice}'): ").strip().upper()
            
            if not choice_keep:
                choice_keep = default_choice
            
            if choice_keep == 'A':
                keep_club_id = club_id
                remove_club_id = merge_with_id
                keep_club_obj = target_club
                remove_club_obj = merge_club
                final_name = target_club.name
            elif choice_keep == 'B':
                keep_club_id = merge_with_id
                remove_club_id = club_id
                keep_club_obj = merge_club
                remove_club_obj = target_club
                final_name = merge_club.name
            else:
                print("❌ Некорректный выбор! Используется рекомендация.")
                if current_athletes >= merge_athletes:
                    keep_club_id = club_id
                    remove_club_id = merge_with_id
                    keep_club_obj = target_club
                    remove_club_obj = merge_club
                    final_name = target_club.name
                else:
                    keep_club_id = merge_with_id
                    remove_club_id = club_id
                    keep_club_obj = merge_club
                    remove_club_obj = target_club
                    final_name = merge_club.name
            
            # Показываем план объединения
            keep_athletes = Athlete.query.filter_by(club_id=keep_club_id).count()
            remove_athletes = Athlete.query.filter_by(club_id=remove_club_id).count()
            
            print("\n" + "=" * 80)
            print("ПЛАН ОБЪЕДИНЕНИЯ:")
            print("=" * 80)
            print(f"  ОСТАВИТЬ: ID {keep_club_id} - '{final_name}'")
            print(f"    Спортсменов: {keep_athletes}")
            print(f"  УДАЛИТЬ: ID {remove_club_id} - '{remove_club_obj.name}'")
            print(f"    Спортсменов: {remove_athletes}")
            print(f"  ИТОГО: {keep_athletes + remove_athletes} спортсменов в '{final_name}'")
            print()
            
            confirm = input("Объединить эти клубы? (yes/NO): ").strip().lower()
            
            if confirm != 'yes':
                print("❌ Отменено")
                print()
                continue
            
            # Создаем бэкап
            print("\nСоздание бэкапа...")
            backup_file = create_backup()
            
            # Объединяем
            print("Объединение...")
            result = merge_clubs(keep_club_id, remove_club_id, None)
            
            if not result:
                print("❌ Ошибка при объединении!")
                print()
                continue
            
            try:
                db.session.commit()
                
                print("\n" + "=" * 80)
                print("✅ УСПЕШНО ОБЪЕДИНЕНО!")
                print("=" * 80)
                print(f"Объединено в: '{result['keep_club'].name}' (ID {keep_club_id})")
                print(f"Удален клуб: '{result['removed_club_name']}' (ID {remove_club_id})")
                print(f"Перенесено спортсменов: {result['athletes_transferred']}")
                print(f"\n📦 Бэкап: backups/{backup_file}")
                print("=" * 80)
                
                # Проверяем результат
                final_count = Athlete.query.filter_by(club_id=keep_club_id).count()
                print(f"\n✅ Итоговое количество спортсменов в '{result['keep_club'].name}': {final_count}")
                print()
                
            except Exception as e:
                db.session.rollback()
                print(f"\n❌ ОШИБКА: {e}")
                print("Изменения отменены!")
                import traceback
                traceback.print_exc()
                print()
        
        print("\n✅ Работа завершена!")
        return 0


def main():
    """Основная функция"""
    try:
        return interactive_merge_club()
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

