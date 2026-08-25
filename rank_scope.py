"""Единый диапазон разрядов для сравнительной статистики сайта."""

from typing import Optional

from flask import has_request_context, request, session
from sqlalchemy import func, or_

from models import Category


INCLUDE_KMS_SESSION_KEY = 'include_kms_in_reports'

CORE_RANK_PREFIXES = (
    '1 Спортивный',
    '2 Спортивный',
    '3 Спортивный',
    '1 Юношеский',
    '2 Юношеский',
    '3 Юношеский',
)

KMS_RANK_PREFIX = 'КМС'


def _parse_bool(value) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in ('1', 'true', 'yes', 'on'):
        return True
    if normalized in ('0', 'false', 'no', 'off'):
        return False
    return None


def get_include_kms(explicit_value=None) -> bool:
    """Возвращает и при явном параметре сохраняет общий режим учёта КМС."""
    if not has_request_context():
        return bool(_parse_bool(explicit_value))

    requested = explicit_value
    if requested is None:
        requested = request.args.get('include_kms')
    parsed = _parse_bool(requested)
    if parsed is not None:
        session[INCLUDE_KMS_SESSION_KEY] = parsed
        return parsed
    return bool(session.get(INCLUDE_KMS_SESSION_KEY, False))


def category_scope_clause(include_kms: Optional[bool] = None):
    """SQLAlchemy-условие: 3 юн.–1 сп., опционально плюс все категории КМС."""
    if include_kms is None:
        include_kms = get_include_kms()
    effective_name = func.coalesce(
        func.nullif(func.trim(Category.normalized_name), ''),
        Category.name,
        '',
    )
    prefixes = list(CORE_RANK_PREFIXES)
    if include_kms:
        prefixes.append(KMS_RANK_PREFIX)
    patterns = []
    for prefix in prefixes:
        patterns.append(effective_name.like(prefix + '%'))
        patterns.append(effective_name.like(prefix.lower() + '%'))
    return or_(*patterns)


def rank_label_in_scope(label, include_kms: Optional[bool] = None) -> bool:
    """Python-версия того же правила для уже загруженных строк."""
    if include_kms is None:
        include_kms = get_include_kms()
    normalized = str(label or '').strip().casefold()
    prefixes = list(CORE_RANK_PREFIXES)
    if include_kms:
        prefixes.append(KMS_RANK_PREFIX)
    return any(normalized.startswith(prefix.casefold()) for prefix in prefixes)


def get_rank_scope_label(include_kms: Optional[bool] = None) -> str:
    if include_kms is None:
        include_kms = get_include_kms()
    return '3 юн. — 1 сп. + КМС' if include_kms else '3 юн. — 1 сп.'
