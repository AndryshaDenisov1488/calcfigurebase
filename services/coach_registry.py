"""Coach registry with deduplication and transition tracking."""

import logging
from models import db, Coach, CoachAssignment
from utils.normalizers import normalize_string, fix_latin_to_cyrillic

logger = logging.getLogger(__name__)


def record_assignment_on_import(athlete_id, coach_id, participant_id, event_id, event_date):
    """
    Пишет CoachAssignment при импорте XML.

    Важно: турниры часто импортируют не по хронологии. Если событие старше
    текущего назначения, нельзя закрывать текущего тренера и ставить
    исторического как is_current — иначе ломается «текущий тренер» и даты.
    """
    if not event_date:
        return None

    existing = CoachAssignment.query.filter_by(
        athlete_id=athlete_id,
        coach_id=coach_id,
        event_id=event_id,
    ).first()
    if existing:
        return existing

    current = CoachAssignment.query.filter_by(
        athlete_id=athlete_id,
        is_current=True,
    ).first()

    if not current:
        assignment = CoachAssignment(
            coach_id=coach_id,
            athlete_id=athlete_id,
            participant_id=participant_id,
            event_id=event_id,
            start_date=event_date,
            is_current=True,
        )
        db.session.add(assignment)
        return assignment

    if current.coach_id == coach_id:
        return current

    # Исторический импорт: событие раньше старта текущего тренера
    if current.start_date and event_date < current.start_date:
        assignment = CoachAssignment(
            coach_id=coach_id,
            athlete_id=athlete_id,
            participant_id=participant_id,
            event_id=event_id,
            start_date=event_date,
            end_date=current.start_date,
            is_current=False,
        )
        db.session.add(assignment)
        logger.info(
            "Историческое назначение тренера для спортсмена %s: coach %s "
            "на %s (текущий coach %s с %s сохранён)",
            athlete_id,
            coach_id,
            event_date,
            current.coach_id,
            current.start_date,
        )
        return assignment

    # Переход вперёд по времени
    previous_coach_id = current.coach_id
    current.end_date = event_date
    current.is_current = False
    assignment = CoachAssignment(
        coach_id=coach_id,
        athlete_id=athlete_id,
        participant_id=participant_id,
        event_id=event_id,
        start_date=event_date,
        is_current=True,
    )
    db.session.add(assignment)
    logger.info(
        "Переход спортсмена %s от тренера %s к тренеру %s на дату %s",
        athlete_id,
        previous_coach_id,
        coach_id,
        event_date,
    )
    return assignment


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
