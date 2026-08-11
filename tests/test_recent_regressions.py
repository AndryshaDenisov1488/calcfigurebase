import unittest
from datetime import date, timedelta
from unittest.mock import Mock, patch

from flask import Flask, session

from extensions import db
from models import Athlete, Category, Event, Participant
from routes import admin as admin_routes
from services.rank_service import build_rank_groups


class MultiFileNormalizeTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.secret_key = 'test-secret'
        self.app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)
        self.app.config['UPLOAD_FOLDER'] = '/tmp'

    def _seed_admin_session(self):
        session['admin_logged_in'] = True
        session['parser_data'] = {
            'files': [
                {'filepath': '/tmp/missing-1.xml', 'filename': 'one.xml', 'categories_count': 1},
                {'filepath': '/tmp/missing-2.xml', 'filename': 'two.xml', 'categories_count': 1},
            ],
            'categories_analysis': [
                {'normalized': 'Rank A', 'needs_manual': False},
                {'normalized': 'Rank B', 'needs_manual': False},
            ],
            'parser_summaries': [],
        }

    def test_birth_conflict_check_uses_submitted_deletes_for_multi_file_import(self):
        with self.app.test_request_context(
            '/check-import-birth-conflicts',
            method='POST',
            data={'delete_1': '1', 'normalize_0': 'Rank A', 'normalize_1': 'Rank B'},
        ):
            self._seed_admin_session()
            with patch.object(admin_routes, 'iter_ready_parsers', return_value=[]) as iter_ready_parsers:
                with patch.object(admin_routes, 'find_birth_date_conflicts', return_value=[]):
                    response = admin_routes.check_import_birth_conflicts()

            self.assertEqual(response.status_code, 200)
            iter_ready_parsers.assert_called_once()
            self.assertEqual(iter_ready_parsers.call_args.args[2], {1})

    def test_multi_file_normalize_uses_submitted_deletes_and_single_batch_commit(self):
        parser = Mock()
        parser.get_athletes_with_results.return_value = ['athlete']
        parser_bundle = [(parser, '/tmp/missing-1.xml', 'one.xml')]

        with self.app.test_request_context(
            '/normalize-categories',
            method='POST',
            data={
                'delete_1': '1',
                'normalize_0': 'Rank A',
                'normalize_1': 'Rank B',
                'birth_conflict_resolutions': '[]',
            },
        ):
            self._seed_admin_session()
            with patch.object(admin_routes, 'iter_ready_parsers', return_value=parser_bundle) as iter_ready_parsers:
                with patch.object(admin_routes, 'apply_birth_conflict_resolutions_json'):
                    with patch.object(admin_routes, 'save_to_database') as save_to_database:
                        with patch.object(admin_routes, 'archive_imported_xml'):
                            with patch.object(admin_routes.db.session, 'flush'):
                                with patch.object(admin_routes.db.session, 'commit') as commit:
                                    with patch.object(admin_routes, 'url_for', return_value='/'):
                                        response = admin_routes.normalize_categories()

            self.assertEqual(response.status_code, 302)
            iter_ready_parsers.assert_called_once()
            self.assertEqual(iter_ready_parsers.call_args.args[2], {1})
            save_to_database.assert_called_once_with(parser, commit=False)
            commit.assert_called_once()
            self.assertNotIn('parser_data', session)


class RankFreeParticipationTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        db.init_app(self.app)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_rank_groups_ignore_participant_excluded_free_starts(self):
        event = Event(name='Event', begin_date=date(2026, 1, 1))
        db.session.add(event)
        db.session.flush()
        category = Category(
            event_id=event.id,
            name='Category',
            normalized_name='Rank A',
            gender='F',
        )
        athlete = Athlete(first_name='Anna', last_name='Skater')
        db.session.add_all([category, athlete])
        db.session.flush()
        db.session.add(
            Participant(
                event_id=event.id,
                category_id=category.id,
                athlete_id=athlete.id,
                pct_ppname='БЕСП',
                exclude_free_from_reports=True,
            )
        )
        db.session.commit()

        rank = next(group for group in build_rank_groups() if group['display_name'] == 'Rank A')

        self.assertEqual(rank['total_free_participations'], 0)
        self.assertFalse(rank['athletes'][0]['has_free_participation'])


if __name__ == '__main__':
    unittest.main()
