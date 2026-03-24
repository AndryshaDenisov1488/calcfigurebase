#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Добавляет в таблицу event колонку exclude_free_from_reports (если её нет).

Запуск:
    python scripts/add_event_exclude_free_flag.py
"""

from app import app, db


def main():
    with app.app_context():
        # Универсальный SQL для PostgreSQL
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

