#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cross-process Google Sheets export lock regressions."""

import multiprocessing
import tempfile
import time
import unittest
from types import SimpleNamespace


def _child_hold_lock(instance_path, ready_event, release_event):
    """Acquire export flock in a child process and hold until signaled."""
    from routes import admin as admin_mod

    app_obj = SimpleNamespace(instance_path=instance_path)
    lock_file = admin_mod._try_acquire_export_lock(app_obj)
    if lock_file is None:
        ready_event.set()
        return 2
    ready_event.set()
    release_event.wait(timeout=10)
    admin_mod._release_export_lock(lock_file)
    return 0


class GoogleExportLockTests(unittest.TestCase):
    def test_second_acquire_fails_while_held_in_same_process(self):
        from routes import admin as admin_mod

        with tempfile.TemporaryDirectory() as tmp:
            app_obj = SimpleNamespace(instance_path=tmp)
            first = admin_mod._try_acquire_export_lock(app_obj)
            self.assertIsNotNone(first)
            second = admin_mod._try_acquire_export_lock(app_obj)
            self.assertIsNone(second)
            admin_mod._release_export_lock(first)
            third = admin_mod._try_acquire_export_lock(app_obj)
            self.assertIsNotNone(third)
            admin_mod._release_export_lock(third)

    def test_cross_process_exclusive_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            ready = multiprocessing.Event()
            release = multiprocessing.Event()
            proc = multiprocessing.Process(
                target=_child_hold_lock,
                args=(tmp, ready, release),
            )
            proc.start()
            self.assertTrue(ready.wait(timeout=5))

            from routes import admin as admin_mod

            app_obj = SimpleNamespace(instance_path=tmp)
            contested = admin_mod._try_acquire_export_lock(app_obj)
            self.assertIsNone(
                contested,
                'second Gunicorn worker must not start a concurrent Sheets export',
            )

            release.set()
            proc.join(timeout=5)
            self.assertEqual(proc.exitcode, 0)

            after = admin_mod._try_acquire_export_lock(app_obj)
            self.assertIsNotNone(after)
            admin_mod._release_export_lock(after)

    def test_reconcile_clears_stale_running_flag(self):
        from routes import admin as admin_mod

        with tempfile.TemporaryDirectory() as tmp:
            app_obj = SimpleNamespace(instance_path=tmp)
            admin_mod._write_export_state(
                app_obj,
                {
                    'running': True,
                    'started_at': int(time.time()) - 100,
                    'finished_at': None,
                    'success': None,
                    'message': 'Экспорт запущен. Это может занять несколько минут...',
                    'url': None,
                },
            )
            state = admin_mod._reconcile_export_state(app_obj)
            self.assertFalse(state['running'])
            self.assertIs(state['success'], False)
            self.assertIn('прерван', state['message'])

    def test_reconcile_keeps_running_when_lock_held(self):
        from routes import admin as admin_mod

        with tempfile.TemporaryDirectory() as tmp:
            app_obj = SimpleNamespace(instance_path=tmp)
            lock_file = admin_mod._try_acquire_export_lock(app_obj)
            self.assertIsNotNone(lock_file)
            try:
                admin_mod._set_export_state_running(app_obj)
                state = admin_mod._reconcile_export_state(app_obj)
                self.assertTrue(state['running'])
            finally:
                admin_mod._release_export_lock(lock_file)

    def test_background_start_rejects_second_caller(self):
        from routes import admin as admin_mod

        with tempfile.TemporaryDirectory() as tmp:
            app_obj = SimpleNamespace(instance_path=tmp)

            # Avoid real Google API: hold lock as if another worker is exporting.
            held = admin_mod._try_acquire_export_lock(app_obj)
            self.assertIsNotNone(held)
            try:
                started = admin_mod._start_google_export_background(app_obj)
                self.assertFalse(started)
            finally:
                admin_mod._release_export_lock(held)


if __name__ == '__main__':
    unittest.main()
