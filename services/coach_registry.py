"""Coach registry with deduplication and transition tracking."""

import logging
from models import db, Coach
from utils.normalizers import normalize_string, fix_latin_to_cyrillic

logger = logging.getLogger(__name__)


class CoachRegistry:
    """Registry for coaches with deduplication."""

    def __init__(self):
        self._cache_by_name = {}

    def get_or_create(self, coach_name):
        """Finds or creates a coach by name."""
        if not coach_name or not coach_name.strip():
            return None

        # Нормализуем имя тренера
        normalized_name = normalize_string(fix_latin_to_cyrillic(coach_name))
        
        if not normalized_name:
            return None

        # Проверяем кеш
        if normalized_name in self._cache_by_name:
            return self._cache_by_name[normalized_name]

        # Ищем существующего тренера по нормализованному имени
        coach = Coach.query.filter_by(normalized_name=normalized_name).first()
        
        if not coach:
            # Создаем нового тренера
            coach = Coach(
                name=coach_name.strip(),
                normalized_name=normalized_name
            )
            db.session.add(coach)
            db.session.flush()
            logger.info(f"Создан новый тренер: {coach_name}")

        self._cache_by_name[normalized_name] = coach
        return coach
