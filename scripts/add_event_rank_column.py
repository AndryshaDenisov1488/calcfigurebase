#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Добавляет в таблицу event колонку event_rank (если её нет).

Запуск:
    python scripts/add_event_rank_column.py
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
            cols = db.session.execute(db.text("PRAGMA table_info(event)")).fetchall()
            col_names = {row[1] for row in cols}
            if 'event_rank' not in col_names:
                db.session.execute(db.text("""
                    ALTER TABLE event
                    ADD COLUMN event_rank TEXT
                """))
        else:
            db.session.execute(db.text("""
                ALTER TABLE event
                ADD COLUMN IF NOT EXISTS event_rank VARCHAR(50)
            """))

        db.session.execute(db.text("""
            CREATE INDEX IF NOT EXISTS ix_event_event_rank
            ON event (event_rank)
        """))
        db.session.commit()
        print("OK: event.event_rank готово")


if __name__ == "__main__":
    main()

