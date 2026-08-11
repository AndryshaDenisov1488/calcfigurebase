#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fuzzy club matching must not auto-merge distinct schools."""

import os
import unittest

os.environ.setdefault('ALLOW_INSECURE_DEFAULTS', '1')

from flask import Flask

from extensions import db
from models import Athlete, Club
from services.club_registry import ClubRegistry


class ClubFuzzySimilarityTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
        )
        db.init_app(self.app)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        self.registry = ClubRegistry()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_similarity_rejects_different_school_numbers(self):
        """SequenceMatcher alone scores these ≥0.85; digit tokens must block merge."""
        cases = [
            ('СШОР №1 Москва', 'СШОР №2 Москва'),
            ('СДЮСШОР №1', 'СДЮСШОР №2'),
            ('СШОР №1', 'СШОР №11'),
            ('школа олимпийского резерва 1', 'школа олимпийского резерва 2'),
        ]
        for left, right in cases:
            with self.subTest(left=left, right=right):
                self.assertEqual(self.registry._calculate_similarity(left, right), 0.0)

    def test_similarity_rejects_different_school_org_types(self):
        """
        СШОР vs СДЮШОР/СДЮСШОР — разные типы учреждений.
        SequenceMatcher даёт ≥0.85 на типичных названиях с общим префиксом ГБУ/МБУ.
        """
        cases = [
            ('ГБУ ДО СШОР', 'ГБУ ДО СДЮСШОР'),
            ('ГБУ ДО СШОР', 'ГБУ ДО СДЮШОР'),
            ('МБУ СШОР', 'МБУ СДЮШОР'),
            ('СШОР «Лидер»', 'СДЮСШОР «Лидер»'),
            ('МОУ ДО СШОР', 'МОУ ДО СДЮСШОР'),
        ]
        for left, right in cases:
            with self.subTest(left=left, right=right):
                self.assertEqual(self.registry._calculate_similarity(left, right), 0.0)
                self.assertLess(
                    self.registry._calculate_similarity(left, right),
                    0.85,
                )

    def test_sdyushor_spelling_variants_still_can_match(self):
        """СДЮШОР и СДЮСШОР — варианты одной аббревиатуры; не блокируем по типу."""
        score = self.registry._calculate_similarity(
            'СДЮШОР Москомспорта',
            'СДЮСШОР Москомспорта',
        )
        self.assertGreaterEqual(score, 0.85)

    def test_similarity_still_allows_exact_and_typo_without_clash(self):
        self.assertEqual(
            self.registry._calculate_similarity('Динамо', 'Динамо'),
            1.0,
        )
        self.assertGreaterEqual(
            self.registry._calculate_similarity('Динамо Москва', 'Динамо  Москва'),
            0.85,
        )

    def test_register_does_not_attach_to_different_org_type(self):
        existing = Club(name='ГБУ ДО СШОР', city='Москва')
        db.session.add(existing)
        db.session.commit()

        registered = self.registry.register({'name': 'ГБУ ДО СДЮСШОР', 'city': 'Москва'})
        db.session.flush()

        self.assertIsNotNone(registered)
        self.assertNotEqual(registered.id, existing.id)
        self.assertEqual(Club.query.count(), 2)

    def test_merge_all_duplicates_keeps_different_org_types(self):
        a = Club(name='МБУ СШОР')
        b = Club(name='МБУ СДЮШОР')
        db.session.add_all([a, b])
        db.session.flush()
        athlete = Athlete(first_name='Анна', last_name='Иванова', club_id=b.id)
        db.session.add(athlete)
        db.session.commit()

        merged = self.registry.merge_all_duplicates()
        self.assertEqual(merged, 0)
        self.assertEqual(Club.query.count(), 2)
        db.session.refresh(athlete)
        self.assertEqual(athlete.club_id, b.id)


if __name__ == '__main__':
    unittest.main()
