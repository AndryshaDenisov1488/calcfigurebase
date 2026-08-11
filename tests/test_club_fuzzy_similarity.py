#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ClubRegistry fuzzy similarity must not auto-merge distinct schools."""

import unittest

from services.club_registry import ClubRegistry


class ClubFuzzySimilarityTests(unittest.TestCase):
    def setUp(self):
        self.reg = ClubRegistry()

    def _sim(self, a, b):
        return self.reg._calculate_similarity(a, b)

    def test_quoted_brand_suffix_not_merged(self):
        # Quotes defeat naive prefix-remainder; SequenceMatcher alone is ~0.93
        self.assertLess(self._sim('СШОР «Москвич»', 'СШОР «Москвичка»'), 0.85)
        self.assertLess(
            self._sim('ГБУ ДО СШОР «Москвич»', 'ГБУ ДО СШОР «Москвичка»'),
            0.85,
        )
        self.assertLess(self._sim('СШОР «Звезда»', 'СШОР «Звездочка»'), 0.85)

    def test_near_brand_tokens_not_merged(self):
        self.assertLess(self._sim('Клуб «Айс»', 'Клуб «Аист»'), 0.85)
        self.assertLess(self._sim('СШОР «Хрустальный»', 'СШОР «Хрустальная»'), 0.85)

    def test_numbered_schools_not_merged(self):
        self.assertEqual(self._sim('СШОР №1 Москва', 'СШОР №2 Москва'), 0.0)
        self.assertEqual(self._sim('СДЮСШОР №1', 'СДЮСШОР №2'), 0.0)
        self.assertEqual(self._sim('СШОР №1', 'СШОР №11'), 0.0)

    def test_org_type_not_merged(self):
        self.assertEqual(self._sim('ГБУ ДО СШОР', 'ГБУ ДО СДЮСШОР'), 0.0)
        self.assertEqual(self._sim('ГБУ ДО СШОР', 'ГБУ ДО СДЮШОР'), 0.0)
        self.assertEqual(self._sim('МБУ СШОР', 'МБУ СДЮШОР'), 0.0)
        self.assertEqual(self._sim('СШОР «Лидер»', 'СДЮСШОР «Лидер»'), 0.0)

    def test_sdyushor_spelling_variants_still_match(self):
        # Same abbreviation family — auto-merge allowed (≥ 0.85)
        self.assertGreaterEqual(self._sim('СДЮШОР', 'СДЮСШОР'), 0.85)
        self.assertGreaterEqual(
            self._sim('ГБУ ДО СДЮШОР «Лидер»', 'ГБУ ДО СДЮСШОР «Лидер»'),
            0.85,
        )

    def test_yo_spelling_variants_still_match(self):
        self.assertGreaterEqual(self._sim('ФФКК «Орлёнок»', 'ФФКК «Орленок»'), 0.85)

    def test_extra_word_not_merged(self):
        self.assertLess(self._sim('Академия спорта', 'Академия спорта Стрижи'), 0.85)
        self.assertLess(self._sim('ООО Академия', 'ООО Академия спорта'), 0.85)

    def test_exact_and_same_club(self):
        self.assertEqual(self._sim('СШОР Москвич', 'СШОР Москвич'), 1.0)
        self.assertGreaterEqual(self._sim('СШОР «Москвич»', 'СШОР Москвич'), 0.85)


if __name__ == '__main__':
    unittest.main()
