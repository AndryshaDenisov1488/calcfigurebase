#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка схожих названий клубов/школ
Находит клубы с похожими названиями, которые могут быть дубликатами
"""

import os
import sys

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


def check_similar_club_names():
    """Проверяет схожие названия клубов"""
    
    with app.app_context():
        print("=" * 80)
        print("ПРОВЕРКА СХОЖИХ НАЗВАНИЙ КЛУБОВ/ШКОЛ")
        print("=" * 80)
        print()
        print("Критерии схожести:")
        print("  ✅ Высокая схожесть (>90%) - вероятные дубликаты")
        print("  ⚠️  Средняя схожесть (80-90%) - требуют проверки")
        print("  ℹ️  Низкая схожесть (65-80%) - возможно разные клубы")
        print()
        print("Особые случаи:")
        print("  • Названия где одно содержит другое (например: 'ИП Орлов' и 'ИП Орлов Роман')")
        print("  • Названия с общим началом (первые 2 слова совпадают)")
        print("  • Аббревиатуры расшифровываются (например: 'КФК' = 'Клуб фигурного катания')")
        print("  • Сравнение ключевых слов для поиска связанных названий")
        print("=" * 80)
        print()
        
        # Получаем все клубы
        all_clubs = Club.query.all()
        total_clubs = len(all_clubs)
        
        print(f"📊 Всего клубов в базе: {total_clubs}")
        print()
        
        # Сравниваем все клубы попарно
        similar_groups = []
        processed = set()
        
        for i, club1 in enumerate(all_clubs):
            if club1.id in processed:
                continue
            
            # Ищем похожие клубы
            similar_clubs = [club1]
            
            for club2 in all_clubs[i+1:]:
                if club2.id in processed:
                    continue
                
                # Вычисляем схожесть
                sim = similarity(club1.name, club2.name)
                
                # Если схожесть > 65% - это потенциальный дубликат
                # Понижен порог для поиска большего количества похожих названий
                if sim > 0.65:
                    similar_clubs.append(club2)
                    processed.add(club2.id)
            
            # Если нашли похожие клубы (больше одного)
            if len(similar_clubs) > 1:
                # Вычисляем среднюю схожесть в группе
                total_sim = 0.0
                comparisons = 0
                for c1 in similar_clubs:
                    for c2 in similar_clubs:
                        if c1.id < c2.id:  # Избегаем двойного сравнения
                            total_sim += similarity(c1.name, c2.name)
                            comparisons += 1
                
                avg_sim = total_sim / comparisons if comparisons > 0 else 0.0
                
                similar_groups.append({
                    'clubs': similar_clubs,
                    'similarity': avg_sim
                })
                
                processed.add(club1.id)
        
        if not similar_groups:
            print("✅ Схожих названий клубов не найдено!")
            return 0
        
        # Сортируем по схожести (от высокой к низкой)
        similar_groups.sort(key=lambda x: x['similarity'], reverse=True)
        
        print(f"🔍 Найдено групп со схожими названиями: {len(similar_groups)}\n")
        print("=" * 80)
        
        # Выводим результаты
        high_similarity = []  # >90%
        medium_similarity = []  # 80-90%
        low_similarity = []  # 65-80%
        
        group_num = 0
        for group in similar_groups:
            group_num += 1
            clubs = group['clubs']
            avg_sim = group['similarity']
            
            # Вычисляем общее количество спортсменов
            total_athletes = 0
            for club in clubs:
                count = Athlete.query.filter_by(club_id=club.id).count()
                total_athletes += count
            
            if avg_sim > 0.90:
                high_similarity.append(group)
            elif avg_sim > 0.80:
                medium_similarity.append(group)
            else:
                low_similarity.append(group)
        
        # Выводим группы с высокой схожестью (вероятные дубликаты)
        if high_similarity:
            print("\n" + "=" * 80)
            print(f"✅ ВЫСОКАЯ СХОЖЕСТЬ (>90%) - ВЕРОЯТНЫЕ ДУБЛИКАТЫ: {len(high_similarity)}")
            print("=" * 80)
            
            for group in high_similarity:
                clubs = group['clubs']
                avg_sim = group['similarity']
                
                print(f"\n{'-' * 80}")
                print(f"Группа #{high_similarity.index(group) + 1} (схожесть: {avg_sim*100:.1f}%)")
                print(f"{'-' * 80}")
                
                for club in clubs:
                    athletes_count = Athlete.query.filter_by(club_id=club.id).count()
                    external_id = club.external_id if club.external_id else "нет"
                    print(f"  ID {club.id}: '{club.name}'")
                    print(f"    Спортсменов: {athletes_count}")
                    print(f"    External ID: {external_id}")
                    print()
        
        # Выводим группы со средней схожестью
        if medium_similarity:
            print("\n" + "=" * 80)
            print(f"⚠️  СРЕДНЯЯ СХОЖЕСТЬ (80-90%) - ТРЕБУЮТ ПРОВЕРКИ: {len(medium_similarity)}")
            print("=" * 80)
            
            for group in medium_similarity:
                clubs = group['clubs']
                avg_sim = group['similarity']
                
                print(f"\n{'-' * 80}")
                print(f"Группа #{medium_similarity.index(group) + 1} (схожесть: {avg_sim*100:.1f}%)")
                print(f"{'-' * 80}")
                
                for club in clubs:
                    athletes_count = Athlete.query.filter_by(club_id=club.id).count()
                    external_id = club.external_id if club.external_id else "нет"
                    print(f"  ID {club.id}: '{club.name}'")
                    print(f"    Спортсменов: {athletes_count}")
                    print(f"    External ID: {external_id}")
                    print()
        
        # Выводим группы с низкой схожестью (возможно разные клубы)
        if low_similarity:
            print("\n" + "=" * 80)
            print(f"ℹ️  НИЗКАЯ СХОЖЕСТЬ (65-80%) - ВОЗМОЖНО РАЗНЫЕ КЛУБЫ: {len(low_similarity)}")
            print("=" * 80)
            
            for group in low_similarity:
                clubs = group['clubs']
                avg_sim = group['similarity']
                
                print(f"\n{'-' * 80}")
                print(f"Группа #{low_similarity.index(group) + 1} (схожесть: {avg_sim*100:.1f}%)")
                print(f"{'-' * 80}")
                
                for club in clubs:
                    athletes_count = Athlete.query.filter_by(club_id=club.id).count()
                    external_id = club.external_id if club.external_id else "нет"
                    print(f"  ID {club.id}: '{club.name}'")
                    print(f"    Спортсменов: {athletes_count}")
                    print(f"    External ID: {external_id}")
                    print()
        
        # Итоги
        print("\n" + "=" * 80)
        print("ИТОГИ:")
        print("=" * 80)
        print(f"Всего групп со схожими названиями: {len(similar_groups)}")
        print(f"  • Высокая схожесть (>90%): {len(high_similarity)} групп")
        print(f"  • Средняя схожесть (80-90%): {len(medium_similarity)} групп")
        print(f"  • Низкая схожесть (65-80%): {len(low_similarity)} групп")
        print()
        print("💡 РЕКОМЕНДАЦИИ:")
        print("  • Группы с высокой схожестью (>90%) - вероятно, это дубликаты")
        print("  • Проверьте каждый случай вручную перед объединением")
        print("  • Для объединения используйте скрипт для объединения клубов")
        print("=" * 80)
        
        return 0


def main():
    """Основная функция"""
    try:
        return check_similar_club_names()
    except Exception as e:
        print(f"❌ Ошибка: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())

