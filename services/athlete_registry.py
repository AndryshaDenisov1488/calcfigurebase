"""Athlete registry with deduplication by name+birth date."""

from models import db, Athlete
from utils.normalizers import normalize_string, normalize_identity_name


class AthleteRegistry:
    """Registry for athletes with safe merge logic."""

    def _make_lookup_key(self, person_data):
        first_name = normalize_identity_name(person_data.get('first_name', ''))
        last_name = normalize_identity_name(person_data.get('last_name', ''))
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

    def _find_by_folded_name_birth(self, first_name, last_name, birth_date):
        """
        Match an existing card when lookup_key missed (legacy keys still contain ё,
        or names differ only by ё/е). Narrow by birth_date (indexed), compare in Python.
        """
        if not first_name or not last_name or not birth_date:
            return None
        first_key = normalize_identity_name(first_name)
        last_key = normalize_identity_name(last_name)
        for athlete in Athlete.query.filter_by(birth_date=birth_date).order_by(Athlete.id.asc()).all():
            if (
                normalize_identity_name(athlete.first_name) == first_key
                and normalize_identity_name(athlete.last_name) == last_key
            ):
                return athlete
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

        # Legacy lookup_key values may still embed ё; fold-compare by name+birth.
        if not athlete and birth_date and first_name and last_name:
            athlete = self._find_by_folded_name_birth(first_name, last_name, birth_date)

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

        effective_key = self._make_lookup_key({
            'first_name': athlete.first_name,
            'last_name': athlete.last_name,
            'birth_date': athlete.birth_date,
        })
        if effective_key and athlete.lookup_key != effective_key:
            clash = Athlete.query.filter(
                Athlete.lookup_key == effective_key,
                Athlete.id != athlete.id,
            ).first()
            if not clash:
                athlete.lookup_key = effective_key

        return athlete
