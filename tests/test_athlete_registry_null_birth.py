"""Regression: AthleteRegistry must not split careers when PCT_BDAY is missing."""

import os
import unittest
from datetime import date

os.environ.setdefault('ALLOW_INSECURE_DEFAULTS', '1')
os.environ.setdefault('SECRET_KEY', 'test-secret-key')
os.environ.setdefault('ADMIN_PASSWORD', 'test-admin')


class AthleteRegistryNullBirthTest(unittest.TestCase):
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

    def _create(self, first, last, birth=None, **extra):
        from services.athlete_registry import AthleteRegistry
        payload = {
            'first_name': first,
            'last_name': last,
            'birth_date': birth,
            **extra,
        }
        athlete = AthleteRegistry().get_or_create(payload)
        from extensions import db
        db.session.flush()
        return athlete

    def test_two_imports_without_birth_reuse_same_card(self):
        from models import Athlete

        a1 = self._create('Иван', 'Иванов')
        a2 = self._create('Иван', 'Иванов')
        self.assertEqual(a1.id, a2.id)
        self.assertEqual(Athlete.query.count(), 1)
        self.assertIsNone(a1.birth_date)
        self.assertIsNone(a1.lookup_key)

    def test_null_birth_then_with_birth_upgrades_same_card(self):
        from models import Athlete

        a1 = self._create('Мария', 'Петрова')
        a2 = self._create('Мария', 'Петрова', birth=date(2012, 5, 1))
        self.assertEqual(a1.id, a2.id)
        self.assertEqual(Athlete.query.count(), 1)
        self.assertEqual(a2.birth_date, date(2012, 5, 1))
        self.assertEqual(a2.lookup_key, 'name:мария:петрова:2012-05-01')

    def test_with_birth_then_null_birth_reuses_unique_named_card(self):
        from models import Athlete

        a1 = self._create('Ольга', 'Сидорова', birth=date(2011, 3, 15))
        a2 = self._create('Ольга', 'Сидорова')  # later XML omits PCT_BDAY
        self.assertEqual(a1.id, a2.id)
        self.assertEqual(Athlete.query.count(), 1)
        self.assertEqual(a2.birth_date, date(2011, 3, 15))

    def test_lookup_key_still_dedupes_full_birth(self):
        from models import Athlete

        a1 = self._create('Анна', 'Козлова', birth=date(2010, 1, 2))
        a2 = self._create('Анна', 'Козлова', birth=date(2010, 1, 2))
        self.assertEqual(a1.id, a2.id)
        self.assertEqual(Athlete.query.count(), 1)

    def test_ambiguous_same_name_different_births_no_guess_without_birth(self):
        """Two different people same FIO; XML without birth must not merge wrongly."""
        from models import Athlete
        from extensions import db

        a1 = self._create('Елена', 'Смирнова', birth=date(2010, 1, 1))
        a2 = Athlete(
            first_name='Елена',
            last_name='Смирнова',
            birth_date=date(2011, 1, 1),
            lookup_key='name:елена:смирнова:2011-01-01',
        )
        db.session.add(a2)
        db.session.flush()

        a3 = self._create('Елена', 'Смирнова')  # no birth → ambiguous
        self.assertNotIn(a3.id, {a1.id, a2.id})
        self.assertEqual(Athlete.query.count(), 3)
        self.assertIsNone(a3.birth_date)


if __name__ == '__main__':
    unittest.main()
