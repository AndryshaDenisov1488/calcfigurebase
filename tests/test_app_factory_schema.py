#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regression tests for startup schema guards."""

import os
import sqlite3
import tempfile
import unittest

from sqlalchemy import inspect


class EventRankSchemaGuardTest(unittest.TestCase):
    def test_create_app_adds_event_rank_to_existing_database(self):
        from app_factory import create_app
        from extensions import db

        old_database_url = os.environ.get('DATABASE_URL')
        old_secret_key = os.environ.get('SECRET_KEY')

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, 'figure_skating.db')
            conn = sqlite3.connect(db_path)
            try:
                conn.execute(
                    """
                    CREATE TABLE event (
                        id INTEGER PRIMARY KEY,
                        name VARCHAR(200) NOT NULL,
                        begin_date DATE
                    )
                    """
                )
                conn.commit()
            finally:
                conn.close()

            os.environ['DATABASE_URL'] = f'sqlite:///{db_path}'
            os.environ['SECRET_KEY'] = 'test-secret'
            try:
                app = create_app()
                with app.app_context():
                    inspector = inspect(db.engine)
                    columns = {column['name'] for column in inspector.get_columns('event')}
                    indexes = {index['name'] for index in inspector.get_indexes('event')}

                self.assertIn('event_rank', columns)
                self.assertIn('ix_event_event_rank', indexes)
            finally:
                if old_database_url is None:
                    os.environ.pop('DATABASE_URL', None)
                else:
                    os.environ['DATABASE_URL'] = old_database_url
                if old_secret_key is None:
                    os.environ.pop('SECRET_KEY', None)
                else:
                    os.environ['SECRET_KEY'] = old_secret_key


if __name__ == '__main__':
    unittest.main()
