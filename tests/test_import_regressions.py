import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from werkzeug.datastructures import MultiDict

from routes.admin import _apply_category_form_to_analysis, _parse_normalize_category_form
from services.xml_import_prepare import iter_ready_parsers


class FakeParser:
    def __init__(self, filepath):
        self.filepath = filepath
        self.categories = []
        self.segments = []
        self.participants = []
        self.persons = []

    def parse(self):
        if self.filepath.endswith('one.xml'):
            self.categories = [{'id': 'cat-1'}, {'id': 'cat-2'}]
        else:
            self.categories = [{'id': 'cat-3'}, {'id': 'cat-4'}]
        self.segments = [{'category_id': c['id']} for c in self.categories]
        self.participants = [{'category_id': c['id']} for c in self.categories]


class ImportNormalizationRegressionTest(unittest.TestCase):
    def test_deleted_categories_are_parsed_and_not_normalized(self):
        request = SimpleNamespace(form=MultiDict([
            ('normalize_0', 'Rank A'),
            ('normalize_1', 'Rank B'),
            ('delete_1', '1'),
        ]))

        normalizations, deleted_indices = _parse_normalize_category_form(request)
        categories = [
            {'normalized': '', 'needs_manual': True},
            {'normalized': '', 'needs_manual': True},
        ]

        _apply_category_form_to_analysis(categories, normalizations, deleted_indices)

        self.assertEqual(normalizations, {0: 'Rank A', 1: 'Rank B'})
        self.assertEqual(deleted_indices, {1})
        self.assertEqual(categories[0]['normalized'], 'Rank A')
        self.assertFalse(categories[0]['needs_manual'])
        self.assertEqual(categories[1]['normalized'], '')
        self.assertTrue(categories[1]['needs_manual'])
        self.assertTrue(categories[1]['deleted'])

    def test_iter_ready_parsers_filters_deleted_global_category_indices(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            one = os.path.join(tmpdir, 'one.xml')
            two = os.path.join(tmpdir, 'two.xml')
            open(one, 'w', encoding='utf-8').close()
            open(two, 'w', encoding='utf-8').close()
            parser_data = {
                'files': [
                    {'filepath': one, 'filename': 'one.xml'},
                    {'filepath': two, 'filename': 'two.xml'},
                ]
            }
            categories_analysis = [
                {'normalized': 'Rank 1'},
                {'normalized': 'Rank 2'},
                {'normalized': 'Rank 3'},
                {'normalized': 'Rank 4'},
            ]

            with patch('services.xml_import_prepare.ISUCalcFSParser', FakeParser):
                bundle = list(iter_ready_parsers(parser_data, categories_analysis, {1, 2}))

        self.assertEqual(len(bundle), 2)
        first_parser = bundle[0][0]
        second_parser = bundle[1][0]
        self.assertEqual([c['id'] for c in first_parser.categories], ['cat-1'])
        self.assertEqual(first_parser.categories[0]['normalized_name'], 'Rank 1')
        self.assertEqual([s['category_id'] for s in first_parser.segments], ['cat-1'])
        self.assertEqual([p['category_id'] for p in first_parser.participants], ['cat-1'])
        self.assertEqual([c['id'] for c in second_parser.categories], ['cat-4'])
        self.assertEqual(second_parser.categories[0]['normalized_name'], 'Rank 4')

    def test_iter_ready_parsers_raises_when_multi_file_import_file_is_missing(self):
        parser_data = {
            'files': [
                {'filepath': '/tmp/does-not-exist.xml', 'filename': 'missing.xml'},
            ]
        }

        with self.assertRaises(FileNotFoundError):
            list(iter_ready_parsers(parser_data, [], set()))


if __name__ == '__main__':
    unittest.main()
