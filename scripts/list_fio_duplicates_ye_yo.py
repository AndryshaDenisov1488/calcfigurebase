#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Выводит и сохраняет в файл всех спортсменов, у кого полностью совпадает ФИО
при учёте Е и Ё как одной буквы (нормализация: Ё -> Е).

Использование: python scripts/list_fio_duplicates_ye_yo.py [--output файл]
Запускать из корня проекта.
"""

import os
import sys
from collections import defaultdict
from datetime import datetime

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app import app, db
from models import Athlete


def normalize_fio_for_compare(name):
    """Нормализует ФИО для сравнения: Е и Ё считаются одной буквой, пробелы схлопываются."""
    if not name or not isinstance(name, str):
        return ""
    s = " ".join((name or "").strip().split())
    return s.replace("Ё", "Е").replace("ё", "е")


def main():
    out_path = "fio_duplicates_ye_yo.txt"
    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        if idx + 1 < len(sys.argv):
            out_path = sys.argv[idx + 1]

    with app.app_context():
        athletes = Athlete.query.all()
        by_normalized = defaultdict(list)
        for a in athletes:
            fio = a.full_name
            key = normalize_fio_for_compare(fio)
            if not key:
                continue
            by_normalized[key].append((a.id, fio, a.birth_date, a.gender))

        # Только группы, где больше одного человека
        duplicates = {k: v for k, v in by_normalized.items() if len(v) > 1}
        num_groups = len(duplicates)
        num_duplicate_records = sum(len(v) for v in duplicates.values())
        lines = []
        lines.append("=" * 80)
        lines.append("Дубликаты ФИО (Е и Ё считаются одной буквой)")
        lines.append(f"Дата запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Групп с дубликатами: {num_groups}")
        lines.append(f"Всего записей-дубликатов: {num_duplicate_records}")
        lines.append("=" * 80)

        for norm_fio in sorted(duplicates.keys()):
            group = duplicates[norm_fio]
            lines.append("")
            lines.append(f"ФИО (нормализовано): {norm_fio}")
            lines.append(f"  Записей: {len(group)}")
            for aid, fio, birth_date, gender in sorted(group, key=lambda x: (x[1], x[0])):
                birth_str = birth_date.strftime("%d.%m.%Y") if birth_date else "—"
                lines.append(f"  id={aid}: {fio}  |  дата рожд.: {birth_str}  |  пол: {gender or '—'}")
            lines.append("")

        text = "\n".join(lines)
        print(text)

        abs_path = os.path.join(project_root, out_path) if not os.path.isabs(out_path) else out_path
        os.makedirs(os.path.dirname(abs_path) or ".", exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(text)
        print("=" * 80)
        print(f"Результат сохранён: {abs_path}")
        print("=" * 80)


if __name__ == "__main__":
    main()
