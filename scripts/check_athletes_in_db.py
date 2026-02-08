#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка списка «Фамилия Имя» (2 слова) по базе спортсменов (Athlete).

В списке — только фамилия и имя. В БД хранится полное ФИО (с отчеством или без).
Совпадение: оба слова из строки списка должны входить в ФИО из БД (по 2 словам).

Формат файла: одна строка — «Фамилия Имя».

Использование:
  python scripts/check_athletes_in_db.py [путь_к_файлу]
  python scripts/check_athletes_in_db.py   # по умолчанию scripts/athlete_names_list.txt

Запуск из корня проекта.
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


def normalize_words(s):
    """Нормализация строки: нижний регистр, один пробел между словами, возврат списка слов."""
    if not s or not isinstance(s, str):
        return []
    s = re.sub(r'\s+', ' ', s.strip()).lower()
    if not s:
        return []
    return s.split()


def list_entry_to_key(s):
    """Из строки списка (Фамилия Имя) — множество из 2 слов для сопоставления."""
    words = normalize_words(s)
    if len(words) < 2:
        return None
    # Берём только первые 2 слова (фамилия, имя); лишние отбрасываем
    return frozenset(words[:2])


def athlete_name_words(name):
    """Из полного ФИО из БД — множество слов (2 или 3: фамилия, имя, отчество)."""
    return set(normalize_words(name))


def load_names(path):
    """Читает строки из файла: одна строка — «Фамилия Имя». Пустые и комментарии пропускаются."""
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            yield line


def find_athletes_by_two_words(athletes_data, list_key):
    """Найти всех спортсменов, у которых в ФИО есть оба слова из list_key."""
    return [
        (aid, db_name)
        for aid, db_name, name_words in athletes_data
        if list_key <= name_words
    ]


def main():
    default_path = os.path.join(project_root, 'scripts', 'athlete_names_list.txt')
    path = sys.argv[1] if len(sys.argv) > 1 else default_path
    if not os.path.isfile(path):
        print(f"Файл не найден: {path}")
        sys.exit(1)

    names = list(load_names(path))
    if not names:
        print("В файле нет строк с ФИО.")
        sys.exit(1)

    app = create_app()
    # Список (athlete_id, full_name, set слов из ФИО) по всем спортсменам
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
    # Вывод
    print("=" * 70)
    print("ПРОВЕРКА СПИСКА «ФАМИЛИЯ ИМЯ» ПО БАЗЕ (СОПОСТАВЛЕНИЕ ПО 2 СЛОВАМ)")
    print("=" * 70)
    print(f"Файл: {path}")
    print(f"Проверено уникальных записей (Фамилия Имя): {len(found) + len(not_found)}")
    print(f"Найдено в БД (есть совпадение по 2 словам): {n_entries_found}")
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
    print(f"Итого: найдено {n_entries_found} записей из списка, не найдено {len(not_found)}")
    print("=" * 70)


if __name__ == '__main__':
    main()
