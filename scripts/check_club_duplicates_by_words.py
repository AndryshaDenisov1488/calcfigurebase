#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка дублирования клубов по совпадению нескольких одинаковых слов в названии.
Находит группы клубов, у которых в названиях совпадает не менее N слов (по умолчанию 2).
Запуск из корня проекта: python scripts/check_club_duplicates_by_words.py [--min-words N]
"""

import os
import re
import sys
import argparse

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app_factory import create_app
from extensions import db
from models import Club, Athlete


# Служебные слова, которые можно не учитывать при сравнении (опционально)
STOP_WORDS = {
    "ооо", "оао", "зао", "ип", "ао", "и", "в", "по", "им", "имени", "для", "на", "с",
    "№", "no", "n",  # номер
}


def normalize_word(w: str) -> str:
    """Нормализация одного слова: нижний регистр, только буквы/цифры."""
    if not w:
        return ""
    # Убираем пунктуацию по краям, оставляем буквы, цифры, дефис
    w = w.lower().strip()
    w = re.sub(r"^[^\w\-]+|[^\w\-]+$", "", w)
    return w


def words_from_name(name: str, exclude_stop: bool = True) -> set:
    """
    Извлекает множество слов из названия клуба.
    Слова нормализуются; при exclude_stop=True служебные слова не включаются.
    """
    if not name or not isinstance(name, str):
        return set()
    # Разбиваем по пробелам и возможным разделителям
    raw = re.sub(r"[,.;:!?()\[\]{}]", " ", name)
    tokens = raw.split()
    out = set()
    for t in tokens:
        word = normalize_word(t)
        if len(word) < 2:  # пропускаем слишком короткие
            continue
        if exclude_stop and word in STOP_WORDS:
            continue
        out.add(word)
    return out


def build_word_sets(clubs):
    """Для каждого клуба возвращает (club, set of words)."""
    result = []
    for club in clubs:
        ws = words_from_name(club.name or "")
        result.append((club, ws))
    return result


def find_groups_by_common_words(clubs_with_words, min_common_words: int):
    """
    Группирует клубы: два клуба в одной группе, если у них >= min_common_words общих слов.
    Возвращает список групп; каждая группа — список (club, set_of_words, common_words с другими в группе).
    """
    n = len(clubs_with_words)
    # Граф смежности: club_id -> set of club_id с достаточным числом общих слов
    adj = {c.id: set() for c, _ in clubs_with_words}
    # Пара (club_id, club_id) -> set of common words
    common = {}

    for i in range(n):
        c1, w1 = clubs_with_words[i]
        for j in range(i + 1, n):
            c2, w2 = clubs_with_words[j]
            inter = w1 & w2
            if len(inter) >= min_common_words:
                adj[c1.id].add(c2.id)
                adj[c2.id].add(c1.id)
                common[(c1.id, c2.id)] = inter

    # Поиск связных компонент (каждая компонента — группа дубликатов по словам)
    visited = set()

    def dfs(cid, comp):
        visited.add(cid)
        comp.add(cid)
        for neighbor in adj[cid]:
            if neighbor not in visited:
                dfs(neighbor, comp)

    components = []
    for c, _ in clubs_with_words:
        if c.id not in visited:
            comp = set()
            dfs(c.id, comp)
            if len(comp) >= 2:  # только группы из 2+ клубов
                components.append(comp)

    # Преобразуем в удобный вывод: для каждой группы — список (club, words, common_in_group)
    club_by_id = {c.id: c for c, _ in clubs_with_words}
    word_set_by_id = {c.id: w for c, w in clubs_with_words}

    groups_out = []
    for comp in components:
        comp_list = list(comp)
        # Общие слова по группе — объединение всех парных совпадений (причины объединения)
        common_in_group = set()
        for i, cid1 in enumerate(comp_list):
            for cid2 in comp_list[i + 1 :]:
                pair_common = common.get((cid1, cid2)) or common.get((cid2, cid1))
                if pair_common:
                    common_in_group |= pair_common
        group_entries = []
        for cid in comp_list:
            club = club_by_id[cid]
            words = word_set_by_id[cid]
            group_entries.append((club, words, common_in_group))
        groups_out.append(group_entries)
    return groups_out


def athlete_count_for_club(session, club_id: int) -> int:
    """Количество спортсменов в клубе."""
    return session.query(Athlete).filter(Athlete.club_id == club_id).count()


def main():
    parser = argparse.ArgumentParser(description="Поиск дубликатов клубов по совпадению слов в названии")
    parser.add_argument(
        "--min-words",
        type=int,
        default=2,
        metavar="N",
        help="Минимальное количество совпадающих слов для признания дубликатами (по умолчанию 2)",
    )
    parser.add_argument(
        "--no-stop-words",
        action="store_true",
        help="Учитывать служебные слова (ООО, ИП и т.д.) при сравнении",
    )
    args = parser.parse_args()
    min_common_words = max(1, args.min_words)

    app = create_app()
    with app.app_context():
        clubs = Club.query.order_by(Club.name).all()
        if not clubs:
            print("В базе нет клубов.")
            return

        # Собираем слова (при необходимости отключаем исключение стоп-слов через глобал/флаг)
        clubs_with_words = [(c, words_from_name(c.name or "", exclude_stop=not args.no_stop_words)) for c in clubs]
        # Убираем клубы без слов (или с одним словом — для них не найдём пару по 2+ словам)
        clubs_with_words = [(c, w) for c, w in clubs_with_words if len(w) >= 1]

        groups = find_groups_by_common_words(clubs_with_words, min_common_words)

        print("=" * 80)
        print("ПРОВЕРКА ДУБЛИРОВАНИЯ КЛУБОВ ПО СОВПАДЕНИЮ СЛОВ")
        print("=" * 80)
        print(f"Минимум совпадающих слов: {min_common_words}")
        print(f"Всего клубов в базе: {len(clubs)}")
        print(f"Найдено групп с дубликатами (по словам): {len(groups)}")
        print("=" * 80)

        if not groups:
            print("\nГрупп с совпадением нескольких слов не найдено.")
            return

        for idx, group in enumerate(groups, 1):
            common_words = group[0][2] if group else set()
            print(f"\n--- Группа {idx} (общие слова: {', '.join(sorted(common_words)) or '—'} ) ---")
            for club, words, _ in group:
                cnt = athlete_count_for_club(db.session, club.id)
                print(f"  ID {club.id}: \"{club.name}\"")
                print(f"         слова: {', '.join(sorted(words))}")
                print(f"         спортсменов: {cnt}")
        print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
