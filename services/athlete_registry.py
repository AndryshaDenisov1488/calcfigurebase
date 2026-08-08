"""Athlete registry with deduplication by name+birth date."""

from models import db, Athlete
from utils.normalizers import normalize_string


class AthleteRegistry:
    """Registry for athletes with safe merge logic."""

    def _make_lookup_key(self, person_data):
        first_name = normalize_string(person_data.get('first_name', '')).lower()
        last_name = normalize_string(person_data.get('last_name', '')).lower()
        birth_date = person_data.get('birth_date')
        if first_name and last_name and birth_date:
            return f"name:{first_name}:{last_name}:{birth_date}"
        return None

    def _should_update(self, old_value, new_value):
        if not new_value:
            return False
        if not old_value:
            return True
        return len(str(new_value)) > len(str(old_value))

    def _find_same_name_fallback(self, first_name, last_name, birth_date):
        """
        When lookup_key is missing or missed, reuse an existing card instead of
        inserting a duplicate for the same structured name.

        - Prefer same first+last with NULL birth_date (oldest id).
        - If incoming also has no birth_date and there is exactly one athlete
          with that name (any birth), reuse it — XML often omits PCT_BDAY on
          later tournaments for the same person already in the DB.
        - If multiple named athletes with different births exist and incoming
          has no birth, do not guess (return None).

        Name match uses exact normalized strings (as stored by get_or_create).
        Avoid DB lower() — SQLite LOWER() is ASCII-only and breaks Cyrillic.
        """
        if not first_name or not last_name:
            return None

        # Narrow by last_name (indexed), then match first_name in Python.
        rows = (
            Athlete.query.filter(Athlete.last_name == last_name)
            .order_by(Athlete.id.asc())
            .all()
        )
        first_l = first_name.lower()
        same_name = [
            a for a in rows
            if (a.first_name or '').lower() == first_l
        ]
        null_birth = [a for a in same_name if a.birth_date is None]
        if null_birth:
            return null_birth[0]

        if birth_date:
            return None

        if len(same_name) == 1:
            return same_name[0]
        return None

    def get_or_create(self, person_data):
        """Finds or creates an athlete with merge protection."""
        if not person_data:
            return None

        lookup_key = self._make_lookup_key(person_data)
        first_name = normalize_string(person_data.get('first_name', ''))
        last_name = normalize_string(person_data.get('last_name', ''))
        birth_date = person_data.get('birth_date')

        athlete = None
        if lookup_key:
            athlete = Athlete.query.filter_by(lookup_key=lookup_key).first()

        if not athlete and first_name and last_name:
            athlete = self._find_same_name_fallback(first_name, last_name, birth_date)

        if not athlete:
            athlete = Athlete(
                first_name=first_name,
                last_name=last_name,
                patronymic=normalize_string(person_data.get('patronymic', '')) or None,
                full_name_xml=normalize_string(person_data.get('full_name_xml', '')) or None,
                birth_date=birth_date,
                gender=normalize_string(person_data.get('gender', '')) or None,
                country=normalize_string(person_data.get('country', '')) or None,
                club_id=person_data.get('club_id'),
                lookup_key=lookup_key,
            )
            db.session.add(athlete)
            return athlete

        # Merge data without overwriting with empty values
        if self._should_update(athlete.first_name, person_data.get('first_name')):
            athlete.first_name = first_name
        if self._should_update(athlete.last_name, person_data.get('last_name')):
            athlete.last_name = last_name
        if self._should_update(athlete.patronymic, person_data.get('patronymic')):
            athlete.patronymic = normalize_string(person_data.get('patronymic', '')) or None
        if self._should_update(athlete.full_name_xml, person_data.get('full_name_xml')):
            athlete.full_name_xml = normalize_string(person_data.get('full_name_xml', '')) or None
        if not athlete.birth_date and birth_date:
            athlete.birth_date = birth_date
        if not athlete.gender and person_data.get('gender'):
            athlete.gender = normalize_string(person_data.get('gender', ''))
        if not athlete.country and person_data.get('country'):
            athlete.country = normalize_string(person_data.get('country', ''))
        if not athlete.club_id and person_data.get('club_id'):
            athlete.club_id = person_data.get('club_id')
        # Recompute key after upgrading a null-birth card, or fill missing key.
        effective_key = self._make_lookup_key({
            'first_name': athlete.first_name,
            'last_name': athlete.last_name,
            'birth_date': athlete.birth_date,
        })
        if effective_key and athlete.lookup_key != effective_key:
            # Do not steal another athlete's key; keep existing card without key clash.
            clash = Athlete.query.filter(
                Athlete.lookup_key == effective_key,
                Athlete.id != athlete.id,
            ).first()
            if not clash:
                athlete.lookup_key = effective_key

        return athlete
