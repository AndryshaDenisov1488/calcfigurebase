#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Удаляет указанных спортсменов и их школу (клуб).
Сначала удаляются привязки тренеров (CoachAssignment), затем спортсмены (каскадно — участия и т.д.),
затем у остальных спортсменов школы снимается привязка к клубу (если есть), затем удаляется клуб.

Использование: python scripts/delete_athletes_and_club.py
Запускать из корня проекта. ID спортсменов и клуба заданы в скрипте.
"""

import os
import sys
import shutil
from datetime import datetime

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app import app, db
from models import Athlete, Participant, CoachAssignment, Club

ATHLETE_IDS_TO_DELETE = [143, 119]
CLUB_ID_TO_DELETE = 15


def create_backup():
    """Создаёт бэкап БД."""
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
    backup_file = os.path.join(backup_dir, f"before_delete_athletes_club_{timestamp}.db")
    try:
        shutil.copy2(db_path, backup_file)
        return backup_file
    except Exception:
        return None


def main():
    with app.app_context():
        athletes = [Athlete.query.get(aid) for aid in ATHLETE_IDS_TO_DELETE]
        club = Club.query.get(CLUB_ID_TO_DELETE)

        print("=" * 60)
        print("Удаление спортсменов и школы")
        print("=" * 60)
        for aid in ATHLETE_IDS_TO_DELETE:
            a = Athlete.query.get(aid)
            if a:
                print(f"  Спортсмен id={aid}: {a.full_name} (клуб id={a.club_id})")
            else:
                print(f"  Спортсмен id={aid}: не найден")
        if club:
            remaining = Athlete.query.filter_by(club_id=CLUB_ID_TO_DELETE).count()
            print(f"  Школа id={CLUB_ID_TO_DELETE}: {club.name} (спортсменов в ней: {remaining})")
        else:
            print(f"  Школа id={CLUB_ID_TO_DELETE}: не найдена")
        print("=" * 60)

        confirm = input("Создать бэкап и удалить? (yes/NO): ").strip().lower()
        if confirm != "yes":
            print("Отменено.")
            return 0

        backup_path = create_backup()
        if not backup_path:
            print("❌ Не удалось создать бэкап. Отмена.")
            return 1
        print(f"✅ Бэкап: {backup_path}\n")

        try:
            # 1) Удалить CoachAssignment для этих спортсменов
            for aid in ATHLETE_IDS_TO_DELETE:
                CoachAssignment.query.filter_by(athlete_id=aid).delete()
            db.session.flush()

            # 2) Удалить спортсменов (каскадно удалятся Participant и т.д.)
            for aid in ATHLETE_IDS_TO_DELETE:
                a = Athlete.query.get(aid)
                if a:
                    db.session.delete(a)
            db.session.flush()

            # 3) У остальных спортсменов школы id=15 снять привязку к клубу
            Athlete.query.filter_by(club_id=CLUB_ID_TO_DELETE).update({"club_id": None})
            db.session.flush()

            # 4) Удалить клуб
            if club:
                db.session.delete(club)

            db.session.commit()
            print("✅ Спортсмены и школа удалены.")
            return 0
        except Exception as e:
            db.session.rollback()
            print(f"❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()
            return 1


if __name__ == "__main__":
    sys.exit(main())
