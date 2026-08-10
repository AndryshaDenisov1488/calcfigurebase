"""Regression: birth-conflict detection must work for Cyrillic names on SQLite.

SQLite LOWER() does not case-fold Cyrillic, so filtering candidates with
``func.lower(Athlete.last_name) == 'иванова'`` misses rows stored as «Иванова»
or «ИВАНОВА». That silently skipped the conflict UI and let import create a
second Athlete card for the same person with a different birth date.
"""

from __future__ import annotations

import os
import unittest
from datetime import date

os.environ.setdefault('ALLOW_INSECURE_DEFAULTS', '1')
os.environ.setdefault('SECRET_KEY', 'test-secret-key')
os.environ.setdefault('ADMIN_PASSWORD', 'test-admin')


class _Parser:
    def __init__(self, persons, participants):
        self.persons = persons
        self.participants = participants


class BirthConflictCyrillicSqliteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app_factory import create_app

        cls.app = create_app()
        cls.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        cls.app.config['TESTING'] = True
        cls.app.config['WTF_CSRF_ENABLED'] = False

    def setUp(self):
        from extensions import db

        self.ctx = self.app.app_context()
        self.ctx.push()
        db.session.remove()
        db.drop_all()
        db.create_all()

    def tearDown(self):
        from extensions import db

        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _seed_athlete(self, *, last_name: str, first_name: str, birth: date, full_name_xml: str):
        from extensions import db
        from models import Athlete

        athlete = Athlete(
            last_name=last_name,
            first_name=first_name,
            birth_date=birth,
            full_name_xml=full_name_xml,
            lookup_key=f'name:{first_name.lower()}:{last_name.lower()}:{birth}',
        )
        db.session.add(athlete)
        db.session.commit()
        return athlete

    def _xml_person(self, *, person_id: str, last_name: str, first_name: str, birth: str, full_name: str):
        return {
            'id': person_id,
            'last_name': last_name,
            'first_name': first_name,
            'full_name': full_name,
            'birth_date': birth,
        }

    def test_detects_conflict_when_db_last_name_is_title_case_cyrillic(self):
        from services.import_birth_conflict import find_birth_date_conflicts

        athlete = self._seed_athlete(
            last_name='Иванова',
            first_name='Мария',
            birth=date(2010, 1, 15),
            full_name_xml='Иванова Мария',
        )
        person = self._xml_person(
            person_id='P1',
            last_name='Иванова',
            first_name='Мария',
            birth='20100520',
            full_name='Иванова Мария',
        )
        parser = _Parser([person], [{'person_id': 'P1', 'id': 'PAR1'}])

        conflicts = find_birth_date_conflicts(parser)

        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]['athlete_id'], athlete.id)
        self.assertEqual(conflicts[0]['person_id'], 'P1')
        self.assertEqual(conflicts[0]['db_birth_iso'], '2010-01-15')
        self.assertEqual(conflicts[0]['xml_birth_iso'], '2010-05-20')

    def test_detects_conflict_when_db_last_name_is_upper_cyrillic(self):
        from services.import_birth_conflict import find_birth_date_conflicts

        athlete = self._seed_athlete(
            last_name='ИВАНОВА',
            first_name='МАРИЯ',
            birth=date(2010, 1, 15),
            full_name_xml='ИВАНОВА МАРИЯ',
        )
        person = self._xml_person(
            person_id='P2',
            last_name='ИВАНОВА',
            first_name='МАРИЯ',
            birth='20101201',
            full_name='ИВАНОВА МАРИЯ',
        )
        parser = _Parser([person], [{'person_id': 'P2', 'id': 'PAR2'}])

        conflicts = find_birth_date_conflicts(parser)

        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]['athlete_id'], athlete.id)

    def test_no_conflict_when_birth_dates_match(self):
        from services.import_birth_conflict import find_birth_date_conflicts

        self._seed_athlete(
            last_name='Иванова',
            first_name='Мария',
            birth=date(2010, 5, 20),
            full_name_xml='Иванова Мария',
        )
        person = self._xml_person(
            person_id='P3',
            last_name='Иванова',
            first_name='Мария',
            birth='20100520',
            full_name='Иванова Мария',
        )
        parser = _Parser([person], [{'person_id': 'P3', 'id': 'PAR3'}])

        self.assertEqual(find_birth_date_conflicts(parser), [])

    def test_legacy_sql_lower_filter_misses_title_case_cyrillic(self):
        """Document the SQLite failure mode this fix replaces."""
        from sqlalchemy import func

        from extensions import db
        from models import Athlete

        self._seed_athlete(
            last_name='Иванова',
            first_name='Мария',
            birth=date(2010, 1, 15),
            full_name_xml='Иванова Мария',
        )
        ln = 'иванова'
        missed = Athlete.query.filter(func.lower(func.trim(Athlete.last_name)) == ln).all()
        self.assertEqual(
            missed,
            [],
            'SQLite LOWER must miss Cyrillic title case; if this passes, the bug platform changed',
        )


if __name__ == '__main__':
    unittest.main()
