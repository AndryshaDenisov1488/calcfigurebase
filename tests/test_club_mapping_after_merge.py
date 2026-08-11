"""Regression: club_mapping must follow merge_all_duplicates keep ids."""

import os
import unittest

os.environ.setdefault('ALLOW_INSECURE_DEFAULTS', '1')
os.environ.setdefault('SECRET_KEY', 'test-secret-key')
os.environ.setdefault('ADMIN_PASSWORD', 'test-admin')


class ClubMappingAfterMergeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app_factory import create_app
        cls.app = create_app()
        cls.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        cls.app.config['TESTING'] = True
        cls.app.config['WTF_CSRF_ENABLED'] = False

    def setUp(self):
        from extensions import db
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.session.remove()
        db.drop_all()
        db.create_all()

    def tearDown(self):
        from extensions import db
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_mapping_remapped_when_exact_match_club_is_deleted(self):
        """
        Legacy near-duplicate clubs in DB: import exact-matches the smaller one,
        merge deletes it into the larger — club_mapping must point at keep id.
        """
        from extensions import db
        from models import Club, Athlete
        from services.club_registry import ClubRegistry

        keep = Club(name='СШОР №1 Москва', city='Москва')
        remove = Club(name='СШОР №2 Москва', city='Москва')
        db.session.add_all([keep, remove])
        db.session.flush()

        for i in range(3):
            db.session.add(Athlete(
                first_name=f'A{i}',
                last_name=f'B{i}',
                club_id=keep.id,
                lookup_key=f'name:a{i}:b{i}:2000-01-0{i + 1}',
            ))
        db.session.flush()
        keep_id = keep.id
        remove_id = remove.id

        club_mapping = {}
        registry = ClubRegistry()
        xml_club = {
            'id': 'xml-1',
            'name': 'СШОР №2 Москва',
            'short_name': '',
            'country': '',
            'city': 'Москва',
        }
        club = registry.register(xml_club)
        db.session.flush()
        club_mapping[xml_club['id']] = club.id
        self.assertEqual(club_mapping['xml-1'], remove_id)

        merged_count, id_remap = registry.merge_all_duplicates()
        self.assertGreaterEqual(merged_count, 1)
        self.assertEqual(id_remap.get(remove_id), keep_id)

        ClubRegistry.apply_club_id_remap(club_mapping, id_remap)
        self.assertEqual(club_mapping['xml-1'], keep_id)
        self.assertIsNotNone(db.session.get(Club, club_mapping['xml-1']))
        self.assertIsNone(db.session.get(Club, remove_id))

    def test_apply_club_id_remap_chains(self):
        from services.club_registry import ClubRegistry

        mapping = {'a': 10, 'b': 20}
        remap = {10: 20, 20: 30}
        ClubRegistry.apply_club_id_remap(mapping, remap)
        self.assertEqual(mapping, {'a': 30, 'b': 30})


if __name__ == '__main__':
    unittest.main()
