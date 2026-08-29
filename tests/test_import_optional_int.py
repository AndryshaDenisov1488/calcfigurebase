#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Import must store GOE/result 0; `if value else None` drops int 0."""
import os
import unittest

os.environ.setdefault('ALLOW_INSECURE_DEFAULTS', '1')
os.environ.setdefault('SECRET_KEY', 'test-import-optional-int')

from parsers.isu_calcfs_parser import ISUCalcFSParser
from services.import_service import _optional_int


def _old_optional_int(raw_value):
    """Buggy import conversion: truthiness drops 0."""
    return int(raw_value) if raw_value else None


class TestOptionalInt(unittest.TestCase):
    def test_keeps_integer_zero(self):
        self.assertEqual(_optional_int(0), 0)
        self.assertEqual(_optional_int('0'), 0)

    def test_keeps_negative_and_positive(self):
        self.assertEqual(_optional_int(-36), -36)
        self.assertEqual(_optional_int('55'), 55)
        self.assertEqual(_optional_int(110), 110)

    def test_missing_is_none(self):
        self.assertIsNone(_optional_int(None))
        self.assertIsNone(_optional_int(''))

    def test_old_truthiness_dropped_zero(self):
        self.assertIsNone(_old_optional_int(0))
        self.assertEqual(_optional_int(0), 0)


class TestParserZeroGoeNotDropped(unittest.TestCase):
    def test_sample_xml_computed_zero_goe_is_kept(self):
        xml_path = os.path.join(os.path.dirname(__file__), '..', 'scripts', '2124priz.XML')
        parser = ISUCalcFSParser(os.path.abspath(xml_path))
        parser.parse()
        zero_goe = 0
        for performance in parser.performances:
            for elem in performance.get('elements', []):
                raw = elem.get('goe_result')
                if raw != 0:
                    continue
                zero_goe += 1
                self.assertIsNone(_old_optional_int(raw))
                self.assertEqual(_optional_int(raw), 0)
        self.assertGreater(
            zero_goe,
            50,
            'sample XML should contain many elements with computed GOE 0 (PNL omitted)',
        )


if __name__ == '__main__':
    unittest.main()
