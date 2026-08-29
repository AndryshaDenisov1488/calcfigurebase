#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Club merge must not wipe the surrounding import transaction on failure."""

import os
import unittest
from datetime import date

os.environ.setdefault('ALLOW_INSECURE_DEFAULTS', '1')

from flask import Flask

from extensions import db
from models import Category, Club, Event
from services.club_registry import ClubRegistry


class ClubMergeSavepointTest(unittest.TestCase):
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

    def test_merge_failure_does_not_orphan_categories_from_open_import(self):
        """
        Trigger: merge_all_duplicates hits an error mid-import (e.g. concurrent
        workers / flush failure). Old code called session.rollback(), wiping the
        uncommitted Event, while save_to_database continued and committed
        Category rows with a dangling event_id on SQLite.
        """
        event = Event(name='Import Event', begin_date=date(2026, 7, 1))
        db.session.add(event)
        db.session.flush()
        event_id = event.id

        keep = Club(name='Duplicate Club Name ZZZZ')
        remove = Club(name='Duplicate Club Name ZZZZ')
        db.session.add_all([keep, remove])
        db.session.flush()

        original_delete = db.session.delete

        def boom_delete(obj):
            if getattr(obj, 'name', None) == 'Duplicate Club Name ZZZZ' and obj.id == remove.id:
                raise RuntimeError('simulated merge failure')
            return original_delete(obj)

        db.session.delete = boom_delete
        try:
            ClubRegistry().merge_all_duplicates()
        finally:
            db.session.delete = original_delete

        # Import continues after a failed merge attempt.
        self.assertEqual(Event.query.count(), 1)
        category = Category(event_id=event_id, name='Cat', normalized_name='1 Юношеский, Девочки')
        db.session.add(category)
        db.session.commit()

        self.assertEqual(Event.query.count(), 1)
        self.assertEqual(Category.query.count(), 1)
        self.assertEqual(Category.query.first().event_id, Event.query.first().id)


if __name__ == '__main__':
    unittest.main()
