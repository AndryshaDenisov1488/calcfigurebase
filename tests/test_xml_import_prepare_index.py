#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Регрессия: сдвиг category_index при пропуске отсутствующего XML в multi-file импорте."""

import os
import tempfile
import unittest
from unittest.mock import patch

from services.xml_import_prepare import iter_ready_parsers


class FakeParser:
    data_by_path = {}

    def __init__(self, filepath):
        self.filepath = filepath

    def parse(self):
        data = self.data_by_path[self.filepath]
        self.categories = [dict(c) for c in data['categories']]
        self.segments = [dict(s) for s in data.get('segments', [])]
        self.participants = [dict(p) for p in data.get('participants', [])]


class XmlImportPrepareIndexTests(unittest.TestCase):
    def test_missing_first_file_keeps_second_file_rank_alignment(self):
        """
        После частичного импорта первый XML уже удалён с диска, сессия ещё жива.
        Второй файл должен получить свои normalized_name, а не ранги первого.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            first = os.path.join(tmpdir, 'first.xml')
            second = os.path.join(tmpdir, 'second.xml')
            # first отсутствует на диске — как после успешного save+os.remove
            open(second, 'w', encoding='utf-8').close()

            FakeParser.data_by_path = {
                second: {
                    'categories': [{'id': 'c3'}, {'id': 'c4'}],
                    'segments': [],
                    'participants': [],
                },
            }
            parser_data = {
                'files': [
                    {
                        'filepath': first,
                        'filename': 'first.xml',
                        'categories_count': 2,
                    },
                    {
                        'filepath': second,
                        'filename': 'second.xml',
                        'categories_count': 2,
                    },
                ]
            }
            categories_analysis = [
                {'normalized': 'Rank A1'},
                {'normalized': 'Rank A2'},
                {'normalized': 'Rank B1'},
                {'normalized': 'Rank B2'},
            ]

            with patch('services.xml_import_prepare.ISUCalcFSParser', FakeParser):
                ready = list(iter_ready_parsers(parser_data, categories_analysis, set()))

            self.assertEqual(len(ready), 1)
            second_parser = ready[0][0]
            self.assertEqual(
                [c['normalized_name'] for c in second_parser.categories],
                ['Rank B1', 'Rank B2'],
            )

    def test_missing_file_without_categories_count_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            first = os.path.join(tmpdir, 'first.xml')
            second = os.path.join(tmpdir, 'second.xml')
            open(second, 'w', encoding='utf-8').close()

            FakeParser.data_by_path = {
                second: {
                    'categories': [{'id': 'c3'}],
                    'segments': [],
                    'participants': [],
                },
            }
            parser_data = {
                'files': [
                    {'filepath': first, 'filename': 'first.xml'},  # нет categories_count
                    {'filepath': second, 'filename': 'second.xml', 'categories_count': 1},
                ]
            }
            categories_analysis = [
                {'normalized': 'Rank A1'},
                {'normalized': 'Rank B1'},
            ]

            with patch('services.xml_import_prepare.ISUCalcFSParser', FakeParser):
                with self.assertRaises(FileNotFoundError):
                    list(iter_ready_parsers(parser_data, categories_analysis, set()))

    def test_category_count_mismatch_stops_import(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            first = os.path.join(tmpdir, 'first.xml')
            open(first, 'w', encoding='utf-8').close()

            FakeParser.data_by_path = {
                first: {
                    'categories': [{'id': 'c1'}],  # 1 в XML
                    'segments': [],
                    'participants': [],
                },
            }
            parser_data = {
                'files': [
                    {'filepath': first, 'filename': 'first.xml', 'categories_count': 2},
                ]
            }
            categories_analysis = [
                {'normalized': 'Rank A1'},
                {'normalized': 'Rank A2'},
            ]

            with patch('services.xml_import_prepare.ISUCalcFSParser', FakeParser):
                with self.assertRaises(ValueError):
                    list(iter_ready_parsers(parser_data, categories_analysis, set()))


if __name__ == '__main__':
    unittest.main()
