#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Выводит и сохраняет в файл всех спортсменов, у кого дата рождения 01.01.yyyy
(часто подставная дата при неизвестной реальной).

Использование: python scripts/list_birth_date_0101.py [--output файл]
Запускать из корня проекта.
"""

import os
import sys
from datetime import datetime

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app import app
from models import Athlete, Participant, Event


def main():
    out_path = "birth_date_0101.txt"
    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        if idx + 1 < len(sys.argv):
            out_path = sys.argv[idx + 1]

    with app.app_context():
        # Все у кого дата рождения 01.01.yyyy (день=1, месяц=1)
        all_with_birth = Athlete.query.filter(Athlete.birth_date.isnot(None)).order_by(
            Athlete.birth_date.asc(), Athlete.full_name_xml.asc()
        ).all()
        athletes = [a for a in all_with_birth if a.birth_date and a.birth_date.day == 1 and a.birth_date.month == 1]

        lines = []
        lines.append("=" * 80)
        lines.append("Спортсмены с датой рождения 01.01.yyyy")
        lines.append(f"Дата запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Всего записей: {len(athletes)}")
        lines.append("=" * 80)

        for a in athletes:
            birth_s = a.birth_date.strftime("%d.%m.%Y") if a.birth_date else "—"
            fio = a.full_name
            lines.append("")
            lines.append(f"id={a.id}  |  ФИО: {fio}  |  дата рожд.: {birth_s}  |  пол: {a.gender or '—'}")
            # Участия: турнир и дата (уникальные по event_id)
            event_ids_seen = set()
            participations = []
            for p in a.participants:
                if p.event_id in event_ids_seen:
                    continue
                event_ids_seen.add(p.event_id)
                ev = p.event
                if ev:
                    date_str = ev.begin_date.strftime("%d.%m.%Y") if ev.begin_date else "—"
                    participations.append((ev.name or "—", date_str))
            participations.sort(key=lambda x: (x[1], x[0]))
            if participations:
                for ev_name, date_str in participations:
                    lines.append(f"    — {ev_name}  ({date_str})")
            else:
                lines.append("    — не участвовал")

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
