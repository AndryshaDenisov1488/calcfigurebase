import os
import tempfile
import unittest
from datetime import date


os.environ.setdefault('ALLOW_INSECURE_DEFAULTS', '1')
os.environ.setdefault('DISABLE_PUBLIC_API_AUTH', '1')
_db_fd, _db_path = tempfile.mkstemp(prefix='calcfigurebase-season-', suffix='.db')
os.close(_db_fd)
os.environ['DATABASE_URL'] = f"sqlite:///{_db_path.replace(os.sep, '/')}"

from app_factory import create_app
from extensions import db
from models import Athlete, Category, Club, Event, Participant


def tearDownModule():
    try:
        from google_sheets_sync import app as reports_app

        with reports_app.app_context():
            db.engine.dispose()
    except (ImportError, RuntimeError):
        pass
    try:
        os.unlink(_db_path)
    except OSError:
        pass


class SeasonScopingTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        club = Club(name='Тестовая школа')
        current_athlete = Athlete(first_name='Новый', last_name='Спортсмен', club=club)
        old_athlete = Athlete(first_name='Старый', last_name='Спортсмен', club=club)
        current_event = Event(name='Новый сезон', begin_date=date(2026, 8, 10))
        old_event = Event(name='Прошлый сезон', begin_date=date(2025, 8, 10))
        current_category = Category(name='1 спортивный', normalized_name='1 Спортивный, Девочки', event=current_event)
        old_category = Category(name='2 спортивный', normalized_name='2 Спортивный, Девочки', event=old_event)
        current_participant = Participant(
            event=current_event,
            category=current_category,
            athlete=current_athlete,
            total_place=1,
            total_points=100,
        )
        db.session.add_all([
            current_participant,
            Participant(
                event=old_event,
                category=old_category,
                athlete=old_athlete,
                total_place=1,
                total_points=90,
            ),
        ])
        db.session.commit()
        self.current_athlete_id = current_athlete.id
        self.current_club_id = club.id
        self.current_category_id = current_category.id
        self.current_participant_id = current_participant.id
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.ctx.pop()

    def _authorize(self):
        with self.client.session_transaction() as flask_session:
            flask_session['admin_logged_in'] = True

    def test_current_season_is_the_default_everywhere(self):
        self._authorize()

        page = self.client.get('/')
        self.assertEqual(page.status_code, 200)
        self.assertIn('Новый сезон', page.get_data(as_text=True))
        self.assertNotIn('Прошлый сезон', page.get_data(as_text=True))

        statistics = self.client.get('/api/statistics').get_json()
        self.assertEqual(statistics['total_events'], 1)
        self.assertEqual(statistics['total_athletes'], 1)
        self.assertEqual(statistics['total_participations'], 1)

        athletes = self.client.get('/api/athletes').get_json()
        self.assertEqual(athletes['pagination']['total'], 1)
        self.assertEqual(athletes['athletes'][0]['full_name'], 'Спортсмен Новый')

    def test_historical_season_can_be_selected_without_losing_data(self):
        self._authorize()

        page = self.client.get('/?season=2025%2F26')
        self.assertEqual(page.status_code, 200)
        self.assertIn('Прошлый сезон', page.get_data(as_text=True))
        self.assertNotIn('Новый сезон', page.get_data(as_text=True))

        statistics = self.client.get('/api/statistics').get_json()
        self.assertEqual(statistics['total_events'], 1)
        athletes = self.client.get('/api/athletes').get_json()
        self.assertEqual(athletes['athletes'][0]['full_name'], 'Спортсмен Старый')

    def test_season_scoped_pages_and_reports_render(self):
        self._authorize()
        urls = (
            '/events',
            '/athletes',
            '/categories',
            '/best_results',
            '/clubs',
            '/coaches',
            '/analytics',
            '/free-participation',
            '/club-free-analysis',
            '/school-segment-event-ranks',
            '/free-participation-analysis',
            '/first-timers-detail',
            '/first-timers-detail-free',
            '/judge-helper-free',
            '/admin/event-ranks',
            '/admin/free-participation',
            '/api/events',
            '/api/analytics/top-athletes',
            '/api/analytics/club-statistics',
            '/api/analytics/category-statistics',
            '/api/analytics/free-participation',
            '/api/analytics/club-free-participation',
            '/api/analytics/free-participation-analysis',
            '/api/clubs',
            '/api/coaches',
            f'/athlete/{self.current_athlete_id}',
            f'/club/{self.current_club_id}',
            f'/api/athlete/{self.current_athlete_id}/results-chart',
            f'/api/category/{self.current_category_id}',
            f'/api/participant/{self.current_participant_id}/performance-details',
        )
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200, response.get_data(as_text=True))


if __name__ == '__main__':
    unittest.main()
