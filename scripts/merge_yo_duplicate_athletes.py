#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Merge the production athlete duplicates confirmed in the Е/Ё review."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app_factory import create_app
from extensions import db
from models import Athlete, CoachAssignment, Participant
from services.athlete_registry import AthleteRegistry


# keep_id, remove_id, spelling_source_id, corrected_birth_date
MERGES = (
    (1232, 3163, 3163, None),
    (1816, 2712, 1816, None),
    (1357, 2650, 1357, None),
    (2740, 1233, 2740, None),
    (1109, 3443, 1109, None),
    (917, 2611, 2611, None),
    (1818, 2707, 2707, None),
    (414, 3271, 3271, None),
    (3358, 1770, 3358, None),
    (3243, 3315, 3315, None),
    (1060, 3552, 1060, None),
    (2009, 2622, 2009, None),
    (211, 3044, 211, None),
    (1602, 3454, 3454, date(2016, 1, 1)),
    (913, 3320, 3320, None),
    (3570, 3577, 3577, None),
    (2600, 35, 2600, None),
)


def merge_duplicates(apply: bool) -> dict[str, int]:
    registry = AthleteRegistry()
    stats = {
        "planned": len(MERGES),
        "merged": 0,
        "already_merged": 0,
        "conflicts": 0,
        "normalized_lookup_keys": 0,
    }

    for keep_id, remove_id, spelling_source_id, corrected_birth_date in MERGES:
        keep = db.session.get(Athlete, keep_id)
        remove = db.session.get(Athlete, remove_id)
        if keep and not remove:
            stats["already_merged"] += 1
            print(f"ALREADY MERGED: {remove_id} -> {keep_id}")
            continue
        if not keep or not remove:
            stats["conflicts"] += 1
            print(f"ERROR missing row: keep={keep_id} remove={remove_id}")
            continue

        keep_slots = {
            (event_id, category_id)
            for event_id, category_id in db.session.query(
                Participant.event_id, Participant.category_id
            ).filter(Participant.athlete_id == keep_id)
        }
        remove_slots = {
            (event_id, category_id)
            for event_id, category_id in db.session.query(
                Participant.event_id, Participant.category_id
            ).filter(Participant.athlete_id == remove_id)
        }
        participation_conflicts = len(keep_slots & remove_slots)
        if participation_conflicts:
            stats["conflicts"] += 1
            print(
                f"CONFLICT {remove_id} -> {keep_id}: "
                f"{participation_conflicts} duplicate event/category slots"
            )
            continue

        source = keep if spelling_source_id == keep_id else remove
        final_birth_date = corrected_birth_date or keep.birth_date or remove.birth_date
        remove_participations = Participant.query.filter_by(athlete_id=remove_id).count()
        remove_assignments = CoachAssignment.query.filter_by(athlete_id=remove_id).count()
        print(
            f"{'MERGE' if apply else 'WOULD MERGE'} {remove_id} -> {keep_id}: "
            f"{remove.full_name} => {source.full_name}; "
            f"participations={remove_participations}, coaches={remove_assignments}, "
            f"birth_date={final_birth_date}"
        )

        if not apply:
            stats["merged"] += 1
            continue

        for field in (
            "external_id",
            "first_name",
            "last_name",
            "patronymic",
            "full_name_xml",
            "gender",
            "country",
            "club_id",
        ):
            source_value = getattr(source, field)
            if source_value not in (None, ""):
                setattr(keep, field, source_value)

        keep.birth_date = final_birth_date
        keep.lookup_key = registry._make_lookup_key(
            {
                "first_name": keep.first_name,
                "last_name": keep.last_name,
                "birth_date": keep.birth_date,
            }
        )
        Participant.query.filter_by(athlete_id=remove_id).update(
            {"athlete_id": keep_id},
            synchronize_session=False,
        )
        CoachAssignment.query.filter_by(athlete_id=remove_id).update(
            {"athlete_id": keep_id},
            synchronize_session=False,
        )
        db.session.delete(remove)
        stats["merged"] += 1

    if stats["conflicts"]:
        db.session.rollback()
        print("ROLLBACK: unresolved conflicts found")
        return stats

    for athlete in Athlete.query.filter(Athlete.birth_date.isnot(None)):
        normalized_lookup_key = registry._make_lookup_key(
            {
                "first_name": athlete.first_name,
                "last_name": athlete.last_name,
                "birth_date": athlete.birth_date,
            }
        )
        if normalized_lookup_key and athlete.lookup_key != normalized_lookup_key:
            stats["normalized_lookup_keys"] += 1
            if apply:
                athlete.lookup_key = normalized_lookup_key

    if apply:
        db.session.commit()
    else:
        db.session.rollback()
    return stats


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Commit all merges atomically. Without this flag the command is a dry run.",
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        stats = merge_duplicates(args.apply)
        print("mode:", "apply" if args.apply else "dry-run")
        for key, value in stats.items():
            print(f"{key}: {value}")
    return 1 if stats["conflicts"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
