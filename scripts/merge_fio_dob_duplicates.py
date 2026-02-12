#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Объединяет дубликатов спортсменов с одинаковым ФИО (Е и Ё = одна буква) и одинаковой датой рождения
в один профиль. Оставляется запись с минимальным id, остальные удаляются (участия и coach_assignment
переносятся).

Использование:
  python scripts/merge_fio_dob_duplicates.py --dry-run   # только показать, что будет сделано
  python scripts/merge_fio_dob_duplicates.py --apply    # выполнить объединение (с бэкапом и подтверждением)
Запускать из корня проекта.
"""

import os
import sys
import shutil
from collections import defaultdict
from datetime import datetime

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app import app, db
from models import Athlete, Participant, CoachAssignment


def normalize_fio_for_compare(name):
    """Ё -> Е для сравнения."""
    if not name or not isinstance(name, str):
        return ""
    s = " ".join((name or "").strip().split())
    return s.replace("Ё", "Е").replace("ё", "е")


def create_backup():
    """Создаёт бэкап БД."""
    db_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    db_path = db_uri.replace("sqlite:///", "").strip()
    if not db_path:
        db_path = "instance/figure_skating.db"
    if not os.path.isabs(db_path):
        db_path = os.path.join(project_root, db_path)
    if not os.path.exists(db_path):
        # На сервере база часто лежит в instance/ (без .db в имени или с ним)
        for fallback in ("instance/figure_skating.db", "instance/figure_skating"):
            p = os.path.join(project_root, fallback)
            if os.path.exists(p):
                db_path = p
                break
        else:
            print(f"❌ База не найдена: {db_path}")
            return None
    backup_dir = os.path.join(project_root, "backups")
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(backup_dir, f"before_merge_fio_dob_{timestamp}.db")
    try:
        shutil.copy2(db_path, backup_file)
        print(f"✅ Бэкап: {backup_file}")
        return backup_file
    except Exception as e:
        print(f"❌ Ошибка бэкапа: {e}")
        return None


def find_groups_to_merge():
    """Группы (normalized_fio, birth_date) с более чем одной записью. Возвращает список (keep_id, [remove_ids], display_name, birth_date)."""
    athletes = Athlete.query.all()
    by_key = defaultdict(list)  # (norm_fio, birth_date) -> [(id, full_name), ...]
    for a in athletes:
        fio = a.full_name
        key = normalize_fio_for_compare(fio)
        if not key:
            continue
        birth = a.birth_date
        by_key[(key, birth)].append((a.id, fio))
    groups = []
    for (key, birth), items in by_key.items():
        if len(items) < 2:
            continue
        ids = sorted(x[0] for x in items)
        keep_id = ids[0]
        remove_ids = ids[1:]
        names = [x[1] for x in items]
        display_name = names[0] if names else key
        groups.append((keep_id, remove_ids, display_name, birth))
    return groups


def check_conflicts(keep_id, remove_ids):
    """Проверка UniqueConstraint (event_id, category_id, athlete_id). Возвращает True если конфликт."""
    seen = set()
    for p in Participant.query.filter_by(athlete_id=keep_id).all():
        pair = (p.event_id, p.category_id)
        if pair in seen:
            return True
        seen.add(pair)
    for rid in remove_ids:
        for p in Participant.query.filter_by(athlete_id=rid).all():
            pair = (p.event_id, p.category_id)
            if pair in seen:
                return True
            seen.add(pair)
    return False


def merge_group(keep_id, remove_ids, choose_best_name=True):
    """Переносит участия и coach_assignment с remove_ids на keep_id, обновляет full_name_xml при необходимости, удаляет remove."""
    keep = Athlete.query.get(keep_id)
    if not keep:
        return False
    if choose_best_name:
        candidates = [keep.full_name_xml or keep.full_name]
        for rid in remove_ids:
            a = Athlete.query.get(rid)
            if a:
                candidates.append(a.full_name_xml or a.full_name)
        best = max(candidates, key=lambda s: len(s or ""))
        if best and keep.full_name_xml != best:
            keep.full_name_xml = best
    for rid in remove_ids:
        Participant.query.filter_by(athlete_id=rid).update({"athlete_id": keep_id})
        CoachAssignment.query.filter_by(athlete_id=rid).update({"athlete_id": keep_id})
    for rid in remove_ids:
        a = Athlete.query.get(rid)
        if a:
            db.session.delete(a)
    return True


def main():
    dry_run = "--dry-run" in sys.argv
    apply = "--apply" in sys.argv

    with app.app_context():
        groups = find_groups_to_merge()
        if not groups:
            print("Нет групп с одинаковым ФИО (Е/Ё) и одинаковой датой рождения.")
            return 0

        # Проверяем конфликты
        to_merge = []
        skipped = []
        for keep_id, remove_ids, display_name, birth in groups:
            if check_conflicts(keep_id, remove_ids):
                skipped.append((keep_id, remove_ids, display_name, birth))
            else:
                to_merge.append((keep_id, remove_ids, display_name, birth))

        print("=" * 80)
        print("Объединение дубликатов: одинаковое ФИО (Е=Ё) + одинаковая дата рождения")
        print("=" * 80)
        print(f"Групп к объединению (без конфликтов): {len(to_merge)}")
        print(f"Групп пропущено (конфликт event+category): {len(skipped)}")
        if skipped:
            print("\nПропущенные (нужно объединять вручную):")
            for keep_id, remove_ids, name, birth in skipped:
                birth_s = birth.strftime("%d.%m.%Y") if birth else "—"
                print(f"  {name} ({birth_s}) — оставить id={keep_id}, удалить {remove_ids}")
        if not to_merge:
            print("\nНечего объединять автоматически.")
            return 0

        total_remove = sum(len(remove_ids) for _, remove_ids, _, _ in to_merge)
        print(f"\nБудет объединено записей в один профиль: {total_remove} (останется {len(to_merge)} профилей)")
        print("\nГруппы:")
        for keep_id, remove_ids, display_name, birth in to_merge:
            birth_s = birth.strftime("%d.%m.%Y") if birth else "—"
            print(f"  оставить id={keep_id}, удалить {remove_ids}: {display_name} ({birth_s})")

        if dry_run:
            print("\n[--dry-run] Изменений не вносилось.")
            return 0

        if not apply:
            print("\nДля выполнения запустите с флагом: python scripts/merge_fio_dob_duplicates.py --apply")
            return 0

        confirm = input("\nВыполнить объединение? (yes/NO): ").strip().lower()
        if confirm != "yes":
            print("Отменено.")
            return 0

        backup_file = create_backup()
        if not backup_file:
            print("Объединение отменено из-за ошибки бэкапа.")
            return 1

        try:
            for keep_id, remove_ids, display_name, birth in to_merge:
                merge_group(keep_id, remove_ids, choose_best_name=True)
            db.session.commit()
            print("\n✅ Все группы объединены успешно.")
            print(f"📦 Бэкап: backups/{os.path.basename(backup_file)}")
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
