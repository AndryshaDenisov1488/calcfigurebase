#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Пакетное объединение спортсменов: список пар (удалить_ID, оставить_ID).
Один бэкап в начале, затем все объединения подряд.

Использование: python scripts/merge_athletes_batch.py
Запускать из корня проекта.
"""

import os
import sys
import shutil
from datetime import datetime

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app import app, db
from models import Athlete, Participant, CoachAssignment

# Пары: (удалить_id, оставить_id) — объединить удаляемого в оставляемого
MERGE_PAIRS = [
    (1674, 160),
    (1244, 630),
    (374, 1602),
    (1247, 635),
    (354, 110),
    (2490, 1930),
    (1219, 37),
    (1248, 636),
    (1638, 500),
    (719, 569),
    (1722, 210),
    (2140, 987),
    (1253, 646),
    (502, 2453),
    (1387, 15),
    (1249, 639),
    (1350, 163),
]


def create_backup():
    """Создаёт один бэкап БД."""
    db_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    db_path = db_uri.replace("sqlite:///", "").strip()
    if not db_path:
        db_path = "instance/figure_skating.db"
    if not os.path.isabs(db_path):
        db_path = os.path.join(project_root, db_path)
    if not os.path.exists(db_path):
        for fallback in ("instance/figure_skating.db", "instance/figure_skating"):
            p = os.path.join(project_root, fallback)
            if os.path.exists(p):
                db_path = p
                break
        else:
            return None
    backup_dir = os.path.join(project_root, "backups")
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(backup_dir, f"before_merge_batch_{timestamp}.db")
    try:
        shutil.copy2(db_path, backup_file)
        return backup_file
    except Exception:
        return None


def merge_one(keep_id, remove_id):
    """Объединяет remove_id в keep_id. Возвращает True при успехе."""
    keep = Athlete.query.get(keep_id)
    remove = Athlete.query.get(remove_id)
    if not keep:
        print(f"  ❌ Не найден оставляемый id={keep_id}")
        return False
    if not remove:
        print(f"  ❌ Не найден удаляемый id={remove_id}")
        return False
    # Конфликт (event_id, category_id)?
    remove_parts = Participant.query.filter_by(athlete_id=remove_id).all()
    for p in remove_parts:
        if Participant.query.filter_by(athlete_id=keep_id, event_id=p.event_id, category_id=p.category_id).first():
            print(f"  ❌ Конфликт: id={remove_id} и id={keep_id} в одном (event_id={p.event_id}, category_id={p.category_id})")
            return False
    # Перенос
    Participant.query.filter_by(athlete_id=remove_id).update({"athlete_id": keep_id})
    CoachAssignment.query.filter_by(athlete_id=remove_id).update({"athlete_id": keep_id})
    # Более полное имя
    kf = keep.full_name_xml or ""
    rf = remove.full_name_xml or ""
    if len(rf) > len(kf):
        keep.full_name_xml = rf
    db.session.delete(remove)
    db.session.commit()
    return True


def main():
    print("=" * 60)
    print("Пакетное объединение спортсменов")
    print("=" * 60)
    for remove_id, keep_id in MERGE_PAIRS:
        print(f"  {remove_id} → {keep_id}")
    print("=" * 60)

    confirm = input("Создать бэкап и выполнить все объединения? (yes/NO): ").strip().lower()
    if confirm != "yes":
        print("Отменено.")
        return 0

    with app.app_context():
        backup_path = create_backup()
        if not backup_path:
            print("❌ Не удалось создать бэкап. Отмена.")
            return 1
        print(f"✅ Бэкап: {backup_path}\n")

        ok = 0
        fail = 0
        for remove_id, keep_id in MERGE_PAIRS:
            print(f"Объединяю {remove_id} → {keep_id} ... ", end="", flush=True)
            try:
                if merge_one(keep_id, remove_id):
                    print("OK")
                    ok += 1
                else:
                    fail += 1
            except Exception as e:
                db.session.rollback()
                print(f"Ошибка: {e}")
                fail += 1

        print()
        print("=" * 60)
        print(f"Готово: успешно {ok}, ошибок {fail}")
        print("=" * 60)
        return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
