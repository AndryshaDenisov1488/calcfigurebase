#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Backfill pair-member fields for existing Athlete rows from an ISUCalcFS XML."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app_factory import create_app
from extensions import db
from models import Athlete
from parsers.isu_calcfs_parser import ISUCalcFSParser
from services.athlete_registry import AthleteRegistry
from utils.date_parsing import parse_date


def find_pair(person_data: dict) -> tuple[Athlete | None, str]:
    """Find an existing composite pair without creating a new athlete."""
    external_id = person_data.get("external_id")
    if external_id:
        candidates = Athlete.query.filter_by(external_id=external_id).all()
        if len(candidates) == 1:
            return candidates[0], "external_id"
        if len(candidates) > 1:
            return None, "ambiguous_external_id"

    full_name = person_data.get("full_name") or person_data.get("full_name_xml")
    birth_date = parse_date(person_data.get("birth_date"))
    if full_name:
        candidates = Athlete.query.filter_by(
            full_name_xml=full_name,
            birth_date=birth_date,
        ).all()
        if len(candidates) == 1:
            return candidates[0], "name_birth"
        if len(candidates) > 1:
            return None, "ambiguous_name_birth"
    return None, "not_found"


def backfill(xml_path: Path, apply: bool) -> dict[str, int]:
    parser = ISUCalcFSParser(xml_path)
    parser.parse()
    registry = AthleteRegistry()
    stats = {
        "xml_pairs": 0,
        "matched": 0,
        "updated": 0,
        "not_found": 0,
        "ambiguous": 0,
    }

    for person_data in parser.persons:
        if person_data.get("type") != "COU":
            continue
        stats["xml_pairs"] += 1
        athlete, match_type = find_pair(person_data)
        if not athlete:
            key = "ambiguous" if match_type.startswith("ambiguous") else "not_found"
            stats[key] += 1
            print(
                f"SKIP {match_type}: "
                f"{person_data.get('full_name') or person_data.get('full_name_xml')}"
            )
            continue

        stats["matched"] += 1
        before = tuple(getattr(athlete, field) for field in registry.PAIR_DETAIL_FIELDS)
        registry._merge_pair_details(athlete, person_data)
        after = tuple(getattr(athlete, field) for field in registry.PAIR_DETAIL_FIELDS)
        if before != after:
            stats["updated"] += 1
            print(
                f"{'UPDATE' if apply else 'WOULD UPDATE'} ID {athlete.id}: "
                f"{athlete.full_name}"
            )

    if apply:
        db.session.commit()
    else:
        db.session.rollback()
    return stats


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("xml", type=Path)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Commit updates. Without this flag the command is a dry run.",
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        stats = backfill(args.xml, args.apply)
        print("mode:", "apply" if args.apply else "dry-run")
        for key, value in stats.items():
            print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
