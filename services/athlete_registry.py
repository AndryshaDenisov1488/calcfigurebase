"""Athlete registry with deduplication by name+birth date."""

from models import db, Athlete
from utils.normalizers import normalize_string


class AthleteRegistry:
    """Registry for athletes with safe merge logic."""

    PAIR_DETAIL_FIELDS = (
        'primary_external_id',
        'primary_first_name',
        'primary_last_name',
        'primary_patronymic',
        'primary_birth_date',
        'primary_gender',
        'partner_external_id',
        'partner_first_name',
        'partner_last_name',
        'partner_patronymic',
        'partner_birth_date',
        'partner_gender',
    )

    def _make_lookup_key(self, person_data):
        first_name = normalize_string(person_data.get('first_name', '')).lower().replace('ё', 'е')
        last_name = normalize_string(person_data.get('last_name', '')).lower().replace('ё', 'е')
        birth_date = person_data.get('birth_date')
        if first_name and last_name and birth_date:
            return f"name:{first_name}:{last_name}:{birth_date}"
        return None

    def _fold_lookup_key(self, lookup_key):
        if not lookup_key:
            return None
        return str(lookup_key).replace('ё', 'е').replace('Ё', 'е')

    def _find_existing_athlete(self, lookup_key, person_data):
        """Match by folded key, including rows still stored with ё from before folding."""
        if lookup_key:
            athlete = Athlete.query.filter_by(lookup_key=lookup_key).first()
            if athlete:
                return athlete

        birth_date = person_data.get('birth_date')
        if not lookup_key or not birth_date:
            return None

        # Exact filter_by misses legacy keys such as name:алёна:... after ё→е folding.
        candidates = (
            Athlete.query.filter(Athlete.birth_date == birth_date)
            .order_by(Athlete.id.asc())
            .all()
        )
        for candidate in candidates:
            stored = self._fold_lookup_key(candidate.lookup_key)
            if stored == lookup_key:
                return candidate
            recomputed = self._make_lookup_key(
                {
                    'first_name': candidate.first_name,
                    'last_name': candidate.last_name,
                    'birth_date': candidate.birth_date,
                }
            )
            if recomputed == lookup_key:
                return candidate
        return None

    def _should_update(self, old_value, new_value):
        if not new_value:
            return False
        if not old_value:
            return True
        return len(str(new_value)) > len(str(old_value))

    def get_or_create(self, person_data):
        """Finds or creates an athlete with merge protection."""
        if not person_data:
            return None

        lookup_key = self._make_lookup_key(person_data)
        athlete = self._find_existing_athlete(lookup_key, person_data)

        if not athlete:
            athlete = Athlete(
                first_name=normalize_string(person_data.get('first_name', '')),
                last_name=normalize_string(person_data.get('last_name', '')),
                patronymic=normalize_string(person_data.get('patronymic', '')) or None,
                full_name_xml=normalize_string(person_data.get('full_name_xml', '')) or None,
                birth_date=person_data.get('birth_date'),
                gender=normalize_string(person_data.get('gender', '')) or None,
                country=normalize_string(person_data.get('country', '')) or None,
                club_id=person_data.get('club_id'),
                lookup_key=lookup_key,
            )
            self._merge_pair_details(athlete, person_data)
            db.session.add(athlete)
            return athlete

        # Merge data without overwriting with empty values
        if self._should_update(athlete.first_name, person_data.get('first_name')):
            athlete.first_name = normalize_string(person_data.get('first_name', ''))
        if self._should_update(athlete.last_name, person_data.get('last_name')):
            athlete.last_name = normalize_string(person_data.get('last_name', ''))
        if self._should_update(athlete.patronymic, person_data.get('patronymic')):
            athlete.patronymic = normalize_string(person_data.get('patronymic', '')) or None
        if self._should_update(athlete.full_name_xml, person_data.get('full_name_xml')):
            athlete.full_name_xml = normalize_string(person_data.get('full_name_xml', '')) or None
        if not athlete.birth_date and person_data.get('birth_date'):
            athlete.birth_date = person_data.get('birth_date')
        if not athlete.gender and person_data.get('gender'):
            athlete.gender = normalize_string(person_data.get('gender', ''))
        if not athlete.country and person_data.get('country'):
            athlete.country = normalize_string(person_data.get('country', ''))
        if not athlete.club_id and person_data.get('club_id'):
            athlete.club_id = person_data.get('club_id')
        if lookup_key and athlete.lookup_key != lookup_key:
            athlete.lookup_key = lookup_key

        self._merge_pair_details(athlete, person_data)

        return athlete

    def _merge_pair_details(self, athlete, person_data):
        """Fill pair member fields and refresh changed non-empty XML values."""
        for field in self.PAIR_DETAIL_FIELDS:
            value = person_data.get(field)
            if value in (None, ''):
                continue
            if field.endswith(('_first_name', '_last_name', '_patronymic', '_external_id')):
                value = normalize_string(value) or None
            setattr(athlete, field, value)
