import os
import tempfile
import unittest
from datetime import date
from pathlib import Path


os.environ.setdefault("ALLOW_INSECURE_DEFAULTS", "1")
os.environ.setdefault("DISABLE_PUBLIC_API_AUTH", "1")
_db_fd, _db_path = tempfile.mkstemp(prefix="calcfigurebase-pairs-", suffix=".db")
os.close(_db_fd)
os.environ["DATABASE_URL"] = f"sqlite:///{_db_path.replace(os.sep, '/')}"

from app_factory import create_app
from extensions import db
from models import Athlete
from parsers.isu_calcfs_parser import ISUCalcFSParser
from scripts.backfill_pair_members_from_xml import backfill
from services.import_service import save_to_database


PAIR_XML = """<?xml version="1.0" encoding="UTF-8"?>
<ISUCalcFS>
  <Event EVT_ID="1" EVT_NAME="Тест" EVT_BEGDAT="20260824">
    <Categories_List>
      <Category CAT_ID="10" EVT_ID="1" CAT_NAME="Танцы на льду" CAT_GENDER="P"/>
    </Categories_List>
    <Participants_List>
      <Person_Couple_Team
        PCT_ID="30"
        PCT_EXTDT="pair-30"
        PCT_TYPE="COU"
        PCT_PLNAME="София Павловна ЩЕГЛОВА / Александр Викторович МУШКИН"
        PCT_CNAME="София ЩЕГЛОВА / Александр МУШКИН"
        PCT_PSNAME="ЩЕГЛОВА / МУШКИН"
        PCT_GNAME="София"
        PCT_FNAMEC="ЩЕГЛОВА"
        PCT_BDAY="20131209"
        PCT_PGNAME="Александр"
        PCT_PFNAMC="МУШКИН"
        PCT_PBDAY="20080416">
        <Team_Members>
          <Person
            PCT_ID="28"
            PCT_EXTDT="skater-28"
            PCT_TYPE="PER"
            PCT_PLNAME="София Павловна ЩЕГЛОВА"
            PCT_GNAME="София"
            PCT_FNAMEC="ЩЕГЛОВА"
            PCT_BDAY="20131209"
            PCT_GENDER="F"/>
          <Person
            PCT_ID="29"
            PCT_EXTDT="skater-29"
            PCT_TYPE="PER"
            PCT_PLNAME="Александр Викторович МУШКИН"
            PCT_GNAME="Александр"
            PCT_FNAMEC="МУШКИН"
            PCT_BDAY="20080416"
            PCT_GENDER="M"/>
        </Team_Members>
      </Person_Couple_Team>
    </Participants_List>
    <Participant PAR_ID="40" CAT_ID="10" PCT_ID="30"/>
  </Event>
</ISUCalcFS>
"""


class PairMemberParsingTestCase(unittest.TestCase):
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

    def test_both_pair_members_are_preserved(self):
        with tempfile.NamedTemporaryFile("w", suffix=".xml", encoding="utf-8", delete=False) as handle:
            handle.write(PAIR_XML)
            path = Path(handle.name)
        try:
            parser = ISUCalcFSParser(path)
            parser.parse()
            self.assertEqual(len(parser.persons), 1)
            pair = parser.persons[0]

            self.assertEqual(pair["birth_date"], date(2013, 12, 9))
            self.assertEqual(pair["primary_external_id"], "skater-28")
            self.assertEqual(pair["primary_first_name"], "София")
            self.assertEqual(pair["primary_last_name"], "ЩЕГЛОВА")
            self.assertEqual(pair["primary_patronymic"], "Павловна")
            self.assertEqual(pair["primary_birth_date"], date(2013, 12, 9))
            self.assertEqual(pair["partner_external_id"], "skater-29")
            self.assertEqual(pair["partner_first_name"], "Александр")
            self.assertEqual(pair["partner_last_name"], "МУШКИН")
            self.assertEqual(pair["partner_patronymic"], "Викторович")
            self.assertEqual(pair["partner_birth_date"], date(2008, 4, 16))
        finally:
            path.unlink(missing_ok=True)

    def test_pair_member_details_are_saved_to_database(self):
        with tempfile.NamedTemporaryFile("w", suffix=".xml", encoding="utf-8", delete=False) as handle:
            handle.write(PAIR_XML)
            path = Path(handle.name)
        try:
            parser = ISUCalcFSParser(path)
            parser.parse()
            save_to_database(parser)

            pair = Athlete.query.one()
            self.assertTrue(pair.is_pair)
            self.assertEqual(pair.primary_member_full_name, "ЩЕГЛОВА София Павловна")
            self.assertEqual(pair.primary_birth_date, date(2013, 12, 9))
            self.assertEqual(pair.partner_member_full_name, "МУШКИН Александр Викторович")
            self.assertEqual(pair.partner_birth_date, date(2008, 4, 16))
        finally:
            path.unlink(missing_ok=True)

    def test_backfill_has_dry_run_and_apply_modes(self):
        with tempfile.NamedTemporaryFile("w", suffix=".xml", encoding="utf-8", delete=False) as handle:
            handle.write(PAIR_XML)
            path = Path(handle.name)
        try:
            parser = ISUCalcFSParser(path)
            parser.parse()
            save_to_database(parser)
            pair = Athlete.query.one()
            for field in (
                "primary_external_id",
                "primary_first_name",
                "primary_last_name",
                "primary_patronymic",
                "primary_birth_date",
                "primary_gender",
                "partner_external_id",
                "partner_first_name",
                "partner_last_name",
                "partner_patronymic",
                "partner_birth_date",
                "partner_gender",
            ):
                setattr(pair, field, None)
            db.session.commit()

            dry_run = backfill(path, apply=False)
            self.assertEqual(dry_run["matched"], 1)
            self.assertEqual(dry_run["updated"], 1)
            self.assertIsNone(Athlete.query.one().partner_birth_date)

            applied = backfill(path, apply=True)
            self.assertEqual(applied["updated"], 1)
            self.assertEqual(Athlete.query.one().partner_birth_date, date(2008, 4, 16))
        finally:
            path.unlink(missing_ok=True)


def tearDownModule():
    try:
        os.unlink(_db_path)
    except OSError:
        pass


if __name__ == "__main__":
    unittest.main()
