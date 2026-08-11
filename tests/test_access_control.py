import os
import unittest
from unittest.mock import patch


class AccessControlTests(unittest.TestCase):
    def _make_client(self, **env):
        test_env = {
            'SECRET_KEY': 'test-secret',
            'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
            'ADMIN_USERNAME': 'admin',
            'ADMIN_PASSWORD': 'admin-pass',
            'ALLOW_INSECURE_DEFAULTS': '',
            'DISABLE_PUBLIC_API_AUTH': '',
            'DISABLE_PUBLIC_HTML_GATE': '',
            'FLASK_DEBUG': '',
        }
        test_env.update(env)
        patcher = patch.dict(os.environ, test_env, clear=False)
        patcher.start()
        self.addCleanup(patcher.stop)

        from app_factory import create_app
        from extensions import db

        app = create_app()
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        with app.app_context():
            db.create_all()
        return app.test_client()

    def test_api_key_only_configuration_still_gates_public_html(self):
        client = self._make_client(SITE_READ_PASSWORD='', API_KEYS='integration-key')

        self.assertEqual(client.get('/api/events').status_code, 403)
        self.assertEqual(
            client.get('/api/events', headers={'X-API-Key': 'integration-key'}).status_code,
            200,
        )

        response = client.get('/athletes')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/site-access?next=/athletes', response.headers['Location'])

    def test_reader_password_unlocks_gated_html(self):
        client = self._make_client(SITE_READ_PASSWORD='judge-pass', API_KEYS='')

        response = client.get('/athletes')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/site-access?next=/athletes', response.headers['Location'])

        login_response = client.post(
            '/site-access',
            data={'password': 'judge-pass', 'next': '/athletes'},
        )
        self.assertEqual(login_response.status_code, 302)
        self.assertEqual(login_response.headers['Location'], '/athletes')
        self.assertEqual(client.get('/athletes').status_code, 200)


if __name__ == '__main__':
    unittest.main()
