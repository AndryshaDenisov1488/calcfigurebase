#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Добавляет в таблицу event колонку exclude_free_from_reports (если её нет).

Запуск:
    python scripts/add_event_exclude_free_flag.py
"""

import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from app import app, db


def main():
    with app.app_context():
        dialect = db.engine.dialect.name

        if dialect == 'sqlite':
            # Для SQLite старых версий нет ADD COLUMN IF NOT EXISTS.
            cols = db.session.execute(db.text("PRAGMA table_info(event)")).fetchall()
            col_names = {row[1] for row in cols}  # row[1] = name
            if 'exclude_free_from_reports' not in col_names:
                db.session.execute(db.text("""
                    ALTER TABLE event
                    ADD COLUMN exclude_free_from_reports BOOLEAN NOT NULL DEFAULT 0
                """))
        else:
            # PostgreSQL / другие БД
            db.session.execute(db.text("""
                ALTER TABLE event
                ADD COLUMN IF NOT EXISTS exclude_free_from_reports BOOLEAN NOT NULL DEFAULT FALSE
            """))

        db.session.execute(db.text("""
            CREATE INDEX IF NOT EXISTS ix_event_exclude_free_from_reports
            ON event (exclude_free_from_reports)
        """))
        db.session.commit()
        print("OK: event.exclude_free_from_reports готово")


if __name__ == "__main__":
    main()

