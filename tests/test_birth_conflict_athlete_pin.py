"""Regression: birth-conflict resolution must reuse the resolved athlete card."""

import os
import unittest
from datetime import date
from types import SimpleNamespace

os.environ.setdefault('ALLOW_INSECURE_DEFAULTS', '1')
os.environ.setdefault('SECRET_KEY', 'test-secret-key')
os.environ.setdefault('ADMIN_PASSWORD', 'test-admin')


class BirthConflictAthletePinTest(unittest.TestCase):
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

    def _seed_athlete(self):
        from extensions import db
        from models import Athlete
        from services.athlete_registry import AthleteRegistry

        registry = AthleteRegistry()
        athlete = Athlete(
            first_name='Софья',
            last_name='Иванова',
            full_name_xml='Иванова Софья',
            birth_date=date(2010, 1, 1),
            lookup_key=registry._make_lookup_key({
                'first_name': 'Софья',
                'last_name': 'Иванова',
                'birth_date': date(2010, 1, 1),
            }),
        )
        db.session.add(athlete)
        db.session.flush()
        return athlete

    def _parser(self, birth=date(2010, 1, 2)):
        """XML person: display FIO matches DB, structured first_name spelling differs."""
        person = {
            'id': 'xml-person-1',
            'first_name': 'София',
            'last_name': 'Иванова',
            'full_name': 'Иванова Софья',
            'birth_date': birth,
        }
        return SimpleNamespace(
            persons=[person],
            participants=[{'person_id': 'xml-person-1'}],
        )

    def _import_via_registry(self, person_data):
        from services.athlete_registry import AthleteRegistry

        return AthleteRegistry().get_or_create(
            {
                'first_name': person_data.get('first_name'),
                'last_name': person_data.get('last_name'),
                'full_name_xml': person_data.get('full_name'),
                'birth_date': person_data.get('birth_date'),
            },
            preferred_athlete_id=person_data.get('_resolved_athlete_id'),
        )

    def test_use_db_reuses_card_when_first_name_spelling_differs(self):
        """
        Admin chooses profile birth. Without pin, import lookup_key uses
        София+DB birth and creates a second card — UI promised no duplicate.
        """
        from models import Athlete
        from services.import_birth_conflict import apply_birth_conflict_resolutions_json

        athlete = self._seed_athlete()
        parser = self._parser()
        apply_birth_conflict_resolutions_json(
            [{'person_id': 'xml-person-1', 'athlete_id': athlete.id, 'use': 'db'}],
            [parser],
        )

        person = parser.persons[0]
        self.assertEqual(person.get('_resolved_athlete_id'), athlete.id)
        self.assertEqual(person['birth_date'], date(2010, 1, 1))

        imported = self._import_via_registry(person)
        self.assertEqual(imported.id, athlete.id)
        self.assertEqual(Athlete.query.count(), 1)

    def test_use_xml_reuses_card_when_first_name_spelling_differs(self):
        from extensions import db
        from models import Athlete
        from services.import_birth_conflict import apply_birth_conflict_resolutions_json

        athlete = self._seed_athlete()
        parser = self._parser(birth=date(2010, 1, 2))
        apply_birth_conflict_resolutions_json(
            [{'person_id': 'xml-person-1', 'athlete_id': athlete.id, 'use': 'xml'}],
            [parser],
        )
        db.session.flush()

        person = parser.persons[0]
        self.assertEqual(person.get('_resolved_athlete_id'), athlete.id)
        self.assertEqual(athlete.birth_date, date(2010, 1, 2))

        imported = self._import_via_registry(person)
        self.assertEqual(imported.id, athlete.id)
        self.assertEqual(Athlete.query.count(), 1)

    def test_without_pin_lookup_creates_duplicate(self):
        """Documents why preferred_athlete_id is required after conflict resolve."""
        from models import Athlete
        from services.athlete_registry import AthleteRegistry
        from services.import_birth_conflict import apply_birth_conflict_resolutions_json

        athlete = self._seed_athlete()
        parser = self._parser()
        apply_birth_conflict_resolutions_json(
            [{'person_id': 'xml-person-1', 'athlete_id': athlete.id, 'use': 'db'}],
            [parser],
        )
        person = parser.persons[0]
        # Simulate old import path: ignore pin
        dup = AthleteRegistry().get_or_create({
            'first_name': person['first_name'],
            'last_name': person['last_name'],
            'full_name_xml': person['full_name'],
            'birth_date': person['birth_date'],
        })
        self.assertNotEqual(dup.id, athlete.id)
        self.assertEqual(Athlete.query.count(), 2)


if __name__ == '__main__':
    unittest.main()
