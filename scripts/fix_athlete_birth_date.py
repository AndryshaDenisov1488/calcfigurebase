#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Изменить дату рождения спортсмена по ID."""

import os
import sys
from datetime import datetime

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app import app, db
from models import Athlete


def fix_birth_date(athlete_id: int, new_date_str: str) -> int:
    """athlete_id - ID спортсмена, new_date_str - дата в формате DD.MM.YYYY"""
    with app.app_context():
        athlete = Athlete.query.get(athlete_id)
        if not athlete:
            print(f"Спортсмен с ID {athlete_id} не найден.")
            return 1

        try:
            day, month, year = map(int, new_date_str.split('.'))
            new_date = datetime(year, month, day).date()
        except (ValueError, AttributeError) as e:
            print(f"Неверный формат даты: {new_date_str}. Ожидается DD.MM.YYYY")
            return 1

        old_date = athlete.birth_date
        athlete.birth_date = new_date
        db.session.commit()

        print(f"Готово. ID {athlete_id}: {athlete.full_name_xml}")
        print(f"  Дата: {old_date} -> {new_date}")
        return 0


def main():
    if len(sys.argv) < 3:
        print("Использование: python fix_athlete_birth_date.py АЙДИ ДАТА")
        print("Пример: python fix_athlete_birth_date.py 1109 02.09.2010")
        return 1
    return fix_birth_date(int(sys.argv[1]), sys.argv[2])


if __name__ == '__main__':
    sys.exit(main())
