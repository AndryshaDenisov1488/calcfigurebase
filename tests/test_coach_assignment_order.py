#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Out-of-order XML import must not demote the chronologically later coach."""

import os
import unittest
from datetime import date

os.environ.setdefault('ALLOW_INSECURE_DEFAULTS', '1')

from flask import Flask

from extensions import db
from models import Athlete, Category, Coach, CoachAssignment, Event, Participant
from services.coach_registry import record_assignment_on_import


class CoachAssignmentOrderTest(unittest.TestCase):
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

        self.athlete = Athlete(first_name='Анна', last_name='Тестова', birth_date=date(2012, 1, 1))
        self.coach_a = Coach(name='Тренер А', normalized_name='тренер а')
        self.coach_b = Coach(name='Тренер Б', normalized_name='тренер б')
        db.session.add_all([self.athlete, self.coach_a, self.coach_b])
        db.session.flush()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _event_with_participant(self, name, begin):
        event = Event(name=name, begin_date=begin)
        db.session.add(event)
        db.session.flush()
        category = Category(event_id=event.id, name='Кат', normalized_name='1 Юношеский, Девочки')
        db.session.add(category)
        db.session.flush()
        participant = Participant(
            event_id=event.id,
            category_id=category.id,
            athlete_id=self.athlete.id,
        )
        db.session.add(participant)
        db.session.flush()
        return event, participant

    def test_historical_import_keeps_current_coach(self):
        """
        Trigger: import a 2025 event (coach A) first, then a 2023 event (coach B).
        Old code closed A and made B current with end_date before start_date.
        """
        later, p_later = self._event_with_participant('Later', date(2025, 3, 1))
        record_assignment_on_import(
            athlete_id=self.athlete.id,
            coach_id=self.coach_a.id,
            participant_id=p_later.id,
            event_id=later.id,
            event_date=later.begin_date,
        )
        db.session.flush()

        earlier, p_earlier = self._event_with_participant('Earlier', date(2023, 5, 1))
        record_assignment_on_import(
            athlete_id=self.athlete.id,
            coach_id=self.coach_b.id,
            participant_id=p_earlier.id,
            event_id=earlier.id,
            event_date=earlier.begin_date,
        )
        db.session.commit()

        current = CoachAssignment.query.filter_by(
            athlete_id=self.athlete.id,
            is_current=True,
        ).one()
        self.assertEqual(current.coach_id, self.coach_a.id)
        self.assertIsNone(current.end_date)

        historical = CoachAssignment.query.filter_by(
            athlete_id=self.athlete.id,
            coach_id=self.coach_b.id,
        ).one()
        self.assertFalse(historical.is_current)
        self.assertEqual(historical.end_date, date(2025, 3, 1))
        self.assertLess(historical.start_date, current.start_date)

    def test_forward_transition_still_updates_current(self):
        earlier, p_earlier = self._event_with_participant('Earlier', date(2023, 5, 1))
        record_assignment_on_import(
            athlete_id=self.athlete.id,
            coach_id=self.coach_b.id,
            participant_id=p_earlier.id,
            event_id=earlier.id,
            event_date=earlier.begin_date,
        )
        db.session.flush()

        later, p_later = self._event_with_participant('Later', date(2025, 3, 1))
        record_assignment_on_import(
            athlete_id=self.athlete.id,
            coach_id=self.coach_a.id,
            participant_id=p_later.id,
            event_id=later.id,
            event_date=later.begin_date,
        )
        db.session.commit()

        current = CoachAssignment.query.filter_by(
            athlete_id=self.athlete.id,
            is_current=True,
        ).one()
        self.assertEqual(current.coach_id, self.coach_a.id)

        previous = CoachAssignment.query.filter_by(
            athlete_id=self.athlete.id,
            coach_id=self.coach_b.id,
        ).one()
        self.assertFalse(previous.is_current)
        self.assertEqual(previous.end_date, date(2025, 3, 1))


if __name__ == '__main__':
    unittest.main()
