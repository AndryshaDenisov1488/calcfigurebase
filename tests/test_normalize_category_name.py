#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""КМС must not collapse to МС via substring 'мс' in 'кмс'."""
import unittest

from services.rank_service import normalize_category_name


class NormalizeCategoryNameTests(unittest.TestCase):
    def test_kms_not_misclassified_as_ms(self):
        self.assertEqual(normalize_category_name('КМС', 'F'), 'КМС, Девушки')
        self.assertEqual(normalize_category_name('КМС', 'M'), 'КМС, Юноши')
        self.assertEqual(normalize_category_name('кмс'), 'КМС')
        self.assertEqual(
            normalize_category_name('Кандидат в мастера спорта', 'F'),
            'КМС, Девушки',
        )

    def test_ms_still_maps_to_ms(self):
        self.assertEqual(normalize_category_name('МС', 'F'), 'МС, Женщины')
        self.assertEqual(normalize_category_name('МС', 'M'), 'МС, Мужчины')
        self.assertEqual(
            normalize_category_name('Мастер спорта', 'F'),
            'МС, Женщины',
        )

    def test_pairs_and_dance_keep_discipline(self):
        self.assertEqual(normalize_category_name('Парное катание, КМС'), 'КМС, Пары')
        self.assertEqual(normalize_category_name('Пары, КМС'), 'КМС, Пары')
        self.assertEqual(normalize_category_name('Парное катание, МС'), 'МС, Пары')
        self.assertEqual(normalize_category_name('Танцы на льду, КМС'), 'КМС, Танцы')
        self.assertEqual(normalize_category_name('Танцы, КМС'), 'КМС, Танцы')
        self.assertEqual(normalize_category_name('Танцы на льду, МС'), 'МС, Танцы')

    def test_sport_and_junior_ranks_unchanged(self):
        self.assertEqual(
            normalize_category_name('1 спортивный', 'F'),
            '1 Спортивный, Девочки',
        )
        self.assertEqual(
            normalize_category_name('1 юношеский', 'F'),
            '1 Юношеский, Девочки',
        )
        self.assertEqual(
            normalize_category_name('Парное катание, 1 спортивный'),
            '1 Спортивный, Пары',
        )


if __name__ == '__main__':
    unittest.main()
