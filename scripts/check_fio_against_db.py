#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка списка ФИО по базе: есть ли совпадения среди спортсменов (Athlete),
судей (Judge) и тренеров (Coach).

Список ФИО читается из файла (по умолчанию scripts/fio_list.txt).
Формат: одна строка — одно ФИО или пара "ФИО1 / ФИО2" (проверяются оба).
Порядок слов не важен: "Фамилия Имя Отчество" и "Имя Отчество Фамилия"
считаются одним и тем же человеком.

Использование:
  python scripts/check_fio_against_db.py [путь_к_файлу]
  python scripts/check_fio_against_db.py   # берёт scripts/fio_list.txt

Запуск из корня проекта. На сервере: source .venv/bin/activate && python scripts/check_fio_against_db.py
"""

import os
import re
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app_factory import create_app
from extensions import db
from models import Athlete, Judge, Coach


def normalize_fio_key(s):
    """Нормализация ФИО для сравнения: нижний регистр, один пробел между словами, ключ = кортеж слов.
    Так 'Абаркина Мария Алексеевна' и 'Мария Алексеевна Абаркина' дают один ключ."""
    if not s or not isinstance(s, str):
        return None
    s = re.sub(r'\s+', ' ', s.strip()).lower()
    if not s:
        return None
    return tuple(sorted(s.split()))


def build_db_index(app):
    """Строит индекс: normalized_key -> [(source, id, display_name), ...]"""
    index = {}
    with app.app_context():
        for a in Athlete.query.all():
            name = a.full_name
            key = normalize_fio_key(name)
            if key:
                index.setdefault(key, []).append(('Athlete', a.id, name))
        for j in Judge.query.all():
            name = (j.full_name_xml or '').strip() or ' '.join(filter(None, [j.last_name, j.first_name]))
            key = normalize_fio_key(name)
            if key:
                index.setdefault(key, []).append(('Judge', j.id, name))
        for c in Coach.query.all():
            name = c.name or ''
            key = normalize_fio_key(name)
            if key:
                index.setdefault(key, []).append(('Coach', c.id, name))
    return index


def check_one_fio(fio, index):
    """Возвращает список совпадений: [(source, id, display_name), ...] или []."""
    key = normalize_fio_key(fio)
    if not key:
        return []
    return index.get(key, [])


def load_fio_lines(path):
    """Читает строки из файла, пропускает пустые и заголовок 'ФИО'."""
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line == 'ФИО':
                continue
            yield line


def main():
    default_path = os.path.join(project_root, 'scripts', 'fio_list.txt')
    path = sys.argv[1] if len(sys.argv) > 1 else default_path
    if not os.path.isfile(path):
        print(f"Файл не найден: {path}")
        sys.exit(1)

    app = create_app()
    index = build_db_index(app)
    total_checked = 0
    found_count = 0
    not_found = []
    found_details = []

    for raw_line in load_fio_lines(path):
        if ' / ' in raw_line:
            parts = [p.strip() for p in raw_line.split(' / ', 1)]
        else:
            parts = [raw_line]
        for fio in parts:
            if not fio:
                continue
            total_checked += 1
            matches = check_one_fio(fio, index)
            if matches:
                found_count += 1
                for src, sid, dname in matches:
                    found_details.append((fio, 'да', src, sid, dname))
            else:
                not_found.append(fio)

    # Вывод
    print("=" * 80)
    print("ПРОВЕРКА ФИО ПО БАЗЕ")
    print("=" * 80)
    print(f"Файл списка: {path}")
    print(f"Проверено ФИО: {total_checked}")
    print(f"Найдено в БД: {found_count}")
    print(f"Не найдено:   {len(not_found)}")
    print("=" * 80)

    if found_details:
        print("\n--- Найденные в БД ---")
        for fio, status, source, sid, dname in found_details:
            print(f"  {fio}")
            print(f"    -> {source} id={sid}: {dname}")

    if not_found:
        print("\n--- Не найдены в БД ---")
        for fio in not_found:
            print(f"  {fio}")

    # Краткая сводка в конец
    print("\n" + "=" * 80)
    print(f"Итого: найдено {found_count}, не найдено {len(not_found)} из {total_checked}")
    print("=" * 80)


if __name__ == '__main__':
    main()
