#!/usr/bin/env python3
"""
Находит спортсменов с бесплатными стартами, которые не попадают в словарь разрядов.

Пример запуска на сервере:

    cd /var/www/calc.figurebase.ru
    source venv/bin/activate
    python3 scripts/list_free_rank_mismatches.py

Можно указать альтернативный путь к базе:

    python3 scripts/list_free_rank_mismatches.py --db path/to/figure_skating.db
"""

from __future__ import annotations

import argparse
import pathlib
import sqlite3
import sys
from collections import defaultdict

# Добавляем корень проекта в sys.path, чтобы можно было импортировать app.py
ROOT_DIR = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.rank_service import normalize_category_name, RANK_DICTIONARY  # type: ignore  # noqa: E402


def build_known_ranks() -> set[str]:
    """Формирует множество всех разрядов из словаря `RANK_DICTIONARY`."""
    known = set()
    for rank_data in RANK_DICTIONARY.values():
        genders = rank_data.get("genders")
        if genders:
            known.update(genders.values())
        else:
            base_name = rank_data.get("name")
            if base_name:
                known.add(base_name)
    return known


def fetch_free_participations(connection: sqlite3.Connection):
    query = """
        SELECT
            a.id AS athlete_id,
            TRIM(COALESCE(a.last_name, '') || ' ' || COALESCE(a.first_name, '')) AS athlete_name,
            e.name AS event_name,
            e.begin_date AS event_date,
            c.name AS category_name,
            c.gender AS category_gender,
            c.normalized_name AS normalized_name
        FROM participant p
        JOIN athlete a ON a.id = p.athlete_id
        JOIN event e ON e.id = p.event_id
        JOIN category c ON c.id = p.category_id
        WHERE p.pct_ppname = 'БЕСП'
        ORDER BY e.begin_date DESC, athlete_name
    """
    return connection.execute(query)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Показать бесплатные старты, которые не попадают в словарь разрядов."
    )
    parser.add_argument(
        "--db",
        default="instance/figure_skating.db",
        type=pathlib.Path,
        help="Путь к SQLite базе (по умолчанию instance/figure_skating.db)",
    )
    args = parser.parse_args(argv)

    if not args.db.exists():
        print(f"[!] Файл базы данных '{args.db}' не найден.")
        return 1

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    known_ranks = build_known_ranks()
    unknown_participations: list[sqlite3.Row] = []
    by_athlete: defaultdict[int, list[sqlite3.Row]] = defaultdict(list)

    try:
        for row in fetch_free_participations(conn):
            rank = row["normalized_name"] or normalize_category_name(
                row["category_name"], row["category_gender"]
            )
            if rank not in known_ranks:
                unknown_participations.append(row)
                by_athlete[row["athlete_id"]].append(row)
    finally:
        conn.close()

    unique_athletes = len(by_athlete)
    print(f"Бесплатных стартов вне словаря разрядов: {len(unknown_participations)}")
    print(f"Спортсменов затронуто: {unique_athletes}")
    print("-" * 90)

    for athlete_id, participations in sorted(
        by_athlete.items(), key=lambda item: (participations[0]["athlete_name"], item[0])
    ):
        athlete_name = participations[0]["athlete_name"] or "(без имени)"
        print(f"{athlete_id:6} | {athlete_name}")
        for row in participations:
            event_date = row["event_date"] or "Дата не указана"
            category_name = row["category_name"] or "(без категории)"
            normalized = row["normalized_name"] or "-"
            print(
                f"    • {event_date} — {row['event_name']} | Категория: {category_name} "
                f"| normalized: {normalized}"
            )
        print("-" * 90)

    if not unknown_participations:
        print("Все бесплатные старты сопоставлены с разрядами из словаря.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

