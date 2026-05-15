#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import unittest
from datetime import date

os.environ.setdefault('ALLOW_INSECURE_DEFAULTS', '1')

from flask import Flask

from extensions import db
from models import Athlete
from services.import_birth_conflict import (
    apply_birth_conflict_resolutions_json,
    find_birth_date_conflicts,
)


class FakeParser:
    def __init__(self, persons):
        self.persons = persons
        self.participants = [
            {
                'person_id': person['id'],
            }
            for person in persons
        ]


class ImportBirthConflictTest(unittest.TestCase):
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

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_conflicts_include_source_key(self):
        athlete = Athlete(
            first_name='Beta',
            last_name='Two',
            full_name_xml='Two Beta',
            birth_date=date(2001, 1, 1),
        )
        db.session.add(athlete)
        db.session.commit()

        parser = FakeParser([
            {
                'id': 'P1',
                'full_name': 'Two Beta',
                'last_name': 'Two',
                'birth_date': '20020202',
            },
        ])

        conflicts = find_birth_date_conflicts(parser, source_key='file-1')

        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]['source_key'], 'file-1')
        self.assertEqual(conflicts[0]['person_id'], 'P1')
        self.assertEqual(conflicts[0]['athlete_id'], athlete.id)

    def test_apply_uses_source_key_when_person_ids_overlap(self):
        athlete = Athlete(
            first_name='Beta',
            last_name='Two',
            full_name_xml='Two Beta',
            birth_date=date(2001, 1, 1),
        )
        db.session.add(athlete)
        db.session.commit()

        first_file = FakeParser([
            {
                'id': 'P1',
                'full_name': 'One Alpha',
                'last_name': 'One',
                'birth_date': '19900101',
            },
        ])
        second_file = FakeParser([
            {
                'id': 'P1',
                'full_name': 'Two Beta',
                'last_name': 'Two',
                'birth_date': '20020202',
            },
        ])

        apply_birth_conflict_resolutions_json(
            [
                {
                    'source_key': '1',
                    'person_id': 'P1',
                    'athlete_id': athlete.id,
                    'use': 'xml',
                }
            ],
            [('0', first_file), ('1', second_file)],
        )

        self.assertEqual(athlete.birth_date, date(2002, 2, 2))

    def test_apply_skips_unscoped_multi_file_resolution(self):
        athlete = Athlete(
            first_name='Beta',
            last_name='Two',
            full_name_xml='Two Beta',
            birth_date=date(2001, 1, 1),
        )
        db.session.add(athlete)
        db.session.commit()

        first_file = FakeParser([
            {
                'id': 'P1',
                'full_name': 'One Alpha',
                'last_name': 'One',
                'birth_date': '19900101',
            },
        ])
        second_file = FakeParser([
            {
                'id': 'P1',
                'full_name': 'Two Beta',
                'last_name': 'Two',
                'birth_date': '20020202',
            },
        ])

        apply_birth_conflict_resolutions_json(
            [
                {
                    'person_id': 'P1',
                    'athlete_id': athlete.id,
                    'use': 'xml',
                }
            ],
            [first_file, second_file],
        )

        self.assertEqual(athlete.birth_date, date(2001, 1, 1))


if __name__ == '__main__':
    unittest.main()
