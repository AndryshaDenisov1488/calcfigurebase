import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from werkzeug.datastructures import MultiDict

from routes.admin import _parse_normalize_category_form
from services.xml_import_prepare import iter_ready_parsers


class FakeParser:
    data_by_path = {}

    def __init__(self, filepath):
        self.filepath = filepath

    def parse(self):
        data = self.data_by_path[self.filepath]
        self.categories = [dict(c) for c in data['categories']]
        self.segments = [dict(s) for s in data['segments']]
        self.participants = [dict(p) for p in data['participants']]


class XmlImportPrepareTests(unittest.TestCase):
    def test_parse_normalize_form_collects_deleted_indices(self):
        request = SimpleNamespace(form=MultiDict([
            ('normalize_0', '1 Спортивный, Девочки'),
            ('delete_0', '0'),
            ('normalize_1', '2 Спортивный, Девочки'),
            ('delete_1', '1'),
        ]))

        normalizations, deleted_indices = _parse_normalize_category_form(request)

        self.assertEqual(normalizations, {
            0: '1 Спортивный, Девочки',
            1: '2 Спортивный, Девочки',
        })
        self.assertEqual(deleted_indices, {1})

    def test_multi_file_deleted_category_is_removed_from_parser(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            first = os.path.join(tmpdir, 'first.xml')
            second = os.path.join(tmpdir, 'second.xml')
            open(first, 'w', encoding='utf-8').close()
            open(second, 'w', encoding='utf-8').close()

            FakeParser.data_by_path = {
                first: {
                    'categories': [{'id': 'c1'}, {'id': 'c2'}],
                    'segments': [{'id': 's1', 'category_id': 'c1'}, {'id': 's2', 'category_id': 'c2'}],
                    'participants': [{'id': 'p1', 'category_id': 'c1'}, {'id': 'p2', 'category_id': 'c2'}],
                },
                second: {
                    'categories': [{'id': 'c3'}],
                    'segments': [{'id': 's3', 'category_id': 'c3'}],
                    'participants': [{'id': 'p3', 'category_id': 'c3'}],
                },
            }
            parser_data = {
                'files': [
                    {'filepath': first, 'filename': 'first.xml'},
                    {'filepath': second, 'filename': 'second.xml'},
                ]
            }
            categories_analysis = [
                {'normalized': 'Rank 1'},
                {'normalized': 'Rank 2'},
                {'normalized': 'Rank 3'},
            ]

            with patch('services.xml_import_prepare.ISUCalcFSParser', FakeParser):
                ready = list(iter_ready_parsers(parser_data, categories_analysis, {1}))

            self.assertEqual(len(ready), 2)
            first_parser = ready[0][0]
            self.assertEqual([c['id'] for c in first_parser.categories], ['c1'])
            self.assertEqual([s['id'] for s in first_parser.segments], ['s1'])
            self.assertEqual([p['id'] for p in first_parser.participants], ['p1'])
            self.assertEqual(first_parser.categories[0]['normalized_name'], 'Rank 1')


if __name__ == '__main__':
    unittest.main()
