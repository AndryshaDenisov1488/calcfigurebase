#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Удаление турнира по ID и всех связанных данных.
Использование: python scripts/delete_event_by_id.py 23
Запускать из корня проекта. На сервере: source .venv/bin/activate && python scripts/delete_event_by_id.py 23
"""

import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app_factory import create_app
from extensions import db
from models import Event, Category, Participant, CoachAssignment


def delete_event_by_id(event_id: int, backup: bool = True):
    """Удаляет турнир по ID и все связанные записи (категории, участники, выступления, элементы, CoachAssignment и т.д.)."""
    app = create_app()
    with app.app_context():
        event = Event.query.get(event_id)
        if not event:
            print(f"Турнир с ID {event_id} не найден.")
            return False

        categories = Category.query.filter_by(event_id=event_id).all()
        participants_count = Participant.query.filter_by(event_id=event_id).count()
        coach_assignments_count = CoachAssignment.query.filter_by(event_id=event_id).count()

        print("=" * 60)
        print("УДАЛЕНИЕ ТУРНИРА")
        print("=" * 60)
        print(f"ID: {event_id}")
        print(f"Название: {event.name}")
        print(f"Дата: {event.begin_date} — {event.end_date}")
        print(f"Категорий: {len(categories)}")
        print(f"Участников: {participants_count}")
        print(f"Назначений тренеров (CoachAssignment): {coach_assignments_count}")
        print("=" * 60)

        confirm = input("Удалить турнир и все связанные данные? (yes/NO): ").strip().lower()
        if confirm != "yes":
            print("Отменено.")
            return False

        if backup:
            import shutil
            from datetime import datetime
            db_path = app.config.get("SQLALCHEMY_DATABASE_URI", "").replace("sqlite:///", "")
            if db_path:
                full_db_path = os.path.join(project_root, db_path) if not os.path.isabs(db_path) else db_path
                if os.path.exists(full_db_path):
                    backup_dir = os.path.join(project_root, "backups")
                    os.makedirs(backup_dir, exist_ok=True)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup_file = os.path.join(backup_dir, f"before_delete_event_{event_id}_{timestamp}.db")
                    shutil.copy2(full_db_path, backup_file)
                    print(f"Бэкап: {backup_file}")

        # Сначала удаляем назначения тренеров по этому турниру (нет cascade со стороны Event)
        CoachAssignment.query.filter_by(event_id=event_id).delete()
        db.session.flush()
        # Затем удаляем сам турнир — каскадно удалятся Category, Participant, Segment, Performance, Element, ComponentScore, JudgePanel
        db.session.delete(event)
        db.session.commit()
        print("Турнир и все связанные данные удалены.")
        return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python scripts/delete_event_by_id.py <event_id>")
        print("Пример: python scripts/delete_event_by_id.py 23")
        sys.exit(1)
    try:
        eid = int(sys.argv[1])
    except ValueError:
        print("Ошибка: event_id должен быть числом.")
        sys.exit(1)
    no_backup = "--no-backup" in sys.argv
    ok = delete_event_by_id(eid, backup=not no_backup)
    sys.exit(0 if ok else 1)
