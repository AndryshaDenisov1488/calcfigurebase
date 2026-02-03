#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка спортсменов из списка «Организация + ФИО» по БД (только Athlete).
Организации (школы) не учитываются — проверяется только наличие ФИО в базе спортсменов.

Формат файла: заголовки организаций (без отступа), под каждым — ФИО с отступом (2 пробела):
  Организация
  АНО ДО "АСКК" (...)
    Абалмазова Кристина Алексеевна
    Журавская Таисия Владимировна
  ГБУ ДО МАФКК (...)
    Абаркина Мария Алексеевна

Извлекаются только строки с отступом (ФИО). Порядок слов не важен при сравнении.

Использование:
  python scripts/check_athletes_from_org_list.py [путь_к_файлу]
  python scripts/check_athletes_from_org_list.py   # по умолчанию scripts/org_list.txt

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
    """Нормализация ФИО для сравнения: ключ = кортеж слов (без учёта порядка)."""
    if not s or not isinstance(s, str):
        return None
    s = re.sub(r'\s+', ' ', s.strip()).lower()
    if not s:
        return None
    return tuple(sorted(s.split()))


def extract_fio_from_org_list(path):
    """
    Читает файл в формате «организация — список ФИО с отступом».
    Возвращает список уникальных ФИО (строки, начинающиеся с 2+ пробелов).
    """
    seen = set()
    result = []
    org_markers = ('ооо', 'ано', 'гбу', 'ип ', 'сш ', 'сшор', 'мкш', 'ск «', 'црс', 'цст', 'афк', 'арена', 'школа', 'спортивный', 'шфк', 'до "', '«', '»', '(', ')')
    with open(path, 'r', encoding='utf-8') as f:
        for raw in f:
            stripped = raw.strip()
            if not stripped:
                continue
            # Строки с отступом (2+ пробела) — это ФИО спортсменов
            if raw.startswith('  ') and len(stripped) > 2:
                # Не считать организацией строку, похожую на название (скобки, маркеры)
                low = stripped.lower()
                if any(m in low for m in org_markers) and ('(' in stripped or '«' in stripped):
                    continue
                key = normalize_fio_key(stripped)
                if key and key not in seen:
                    seen.add(key)
                    result.append(stripped)
    return result


def build_athlete_index(app):
    """Индекс: normalized_key -> [(athlete_id, full_name), ...] только по Athlete."""
    index = {}
    with app.app_context():
        for a in Athlete.query.all():
            name = a.full_name
            key = normalize_fio_key(name)
            if key:
                index.setdefault(key, []).append((a.id, name))
    return index


def main():
    default_path = os.path.join(project_root, 'scripts', 'org_list.txt')
    path = sys.argv[1] if len(sys.argv) > 1 else default_path
    if not os.path.isfile(path):
        print(f"Файл не найден: {path}")
        print("Создайте файл со списком (организация, затем с отступом ФИО) или укажите путь.")
        sys.exit(1)

    fio_list = extract_fio_from_org_list(path)
    if not fio_list:
        print("В файле не найдено ни одного ФИО (ожидаются строки с отступом 2 пробела).")
        sys.exit(1)

    app = create_app()
    index = build_athlete_index(app)
    found = []
    not_found = []

    for fio in fio_list:
        key = normalize_fio_key(fio)
        matches = index.get(key, []) if key else []
        if matches:
            for aid, db_name in matches:
                found.append((fio, aid, db_name))
        else:
            not_found.append(fio)

    # Вывод
    print("=" * 70)
    print("ПРОВЕРКА СПОРТСМЕНОВ ИЗ СПИСКА (ОРГАНИЗАЦИИ) ПО БД")
    print("=" * 70)
    print(f"Файл: {path}")
    print(f"Извлечено ФИО: {len(fio_list)}")
    print(f"Найдено в БД (Athlete): {len(found)}")
    print(f"Не найдено: {len(not_found)}")
    print("=" * 70)

    if found:
        print("\n--- Найдены в БД ---")
        for fio, aid, db_name in found:
            print(f"  {fio}  -> Athlete id={aid}: {db_name}")

    if not_found:
        print("\n--- Не найдены в БД ---")
        for fio in not_found:
            print(f"  {fio}")

    print("\n" + "=" * 70)
    print(f"Итого: найдено {len(found)}, не найдено {len(not_found)} из {len(fio_list)}")
    print("=" * 70)


if __name__ == '__main__':
    main()
