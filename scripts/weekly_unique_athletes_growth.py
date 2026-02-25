#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Отчёт по приросту количества уникальных спортсменов по неделям.

Идея:
- считаем УНИКАЛЬНЫХ спортсменов так же, как в листе «Общая статистика»:
  исключаем МС/КМС, смотрим только разряды с 1 сп до 3 юношеского (и прочие, кроме МС/КМС).
- для каждой недели (ISO-неделя по дате начала турнира Event.begin_date)
  считаем:
    * total_unique — сколько разных спортсменов уже участвовали к концу этой недели (накопительно с начала сезона/базы)
    * weekly_growth — прирост относительно предыдущей недели

Вывод:
- текстовый отчёт weekly_unique_athletes_growth.txt
- CSV-файл weekly_unique_athletes_growth.csv (можно открыть в Google Sheets / Excel)

Запускать из корня проекта:
    python scripts/weekly_unique_athletes_growth.py
"""

import csv
import os
import sys
from collections import defaultdict
from datetime import datetime, date

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app import app, db  # noqa: E402
from models import Event, Category, Participant  # noqa: E402


def get_week_key(d: date):
    """Возвращает (year, week) для ISO-недели."""
    iso_year, iso_week, _ = d.isocalendar()
    return iso_year, iso_week


def get_monday_of_week(iso_year: int, iso_week: int) -> date:
    """Грубое вычисление понедельника ISO-недели (для отображения).

    Не претендует на идеальную точность для граничных случаев годов,
    но для отчёта достаточно.
    """
    # Берём 4 января как «опорную» (по ISO это всегда неделя 1)
    d = date(iso_year, 1, 4)
    # Смещаем к понедельнику этой недели
    d = d.replace()  # просто чтобы явно использовать copy
    while d.weekday() != 0:
        d = d.replace(day=d.day - 1)
    # Добавляем (week-1) недель
    return d.fromordinal(d.toordinal() + (iso_week - 1) * 7)


def collect_weekly_unique_athletes():
    """Собирает по неделям множества уникальных athlete_id (с учётом фильтров по разрядам)."""
    # Разряды, которые нужно исключить из отчёта (МС и КМС) — те же, что в get_summary_statistics_data
    excluded_ranks = {
        'МС, Женщины',
        'МС, Мужчины',
        'МС, Пары',
        'МС, Танцы',
        'КМС, Девушки',
        'КМС, Юноши',
        'КМС, Пары',
        'КМС, Танцы',
    }

    week_to_athletes: dict[tuple[int, int], set[int]] = defaultdict(set)

    # Берём всех участников с датами турниров и разрядом
    rows = (
        db.session.query(
            Participant.athlete_id,
            Event.begin_date.label("event_date"),
            Category.normalized_name.label("rank"),
        )
        .join(Category, Participant.category_id == Category.id)
        .join(Event, Participant.event_id == Event.id)
        .filter(
            Event.begin_date.isnot(None),
            db.or_(
                Category.normalized_name.is_(None),
                Category.normalized_name.notin_(excluded_ranks),
            ),
        )
        .all()
    )

    for row in rows:
        event_date = row.event_date
        if not event_date:
            continue
        key = get_week_key(event_date)
        week_to_athletes[key].add(row.athlete_id)

    return week_to_athletes


def build_growth_table(week_to_athletes: dict[tuple[int, int], set[int]]):
    """Строит таблицу по неделям: (year, week, monday_date, total_unique, weekly_growth)."""
    all_weeks = sorted(week_to_athletes.keys())
    seen_athletes: set[int] = set()
    result = []
    prev_total = 0

    for (iso_year, iso_week) in all_weeks:
        week_athletes = week_to_athletes[(iso_year, iso_week)]
        seen_athletes |= week_athletes
        total_unique = len(seen_athletes)
        weekly_growth = total_unique - prev_total
        prev_total = total_unique
        monday = get_monday_of_week(iso_year, iso_week)
        result.append(
            {
                "year": iso_year,
                "week": iso_week,
                "monday": monday,
                "total_unique": total_unique,
                "weekly_growth": weekly_growth,
            }
        )

    return result


def main():
    with app.app_context():
        week_to_athletes = collect_weekly_unique_athletes()
        if not week_to_athletes:
            print("Нет данных для отчёта (week_to_athletes пуст).")
            return 0

        table = build_growth_table(week_to_athletes)

        # Текстовый отчёт
        lines = []
        lines.append("=" * 80)
        lines.append("Прирост уникальных спортсменов по неделям (без МС/КМС)")
        lines.append(f"Дата формирования: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Количество недель в отчёте: {len(table)}")
        lines.append("=" * 80)
        lines.append("")
        lines.append("Год-Неделя | Понедельник недели | Уникальных всего | Прирост за неделю")
        lines.append("-" * 80)

        for row in table:
            week_label = f"{row['year']}-W{row['week']:02d}"
            monday_str = row["monday"].strftime("%d.%m.%Y")
            lines.append(
                f"{week_label:10s} | {monday_str:17s} | {row['total_unique']:16d} | {row['weekly_growth']:16d}"
            )

        txt_path = os.path.join(project_root, "weekly_unique_athletes_growth.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        print("\n".join(lines))
        print("\nСохранено в:", txt_path)

        # CSV для импорта в Google Sheets / Excel
        csv_path = os.path.join(project_root, "weekly_unique_athletes_growth.csv")
        with open(csv_path, "w", newline="", encoding="utf-8") as f_csv:
            writer = csv.writer(f_csv, delimiter=";")
            writer.writerow(
                [
                    "year",
                    "week",
                    "monday_date",
                    "total_unique_athletes",
                    "weekly_growth",
                ]
            )
            for row in table:
                writer.writerow(
                    [
                        row["year"],
                        row["week"],
                        row["monday"].strftime("%Y-%m-%d"),
                        row["total_unique"],
                        row["weekly_growth"],
                    ]
                )

        print("CSV сохранён в:", csv_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())

