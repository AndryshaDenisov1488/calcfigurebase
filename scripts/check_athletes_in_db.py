#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка списка «Фамилия Имя» по базе спортсменов (Athlete): кто есть в БД, кого нет.

Формат файла: одна строка — одно ФИО (Фамилия Имя или Фамилия Имя Отчество).
Порядок слов при сравнении не важен: нормализация по множеству слов.

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


def normalize_fio_key(s):
    """Нормализация ФИО для сравнения: нижний регистр, один пробел, ключ = кортеж отсортированных слов."""
    if not s or not isinstance(s, str):
        return None
    s = re.sub(r'\s+', ' ', s.strip()).lower()
    if not s:
        return None
    return tuple(sorted(s.split()))


def build_athlete_index(app):
    """Индекс: normalized_key -> [(athlete_id, full_name), ...] по Athlete."""
    index = {}
    with app.app_context():
        for a in Athlete.query.all():
            name = a.full_name
            key = normalize_fio_key(name)
            if key:
                index.setdefault(key, []).append((a.id, name))
    return index


def load_names(path):
    """Читает строки из файла: одна строка — одно ФИО. Пустые и комментарии пропускаются."""
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            yield line


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
    index = build_athlete_index(app)

    found = []
    not_found = []
    seen_key = set()
    for fio in names:
        key = normalize_fio_key(fio)
        if not key:
            continue
        if key in seen_key:
            continue
        seen_key.add(key)
        matches = index.get(key, [])
        if matches:
            for aid, db_name in matches:
                found.append((fio, aid, db_name))
        else:
            not_found.append(fio)

    # Вывод
    print("=" * 70)
    print("ПРОВЕРКА СПИСКА «ФАМИЛИЯ ИМЯ» ПО БАЗЕ СПОРТСМЕНОВ")
    print("=" * 70)
    print(f"Файл: {path}")
    print(f"Проверено уникальных ФИО: {len(found) + len(not_found)}")
    print(f"Найдено в БД: {len(found)}")
    print(f"Не найдено:   {len(not_found)}")
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
    print(f"Итого: найдено {len(found)}, не найдено {len(not_found)}")
    print("=" * 70)


if __name__ == '__main__':
    main()
