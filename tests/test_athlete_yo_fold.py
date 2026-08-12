"""Regression: ё/е must not split athlete identity on import.

XML from different tournaments often spells the same name as Алёна vs Алена
(or Артём vs Артем). lookup_key previously embedded the raw lowercased spelling,
so the second import created a duplicate Athlete card and split the career.
"""

from __future__ import annotations

import os
import unittest
from datetime import date

os.environ.setdefault('ALLOW_INSECURE_DEFAULTS', '1')
os.environ.setdefault('SECRET_KEY', 'test-secret-key')
os.environ.setdefault('ADMIN_PASSWORD', 'test-admin')


class AthleteRegistryYoFoldTest(unittest.TestCase):
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

    def test_lookup_key_folds_yo(self):
        from services.athlete_registry import AthleteRegistry

        registry = AthleteRegistry()
        birth = date(2010, 1, 15)
        k1 = registry._make_lookup_key({
            'first_name': 'Алёна',
            'last_name': 'Иванова',
            'birth_date': birth,
        })
        k2 = registry._make_lookup_key({
            'first_name': 'Алена',
            'last_name': 'Иванова',
            'birth_date': birth,
        })
        self.assertEqual(k1, k2)
        self.assertIn('алена', k1)
        self.assertNotIn('ё', k1)

    def test_get_or_create_reuses_card_across_yo_spellings(self):
        from extensions import db
        from models import Athlete
        from services.athlete_registry import AthleteRegistry

        registry = AthleteRegistry()
        birth = date(2010, 1, 15)

        first = registry.get_or_create({
            'first_name': 'Алёна',
            'last_name': 'Иванова',
            'birth_date': birth,
            'full_name_xml': 'Иванова Алёна',
        })
        db.session.flush()
        first_id = first.id

        second = registry.get_or_create({
            'first_name': 'Алена',
            'last_name': 'Иванова',
            'birth_date': birth,
            'full_name_xml': 'Иванова Алена',
        })
        db.session.flush()

        self.assertEqual(first_id, second.id)
        self.assertEqual(Athlete.query.count(), 1)
        self.assertNotIn('ё', second.lookup_key or '')

    def test_legacy_lookup_key_with_yo_still_matches(self):
        """Cards created before the fold still match via name+birth rematch."""
        from extensions import db
        from models import Athlete
        from services.athlete_registry import AthleteRegistry

        birth = date(2011, 5, 20)
        legacy = Athlete(
            first_name='Артём',
            last_name='Петров',
            birth_date=birth,
            full_name_xml='Петров Артём',
            lookup_key='name:артём:петров:2011-05-20',
        )
        db.session.add(legacy)
        db.session.commit()

        registry = AthleteRegistry()
        found = registry.get_or_create({
            'first_name': 'Артем',
            'last_name': 'Петров',
            'birth_date': birth,
            'full_name_xml': 'Петров Артем',
        })
        db.session.flush()

        self.assertEqual(found.id, legacy.id)
        self.assertEqual(Athlete.query.count(), 1)
        self.assertEqual(found.lookup_key, 'name:артем:петров:2011-05-20')


class BirthConflictYoFoldTest(unittest.TestCase):
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

    def test_conflict_detected_when_fio_differs_only_by_yo(self):
        from extensions import db
        from models import Athlete
        from services.import_birth_conflict import find_birth_date_conflicts

        athlete = Athlete(
            first_name='Алёна',
            last_name='Иванова',
            birth_date=date(2010, 1, 15),
            full_name_xml='Иванова Алёна',
            lookup_key='name:алена:иванова:2010-01-15',
        )
        db.session.add(athlete)
        db.session.commit()

        class Parser:
            persons = [{
                'id': '1',
                'first_name': 'Алена',
                'last_name': 'Иванова',
                'full_name': 'Иванова Алена',
                'birth_date': date(2010, 5, 20),
            }]
            participants = [{'person_id': '1'}]

        conflicts = find_birth_date_conflicts(Parser())
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]['athlete_id'], athlete.id)
        self.assertEqual(conflicts[0]['xml_birth_iso'], '2010-05-20')

    def test_title_case_cyrillic_last_name_still_matches(self):
        """Python-side FIO index (not SQLite LOWER) finds Title-case surnames."""
        from extensions import db
        from models import Athlete
        from services.import_birth_conflict import find_birth_date_conflicts

        athlete = Athlete(
            first_name='Мария',
            last_name='Иванова',
            birth_date=date(2009, 3, 1),
            full_name_xml='Иванова Мария',
            lookup_key='name:мария:иванова:2009-03-01',
        )
        db.session.add(athlete)
        db.session.commit()

        class Parser:
            persons = [{
                'id': '7',
                'first_name': 'Мария',
                'last_name': 'Иванова',
                'full_name': 'Иванова Мария',
                'birth_date': '20090401',
            }]
            participants = [{'person_id': '7'}]

        conflicts = find_birth_date_conflicts(Parser())
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]['athlete_id'], athlete.id)


if __name__ == '__main__':
    unittest.main()
