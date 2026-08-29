#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Numbered school names must not auto-merge via fuzzy club matching."""

import os
import unittest

os.environ.setdefault('ALLOW_INSECURE_DEFAULTS', '1')

from flask import Flask

from extensions import db
from models import Athlete, Club
from services.club_registry import ClubRegistry


class ClubNumberedSimilarityTest(unittest.TestCase):
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
                self.assertLess(
                    self.registry._calculate_similarity(left, right),
                    0.85,
                )

    def test_similarity_still_allows_exact_and_typo_without_digit_clash(self):
        self.assertEqual(
            self.registry._calculate_similarity('Динамо', 'Динамо'),
            1.0,
        )
        # Same digit tokens (or none): SequenceMatcher path remains available.
        self.assertGreaterEqual(
            self.registry._calculate_similarity('Динамо Москва', 'Динамо  Москва'),
            0.85,
        )
        self.assertEqual(
            self.registry._calculate_similarity('СШОР №1 Москва', 'СШОР №1 Москва'),
            1.0,
        )

    def test_register_does_not_attach_to_different_numbered_school(self):
        """
        Trigger: DB already has «СШОР №1 Москва»; XML brings «СШОР №2 Москва».
        Old code fuzzy-matched at ~0.93 and assigned athletes to the wrong club.
        """
        existing = Club(name='СШОР №1 Москва', city='Москва')
        db.session.add(existing)
        db.session.commit()

        registered = self.registry.register({'name': 'СШОР №2 Москва', 'city': 'Москва'})
        db.session.flush()

        self.assertIsNotNone(registered)
        self.assertNotEqual(registered.id, existing.id)
        self.assertEqual(Club.query.count(), 2)
        names = {c.name for c in Club.query.all()}
        self.assertEqual(names, {'СШОР №1 Москва', 'СШОР №2 Москва'})

    def test_merge_all_duplicates_keeps_numbered_schools_separate(self):
        c1 = Club(name='СШОР №1 Москва')
        c2 = Club(name='СШОР №2 Москва')
        db.session.add_all([c1, c2])
        db.session.flush()
        a1 = Athlete(first_name='Анна', last_name='Иванова', club_id=c1.id)
        a2 = Athlete(first_name='Мария', last_name='Петрова', club_id=c2.id)
        db.session.add_all([a1, a2])
        db.session.commit()

        merged = self.registry.merge_all_duplicates()
        db.session.commit()

        self.assertEqual(merged, 0)
        self.assertEqual(Club.query.count(), 2)
        self.assertEqual(Athlete.query.get(a1.id).club_id, c1.id)
        self.assertEqual(Athlete.query.get(a2.id).club_id, c2.id)


if __name__ == '__main__':
    unittest.main()
