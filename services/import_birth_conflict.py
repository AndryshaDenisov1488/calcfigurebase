#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Конфликты даты рождения: то же ФИО в XML и в БД, разные даты."""

from __future__ import annotations

from datetime import date

from sqlalchemy import func

from models import Athlete
from utils.date_parsing import parse_date
from utils.normalizers import normalize_string, remove_duplication


def _person_display_fio(person_data: dict) -> str:
    full_name_xml = person_data.get('full_name') or person_data.get('full_name_xml')
    xml_trim = normalize_string(full_name_xml or '').strip()
    if xml_trim:
        return xml_trim
    first_name_raw = person_data.get('first_name_cyrillic') or person_data.get('first_name')
    last_name_raw = person_data.get('last_name_cyrillic') or person_data.get('last_name')
    patronymic_raw = person_data.get('patronymic_cyrillic') or person_data.get('patronymic')
    parts = []
    if last_name_raw:
        parts.append(remove_duplication(normalize_string(last_name_raw)))
    if first_name_raw:
        parts.append(remove_duplication(normalize_string(first_name_raw)))
    if patronymic_raw:
        parts.append(remove_duplication(normalize_string(patronymic_raw)))
    return ' '.join(parts) if parts else ''


def _athlete_display_fio(a: Athlete) -> str:
    if a.full_name_xml and str(a.full_name_xml).strip():
        return str(a.full_name_xml).strip()
    parts = []
    if a.last_name:
        parts.append(remove_duplication(normalize_string(a.last_name)))
    if a.first_name:
        parts.append(remove_duplication(normalize_string(a.first_name)))
    if a.patronymic:
        parts.append(remove_duplication(normalize_string(a.patronymic)))
    return ' '.join(parts) if parts else ''


def _fio_key(display_fio: str) -> str:
    return display_fio.strip().lower()


def _format_dmycolon(d: date | None) -> str | None:
    if not d:
        return None
    return d.strftime('%d.%m.%Y')


def _coerce_xml_date(raw) -> date | None:
    if raw is None:
        return None
    if hasattr(raw, 'year') and hasattr(raw, 'month') and hasattr(raw, 'day'):
        return raw
    if isinstance(raw, str):
        return parse_date(raw)
    return None


def find_birth_date_conflicts(parser) -> list[dict]:
    """
    Ищет участников XML: то же отображаемое ФИО, что у спортсмена в БД,
    но дата рождения в файле и в профиле различаются (обе заданы).
    """
    conflicts: list[dict] = []
    seen_pairs: set[tuple[str, int]] = set()

    for participant_data in parser.participants:
        person_id = participant_data.get('person_id')
        person_data = next((p for p in parser.persons if p['id'] == person_id), None)
        if not person_data:
            continue

        xml_date = _coerce_xml_date(person_data.get('birth_date'))
        if not xml_date:
            continue

        display = _person_display_fio(person_data)
        if not display.strip():
            continue
        pkey = _fio_key(display)

        last_raw = person_data.get('last_name_cyrillic') or person_data.get('last_name')
        last_clean = normalize_string(remove_duplication(last_raw or '')).strip()
        if not last_clean:
            continue
        ln = last_clean.lower()
        candidates = Athlete.query.filter(func.lower(func.trim(Athlete.last_name)) == ln).all()

        for a in candidates:
            if _fio_key(_athlete_display_fio(a)) != pkey:
                continue
            adb = a.birth_date
            if not adb or adb == xml_date:
                continue
            dedup = (str(person_id), a.id)
            if dedup in seen_pairs:
                continue
            seen_pairs.add(dedup)
            conflicts.append({
                'person_id': str(person_id),
                'fio': display,
                'xml_birth': _format_dmycolon(xml_date),
                'xml_birth_iso': xml_date.isoformat(),
                'athlete_id': a.id,
                'db_birth': _format_dmycolon(adb),
                'db_birth_iso': adb.isoformat(),
                'profile_url': f'https://calc.figurebase.ru/athlete/{a.id}',
            })
    return conflicts


def apply_birth_conflict_resolutions_json(resolutions: list[dict], parsers: list) -> None:
    """
    resolutions: [{ 'person_id': str, 'athlete_id': int, 'use': 'xml'|'db' }, ...]
    parsers — список уже подготовленных парсеров (тот же порядок, что перед save_to_database).
    Сначала применяются выборы 'xml' (обновление профиля в БД), затем 'db' (правка даты в объектах parser.persons).
    """
    if not resolutions:
        return

    from extensions import db
    from services.athlete_registry import AthleteRegistry

    xml_first = [r for r in resolutions if r.get('use') == 'xml']
    db_rest = [r for r in resolutions if r.get('use') == 'db']

    registry = AthleteRegistry()

    for r in xml_first:
        aid = int(r['athlete_id'])
        person_id = str(r['person_id'])
        athlete = Athlete.query.get(aid)
        person_data = None
        for parser in parsers:
            person_data = next((p for p in parser.persons if str(p['id']) == person_id), None)
            if person_data:
                break
        if not athlete or not person_data:
            continue
        xml_date = _coerce_xml_date(person_data.get('birth_date'))
        if not xml_date:
            continue
        athlete.birth_date = xml_date
        athlete.lookup_key = registry._make_lookup_key({
            'first_name': athlete.first_name,
            'last_name': athlete.last_name,
            'birth_date': xml_date,
        })

    db.session.flush()

    for r in db_rest:
        person_id = str(r['person_id'])
        aid = int(r['athlete_id'])
        athlete = Athlete.query.get(aid)
        if not athlete or not athlete.birth_date:
            continue
        db_d = athlete.birth_date
        for parser in parsers:
            person_data = next((p for p in parser.persons if str(p['id']) == person_id), None)
            if person_data:
                person_data['birth_date'] = db_d
