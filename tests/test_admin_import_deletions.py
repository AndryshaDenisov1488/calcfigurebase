import unittest
from datetime import timedelta
from unittest.mock import patch

from flask import Flask, session

from routes.admin import check_import_birth_conflicts, normalize_categories


def _undecorated(view):
    while hasattr(view, '__wrapped__'):
        view = view.__wrapped__
    return view


class AdminImportDeletionTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            SECRET_KEY='test-secret',
            TESTING=True,
            PERMANENT_SESSION_LIFETIME=timedelta(hours=1),
            UPLOAD_FOLDER='uploads',
        )
        self.app.add_url_rule('/', endpoint='public.index', view_func=lambda: '')
        self.parser_data = {
            'files': [
                {'filepath': '/tmp/one.xml', 'filename': 'one.xml', 'categories_count': 2},
            ],
            'categories_analysis': [
                {'normalized': 'Old Rank 0', 'needs_manual': True},
                {'normalized': 'Old Rank 1', 'needs_manual': True},
            ],
            'parser_summaries': [{'filename': 'one.xml'}],
        }

    def test_multi_file_normalize_uses_current_delete_flags(self):
        captured = {}

        def fake_iter(parser_data, categories_analysis, deleted_indices):
            captured['deleted_indices'] = set(deleted_indices)
            captured['categories_analysis'] = categories_analysis
            return []

        with self.app.test_request_context(
            '/normalize-categories',
            method='POST',
            data={
                'normalize_0': 'Rank 0',
                'normalize_1': 'Rank 1',
                'delete_1': '1',
            },
        ):
            session['parser_data'] = self.parser_data
            with patch('routes.admin.iter_ready_parsers', side_effect=fake_iter):
                response = _undecorated(normalize_categories)()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(captured['deleted_indices'], {1})
        self.assertEqual(captured['categories_analysis'][0]['normalized'], 'Rank 0')
        self.assertTrue(captured['categories_analysis'][1]['deleted'])
        self.assertEqual(captured['categories_analysis'][1]['normalized'], 'Old Rank 1')

    def test_birth_conflict_check_honors_multi_file_delete_flags(self):
        captured = {}

        def fake_iter(parser_data, categories_analysis, deleted_indices):
            captured['deleted_indices'] = set(deleted_indices)
            return []

        with self.app.test_request_context(
            '/check-import-birth-conflicts',
            method='POST',
            data={'delete_1': '1'},
        ):
            session['parser_data'] = self.parser_data
            with patch('routes.admin.iter_ready_parsers', side_effect=fake_iter):
                response = _undecorated(check_import_birth_conflicts)()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {'success': True, 'conflicts': []})
        self.assertEqual(captured['deleted_indices'], {1})


if __name__ == '__main__':
    unittest.main()
