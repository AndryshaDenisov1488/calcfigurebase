#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Synchronize both members of pair Athlete rows from the official XLSX registry."""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from pathlib import Path

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app_factory import create_app
from extensions import db
from models import Athlete
from scripts.compare_registry_birth_dates import load_registry, normalize_name


def split_protocol_name(value: str | None) -> tuple[str | None, str | None, str | None]:
    words = str(value or "").strip().split()
    if len(words) < 2:
        return None, None, None
    first_name = words[0]
    last_name = words[-1]
    patronymic = " ".join(words[1:-1]) or None
    return first_name, last_name, patronymic


def pair_member_names(athlete: Athlete) -> tuple[str, str] | None:
    if athlete.primary_member_full_name and athlete.partner_member_full_name:
        return athlete.primary_member_full_name, athlete.partner_member_full_name
    protocol_names = [part.strip() for part in (athlete.full_name or "").split("/")]
    if len(protocol_names) != 2 or not all(protocol_names):
        return None
    return protocol_names[0], protocol_names[1]


def sync_pair_birth_dates(registry_path: Path, apply: bool) -> dict[str, int]:
    registry_dates: dict[tuple[str, ...], set] = defaultdict(set)
    for row in load_registry(registry_path):
        if row["birth_date"]:
            registry_dates[row["name_key"]].add(row["birth_date"])

    stats = {
        "pair_rows": 0,
        "matched_members": 0,
        "updated_members": 0,
        "unchanged_members": 0,
        "not_found_members": 0,
        "ambiguous_members": 0,
    }

    for athlete in Athlete.query.filter(Athlete.gender == "P").order_by(Athlete.id):
        names = pair_member_names(athlete)
        if not names:
            continue
        stats["pair_rows"] += 1

        for prefix, fio in zip(("primary", "partner"), names):
            dates = registry_dates.get(normalize_name(fio), set())
            if not dates:
                stats["not_found_members"] += 1
                continue
            if len(dates) > 1:
                stats["ambiguous_members"] += 1
                print(
                    f"SKIP ambiguous ID {athlete.id} {prefix}: {fio} "
                    f"=> {', '.join(sorted(value.isoformat() for value in dates))}"
                )
                continue

            stats["matched_members"] += 1
            registry_birth_date = next(iter(dates))
            date_field = f"{prefix}_birth_date"
            old_birth_date = getattr(athlete, date_field)
            if old_birth_date == registry_birth_date:
                stats["unchanged_members"] += 1
                continue

            stats["updated_members"] += 1
            print(
                f"{'UPDATE' if apply else 'WOULD UPDATE'} ID {athlete.id} {prefix}: "
                f"{fio}: {old_birth_date or 'empty'} -> {registry_birth_date}"
            )
            if not apply:
                continue

            setattr(athlete, date_field, registry_birth_date)
            if prefix == "primary":
                athlete.birth_date = registry_birth_date

            first_name, last_name, patronymic = split_protocol_name(fio)
            if not getattr(athlete, f"{prefix}_first_name"):
                setattr(athlete, f"{prefix}_first_name", first_name)
            if not getattr(athlete, f"{prefix}_last_name"):
                setattr(athlete, f"{prefix}_last_name", last_name)
            if not getattr(athlete, f"{prefix}_patronymic"):
                setattr(athlete, f"{prefix}_patronymic", patronymic)

    if apply:
        db.session.commit()
    else:
        db.session.rollback()
    return stats


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("registry", type=Path)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Commit updates. Without this flag the command is a dry run.",
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        stats = sync_pair_birth_dates(args.registry, args.apply)
        print("mode:", "apply" if args.apply else "dry-run")
        for key, value in stats.items():
            print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
