import os
import unittest
from unittest.mock import patch

from flask import Flask, session

from utils.access_control import SESSION_SITE_READER_KEY, request_has_api_access


class RequestHasApiAccessTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.secret_key = 'test-secret'
        self.app.config['API_KEYS'] = ['secret-token']

    def test_accepts_configured_x_api_key(self):
        with patch.dict(os.environ, {'DISABLE_PUBLIC_API_AUTH': ''}, clear=False):
            with self.app.test_request_context('/api/events', headers={'X-API-Key': 'secret-token'}):
                self.assertTrue(request_has_api_access())

    def test_rejects_anonymous_request_without_token_or_session(self):
        with patch.dict(os.environ, {'DISABLE_PUBLIC_API_AUTH': ''}, clear=False):
            with self.app.test_request_context('/api/events'):
                self.assertFalse(request_has_api_access())

    def test_accepts_reader_session_without_token(self):
        with patch.dict(os.environ, {'DISABLE_PUBLIC_API_AUTH': ''}, clear=False):
            with self.app.test_request_context('/api/events'):
                session[SESSION_SITE_READER_KEY] = True
                self.assertTrue(request_has_api_access())


if __name__ == '__main__':
    unittest.main()
