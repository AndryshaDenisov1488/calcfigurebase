#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Protocol score display: do not re-divide 101.00 or drop GOE code 0."""
import unittest

from utils.score_display import judge_mark_raw, points_for_protocol_display


def _parse_score(raw_value):
    """Mirror services.import_service._parse_score without importing Flask."""
    if raw_value is None or raw_value == '':
        return None
    try:
        return int(raw_value) / 100
    except (ValueError, TypeError):
        return None


class TestPointsForProtocolDisplay(unittest.TestCase):
    def test_integer_score_over_100_stays_points_not_hundredths(self):
        stored = _parse_score('10100')  # XML hundredths → 101.0 in DB
        self.assertEqual(stored, 101.0)
        self.assertEqual(points_for_protocol_display(stored), 101.0)

    def test_exact_150_total_not_shown_as_1_50(self):
        stored = _parse_score('15000')
        self.assertEqual(stored, 150.0)
        self.assertEqual(points_for_protocol_display(stored), 150.0)

    def test_fractional_normalized_score_unchanged(self):
        stored = _parse_score('10621')
        self.assertEqual(stored, 106.21)
        self.assertAlmostEqual(points_for_protocol_display(stored), 106.21)

    def test_legacy_raw_hundredths_still_divided(self):
        self.assertAlmostEqual(points_for_protocol_display(10621), 106.21)
        self.assertAlmostEqual(points_for_protocol_display(17040), 170.40)

    def test_scores_at_or_below_100_unchanged(self):
        self.assertEqual(points_for_protocol_display(100.0), 100.0)
        self.assertEqual(points_for_protocol_display(85.5), 85.5)
        self.assertIsNone(points_for_protocol_display(None))


class TestJudgeMarkRaw(unittest.TestCase):
    def test_zero_goe_code_is_not_treated_as_missing(self):
        scores = {'J01': 0, 'J02': 4, 'J03': 5}
        self.assertEqual(judge_mark_raw(scores, 1), 0)
        self.assertEqual(judge_mark_raw(scores, 2), 4)

    def test_unpadded_key_fallback_does_not_drop_zero(self):
        scores = {'J1': 0}
        self.assertEqual(judge_mark_raw(scores, 1), 0)

    def test_missing_judge_is_none(self):
        self.assertIsNone(judge_mark_raw({'J02': 4}, 1))
        self.assertIsNone(judge_mark_raw(None, 1))


if __name__ == '__main__':
    unittest.main()
