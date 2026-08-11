import unittest
from datetime import date

from flask import Flask

from extensions import db
from models import Athlete, Category, Event, Participant
from services.rank_service import build_rank_groups


class RankServiceRegressionTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
        )
        db.init_app(self.app)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_rank_groups_do_not_count_participant_excluded_free_starts(self):
        event = Event(name='Event', begin_date=date(2026, 1, 1), exclude_free_from_reports=False)
        db.session.add(event)
        db.session.flush()
        category = Category(
            event_id=event.id,
            name='Free Test Rank',
            normalized_name='Free Test Rank',
            gender='F',
        )
        db.session.add(category)
        db.session.flush()
        athlete = Athlete(first_name='Anna', last_name='Test')
        db.session.add(athlete)
        db.session.flush()
        db.session.add(Participant(
            event_id=event.id,
            category_id=category.id,
            athlete_id=athlete.id,
            pct_ppname='БЕСП',
            exclude_free_from_reports=True,
        ))
        db.session.commit()

        rank = next(r for r in build_rank_groups() if r['display_name'] == 'Free Test Rank')

        self.assertEqual(rank['athlete_count'], 1)
        self.assertEqual(rank['total_participations'], 1)
        self.assertEqual(rank['total_free_participations'], 0)
        self.assertEqual(rank['athletes'][0]['free_participations'], 0)
        self.assertFalse(rank['athletes'][0]['has_free_participation'])
        self.assertFalse([
            r for r in build_rank_groups(only_free_participation=True)
            if r['display_name'] == 'Free Test Rank' and r['has_data']
        ])


if __name__ == '__main__':
    unittest.main()
