#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка списка «Фамилия Имя» (1617022026ustinov) по базе спортсменов (Athlete).

Список: scripts/1617022026ustinov.txt
Совпадение: по 2 словам (фамилия + имя) с полным ФИО в БД.

Использование (из корня проекта):
  python scripts/1617022026ustinov.py
"""

import os
import re
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app_factory import create_app
from extensions import db
from models import Athlete

LIST_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '1617022026ustinov.txt')


def normalize_words(s):
    if not s or not isinstance(s, str):
        return []
    s = re.sub(r'\s+', ' ', s.strip()).lower()
    if not s:
        return []
    return s.split()


def list_entry_to_key(s):
    words = normalize_words(s)
    if len(words) < 2:
        return None
    return frozenset(words[:2])


def athlete_name_words(name):
    return set(normalize_words(name))


def load_names(path):
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            yield line


def find_athletes_by_two_words(athletes_data, list_key):
    return [
        (aid, db_name)
        for aid, db_name, name_words in athletes_data
        if list_key <= name_words
    ]


def main():
    if not os.path.isfile(LIST_FILE):
        print(f"Файл не найден: {LIST_FILE}")
        sys.exit(1)

    names = list(load_names(LIST_FILE))
    if not names:
        print("В файле нет строк с ФИО.")
        sys.exit(1)

    app = create_app()
    with app.app_context():
        athletes_data = []
        for a in Athlete.query.all():
            name = a.full_name
            words = athlete_name_words(name)
            if words:
                athletes_data.append((a.id, name, words))

    found = []
    not_found = []
    seen_key = set()
    for fio in names:
        key = list_entry_to_key(fio)
        if not key:
            continue
        if key in seen_key:
            continue
        seen_key.add(key)
        matches = find_athletes_by_two_words(athletes_data, key)
        if matches:
            for aid, db_name in matches:
                found.append((fio, aid, db_name))
        else:
            not_found.append(fio)

    n_entries_found = len(set(fio for fio, _, _ in found))
    print("=" * 70)
    print("ПРОВЕРКА СПИСКА 1617022026ustinov ПО БАЗЕ (ФАМИЛИЯ + ИМЯ)")
    print("=" * 70)
    print(f"Файл: {LIST_FILE}")
    print(f"Проверено уникальных записей: {len(found) + len(not_found)}")
    print(f"Найдено в БД: {n_entries_found}")
    print(f"Не найдено: {len(not_found)}")
    print("=" * 70)

    if found:
        print("\n--- В БД есть ---")
        for fio, aid, db_name in found:
            print(f"  {fio}  ->  id={aid}: {db_name}")

    if not_found:
        print("\n--- Нет в БД ---")
        for fio in not_found:
            print(f"  {fio}")

    print("\n" + "=" * 70)
    print(f"Итого: найдено {n_entries_found}, не найдено {len(not_found)}")
    print("=" * 70)


if __name__ == '__main__':
    main()
