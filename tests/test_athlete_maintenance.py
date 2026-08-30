import os
import tempfile
import unittest
from datetime import date
from pathlib import Path

from openpyxl import Workbook


os.environ.setdefault("ALLOW_INSECURE_DEFAULTS", "1")
os.environ.setdefault("DISABLE_PUBLIC_API_AUTH", "1")
_db_fd, _db_path = tempfile.mkstemp(prefix="calcfigurebase-maintenance-", suffix=".db")
os.close(_db_fd)
os.environ["DATABASE_URL"] = f"sqlite:///{_db_path.replace(os.sep, '/')}"

from app_factory import create_app
from extensions import db
from models import Athlete
from scripts.sync_pair_birth_dates_from_registry import sync_pair_birth_dates
from services.athlete_registry import AthleteRegistry


class AthleteMaintenanceTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.context.pop()

    def test_lookup_key_treats_e_and_yo_as_the_same_letter(self):
        registry = AthleteRegistry()
        without_yo = registry._make_lookup_key(
            {
                "first_name": "Алена",
                "last_name": "Бухмарева",
                "birth_date": date(2017, 11, 11),
            }
        )
        with_yo = registry._make_lookup_key(
            {
                "first_name": "Алёна",
                "last_name": "Бухмарёва",
                "birth_date": date(2017, 11, 11),
            }
        )
        self.assertEqual(without_yo, with_yo)

    def test_get_or_create_reuses_legacy_yo_lookup_key(self):
        """Re-import must attach to the existing card, not create a split career.

        Production rows stored lookup_key with ё before 495bc13 folded the key.
        Exact filter_by(lookup_key=folded) misses those rows.
        """
        registry = AthleteRegistry()
        birth = date(2017, 11, 11)
        existing = Athlete(
            first_name="Алёна",
            last_name="Бухмарева",
            full_name_xml="Алёна Бухмарева",
            birth_date=birth,
            lookup_key=f"name:алёна:бухмарева:{birth}",
        )
        db.session.add(existing)
        db.session.commit()
        existing_id = existing.id

        reused = registry.get_or_create(
            {
                "first_name": "Алена",
                "last_name": "Бухмарева",
                "birth_date": birth,
            }
        )
        db.session.flush()

        self.assertEqual(reused.id, existing_id)
        self.assertEqual(Athlete.query.count(), 1)
        self.assertEqual(
            reused.lookup_key,
            f"name:алена:бухмарева:{birth}",
        )

        reused_yo = registry.get_or_create(
            {
                "first_name": "Алёна",
                "last_name": "Бухмарева",
                "birth_date": birth,
            }
        )
        db.session.flush()
        self.assertEqual(reused_yo.id, existing_id)
        self.assertEqual(Athlete.query.count(), 1)

    def test_pair_dates_are_dry_run_then_synchronized_from_xlsx(self):
        pair = Athlete(
            first_name="Таисия ГУСЕВА / Даниил ОВЧИННИКОВ",
            last_name="ГУСЕВА / ОВЧИННИКОВ",
            full_name_xml="Таисия Денисовна ГУСЕВА / Даниил Дмитриевич ОВЧИННИКОВ",
            birth_date=date(2012, 8, 12),
            gender="P",
            primary_first_name="Таисия",
            primary_last_name="ГУСЕВА",
            primary_patronymic="Денисовна",
            primary_birth_date=date(2012, 8, 12),
            partner_first_name="Даниил",
            partner_last_name="ОВЧИННИКОВ",
            partner_patronymic="Дмитриевич",
            partner_birth_date=date(2008, 1, 1),
        )
        db.session.add(pair)
        db.session.commit()

        workbook = Workbook()
        worksheet = workbook.active
        worksheet.append(["Фамилия", "Имя", "Отчество", "Дата рождения"])
        worksheet.append(["Гусева", "Таисия", "Денисовна", date(2015, 9, 3)])
        worksheet.append(["Овчинников", "Даниил", "Дмитриевич", date(2008, 1, 1)])
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as handle:
            registry_path = Path(handle.name)
        workbook.save(registry_path)

        try:
            dry_run = sync_pair_birth_dates(registry_path, apply=False)
            self.assertEqual(dry_run["updated_members"], 1)
            self.assertEqual(Athlete.query.one().primary_birth_date, date(2012, 8, 12))

            applied = sync_pair_birth_dates(registry_path, apply=True)
            self.assertEqual(applied["updated_members"], 1)
            updated_pair = Athlete.query.one()
            self.assertEqual(updated_pair.primary_birth_date, date(2015, 9, 3))
            self.assertEqual(updated_pair.birth_date, date(2015, 9, 3))
            self.assertEqual(updated_pair.partner_birth_date, date(2008, 1, 1))
        finally:
            registry_path.unlink(missing_ok=True)


def tearDownModule():
    try:
        os.unlink(_db_path)
    except OSError:
        pass


if __name__ == "__main__":
    unittest.main()
