#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Статистика участий МАФКК / ЦСКА (Жук) / коммерческие школы в разных разрезах."""

from collections import defaultdict
from datetime import date

from sqlalchemy import case, func, literal

from models import Athlete, Category, Club, Event, Participant

CLUB_NAME_MAFKK = 'ГБУ ДО Московская академия фигурного катания на коньках'
CLUB_NAME_CSKA = 'СШОР ЦСКА им.С.А.Жука по фигурному катанию на коньках'

# Учитываем только 3–1 юношеский и 3–1 спортивный; МС и КМС не входят.
ALLOWED_CATEGORY_RANK_PREFIXES = (
    '1 Спортивный',
    '2 Спортивный',
    '3 Спортивный',
    '1 Юношеский',
    '2 Юношеский',
    '3 Юношеский',
)

MS_KMS_NORMALIZED_NAMES = frozenset({
    'МС, Женщины',
    'МС, Мужчины',
    'МС, Пары',
    'МС, Танцы',
    'КМС, Девушки',
    'КМС, Юноши',
    'КМС, Пары',
    'КМС, Танцы',
})

RANK_FILTER_NOTE = (
    'Учитываются только участия в разрядах с «3 юношеский» по «1 юношеский» '
    'и с «3 спортивный» по «1 спортивный»; разряды МС и КМС не включаются.'
)


def _effective_category_label_raw():
    """Подпись разряда для фильтрации."""
    return func.coalesce(
        func.nullif(func.trim(Category.normalized_name), ''),
        Category.name,
        '',
    )


def _category_label_display():
    return func.coalesce(
        func.nullif(func.trim(Category.normalized_name), ''),
        Category.name,
        'Не указан',
    )


def _allowed_category_rank_clause():
    from sqlalchemy import and_, or_

    eff = _effective_category_label_raw()
    prefix_ok = or_(*[eff.like(pref + '%') for pref in ALLOWED_CATEGORY_RANK_PREFIXES])
    return and_(prefix_ok, eff.notin_(MS_KMS_NORMALIZED_NAMES))


def _pct(numerator: int, denominator: int) -> float:
    if not denominator:
        return 0.0
    return round(100.0 * numerator / denominator, 1)


def _resolve_club_ids(session):
    mafk_row = session.query(Club.id).filter(Club.name == CLUB_NAME_MAFKK).one_or_none()
    cska_row = session.query(Club.id).filter(Club.name == CLUB_NAME_CSKA).one_or_none()
    mafk_id = mafk_row[0] if mafk_row else None
    cska_id = cska_row[0] if cska_row else None
    return mafk_id, cska_id


def _segment_column(mafk_id, cska_id):
    whens = []
    if mafk_id is not None:
        whens.append((Athlete.club_id == mafk_id, 'mafk'))
    if cska_id is not None:
        whens.append((Athlete.club_id == cska_id, 'cska'))
    return case(*whens, else_='commercial') if whens else literal('commercial')


def _empty_seg_bucket():
    return {
        'mafk': {'athletes': 0, 'participations': 0},
        'cska': {'athletes': 0, 'participations': 0},
        'commercial': {'athletes': 0, 'participations': 0},
    }


def _feed_bucket(bucket, dim_key, seg, parts, athletes):
    bucket[dim_key][seg]['participations'] = int(parts or 0)
    bucket[dim_key][seg]['athletes'] = int(athletes or 0)


def _metrics_for_dim(bucket, dim_key):
    m = bucket[dim_key]['mafk']
    c = bucket[dim_key]['cska']
    k = bucket[dim_key]['commercial']
    ta = m['athletes'] + c['athletes'] + k['athletes']
    tp = m['participations'] + c['participations'] + k['participations']
    return m, c, k, ta, tp


def _row_from_metrics(m, c, k, ta, tp, extra):
    row = dict(extra)
    row.update({
        'mafk_athletes': m['athletes'],
        'mafk_athletes_pct': _pct(m['athletes'], ta),
        'cska_athletes': c['athletes'],
        'cska_athletes_pct': _pct(c['athletes'], ta),
        'commercial_athletes': k['athletes'],
        'commercial_athletes_pct': _pct(k['athletes'], ta),
        'total_athletes': ta,
        'mafk_parts': m['participations'],
        'mafk_parts_pct': _pct(m['participations'], tp),
        'cska_parts': c['participations'],
        'cska_parts_pct': _pct(c['participations'], tp),
        'commercial_parts': k['participations'],
        'commercial_parts_pct': _pct(k['participations'], tp),
        'total_participations': tp,
    })
    return row


def _totals_from_bucket(bucket):
    totals = {'mafk': {'athletes': 0, 'participations': 0},
              'cska': {'athletes': 0, 'participations': 0},
              'commercial': {'athletes': 0, 'participations': 0}}
    for dim_key in bucket:
        for seg in ('mafk', 'cska', 'commercial'):
            totals[seg]['athletes'] += bucket[dim_key][seg]['athletes']
            totals[seg]['participations'] += bucket[dim_key][seg]['participations']
    return totals


def _totals_row_generic(totals, extra=None):
    extra = extra or {}
    m, c, k = totals['mafk'], totals['cska'], totals['commercial']
    ta = m['athletes'] + c['athletes'] + k['athletes']
    tp = m['participations'] + c['participations'] + k['participations']
    row = _row_from_metrics(m, c, k, ta, tp, extra)
    return row


def _report_meta(session, mafk_id, cska_id):
    return {
        'mafk_club_id': mafk_id,
        'cska_club_id': cska_id,
        'club_name_mafkk': CLUB_NAME_MAFKK,
        'club_name_cska': CLUB_NAME_CSKA,
        'generated_date': date.today().isoformat(),
        'rank_filter_note': RANK_FILTER_NOTE,
    }


def build_event_rank_school_segment_report(session):
    """По рангу турнира (event.event_rank): спортивное / физкультурное и т.д."""
    mafk_id, cska_id = _resolve_club_ids(session)
    segment = _segment_column(mafk_id, cska_id)
    rank_label = func.coalesce(func.nullif(func.trim(Event.event_rank), ''), 'Не указан')

    raw = (
        session.query(
            rank_label.label('event_rank'),
            segment.label('seg'),
            func.count(Participant.id).label('participations'),
            func.count(func.distinct(Athlete.id)).label('athletes'),
        )
        .select_from(Participant)
        .join(Athlete, Participant.athlete_id == Athlete.id)
        .join(Event, Participant.event_id == Event.id)
        .join(Category, Participant.category_id == Category.id)
        .filter(_allowed_category_rank_clause())
        .group_by(rank_label, segment)
        .all()
    )

    bucket = defaultdict(_empty_seg_bucket)
    for rank, seg, parts, ath in raw:
        _feed_bucket(bucket, rank, seg, parts, ath)

    rows_out = []
    for rank in bucket:
        m, c, k, ta, tp = _metrics_for_dim(bucket, rank)
        rows_out.append(_row_from_metrics(m, c, k, ta, tp, {'event_rank': rank}))

    rows_out.sort(key=lambda r: (-r['total_participations'], str(r['event_rank'])))
    totals = _totals_from_bucket(bucket)
    totals_row = _totals_row_generic(totals, {'event_rank': 'ИТОГО'})

    out = _report_meta(session, mafk_id, cska_id)
    out.update({'rows': rows_out, 'totals_row': totals_row})
    return out


def build_per_event_school_segment_report(session):
    """По каждому турниру (событию)."""
    mafk_id, cska_id = _resolve_club_ids(session)
    segment = _segment_column(mafk_id, cska_id)

    raw = (
        session.query(
            Event.id.label('event_id'),
            segment.label('seg'),
            func.count(Participant.id).label('participations'),
            func.count(func.distinct(Athlete.id)).label('athletes'),
        )
        .select_from(Participant)
        .join(Athlete, Participant.athlete_id == Athlete.id)
        .join(Event, Participant.event_id == Event.id)
        .join(Category, Participant.category_id == Category.id)
        .filter(_allowed_category_rank_clause())
        .group_by(Event.id, segment)
        .all()
    )

    bucket = defaultdict(_empty_seg_bucket)
    eids = set()
    for eid, seg, part, ath in raw:
        _feed_bucket(bucket, eid, seg, part, ath)
        eids.add(eid)

    meta_ev = {}
    if eids:
        for e in session.query(Event).filter(Event.id.in_(eids)).all():
            meta_ev[e.id] = e

    rows_out = []
    for eid in bucket:
        ev = meta_ev.get(eid)
        name = ev.name if ev else '—'
        bd = ev.begin_date if ev else None
        date_s = bd.strftime('%d.%m.%Y') if bd else '—'
        er = (ev.event_rank or '').strip() if ev and ev.event_rank else ''
        if not er:
            er = 'Не указан'
        m, c, k, ta, tp = _metrics_for_dim(bucket, eid)
        rows_out.append(_row_from_metrics(m, c, k, ta, tp, {
            'event_id': eid,
            'event_name': name,
            'event_date': bd,
            'event_date_display': date_s,
            'tournament_rank': er,
        }))

    rows_out.sort(key=lambda r: (
        r['event_date'] is None,
        -(r['event_date'].toordinal() if r['event_date'] else 0),
        r['event_name'] or '',
    ))

    totals = _totals_from_bucket(bucket)
    totals_row = _totals_row_generic(totals, {
        'event_name': 'ИТОГО',
        'event_date_display': '',
        'tournament_rank': '',
    })

    out = _report_meta(session, mafk_id, cska_id)
    out.update({'rows': rows_out, 'totals_row': totals_row})
    return out


def build_per_category_school_segment_report(session):
    """По спортивному разряду (категории) в целом по базе."""
    mafk_id, cska_id = _resolve_club_ids(session)
    segment = _segment_column(mafk_id, cska_id)
    cat_label = _category_label_display()

    raw = (
        session.query(
            cat_label.label('category_label'),
            segment.label('seg'),
            func.count(Participant.id).label('participations'),
            func.count(func.distinct(Athlete.id)).label('athletes'),
        )
        .select_from(Participant)
        .join(Athlete, Participant.athlete_id == Athlete.id)
        .join(Category, Participant.category_id == Category.id)
        .filter(_allowed_category_rank_clause())
        .group_by(cat_label, segment)
        .all()
    )

    bucket = defaultdict(_empty_seg_bucket)
    for clbl, seg, parts, ath in raw:
        _feed_bucket(bucket, clbl, seg, parts, ath)

    rows_out = []
    for clbl in bucket:
        m, c, k, ta, tp = _metrics_for_dim(bucket, clbl)
        rows_out.append(_row_from_metrics(m, c, k, ta, tp, {'category_label': clbl}))

    rows_out.sort(key=lambda r: (-r['total_participations'], str(r['category_label'])))

    totals = _totals_from_bucket(bucket)
    totals_row = _totals_row_generic(totals, {'category_label': 'ИТОГО'})

    out = _report_meta(session, mafk_id, cska_id)
    out.update({'rows': rows_out, 'totals_row': totals_row})
    return out


def build_per_event_category_school_segment_report(session):
    """По каждому турниру и разряду внутри него."""
    mafk_id, cska_id = _resolve_club_ids(session)
    segment = _segment_column(mafk_id, cska_id)
    cat_label = _category_label_display()

    raw = (
        session.query(
            Event.id.label('event_id'),
            cat_label.label('category_label'),
            segment.label('seg'),
            func.count(Participant.id).label('participations'),
            func.count(func.distinct(Athlete.id)).label('athletes'),
        )
        .select_from(Participant)
        .join(Athlete, Participant.athlete_id == Athlete.id)
        .join(Event, Participant.event_id == Event.id)
        .join(Category, Participant.category_id == Category.id)
        .filter(_allowed_category_rank_clause())
        .group_by(Event.id, cat_label, segment)
        .all()
    )

    bucket = defaultdict(_empty_seg_bucket)
    keys = set()
    for eid, clbl, seg, parts, ath in raw:
        key = (eid, clbl)
        _feed_bucket(bucket, key, seg, parts, ath)
        keys.add(key)

    eids = {k[0] for k in keys}
    meta_ev = {}
    if eids:
        for e in session.query(Event).filter(Event.id.in_(eids)).all():
            meta_ev[e.id] = e

    rows_out = []
    for eid, clbl in sorted(keys, key=lambda x: (x[0], str(x[1]))):
        ev = meta_ev.get(eid)
        name = ev.name if ev else '—'
        bd = ev.begin_date if ev else None
        date_s = bd.strftime('%d.%m.%Y') if bd else '—'
        er = (ev.event_rank or '').strip() if ev and ev.event_rank else ''
        if not er:
            er = 'Не указан'
        m, c, k, ta, tp = _metrics_for_dim(bucket, (eid, clbl))
        rows_out.append(_row_from_metrics(m, c, k, ta, tp, {
            'event_id': eid,
            'event_name': name,
            'event_date': bd,
            'event_date_display': date_s,
            'tournament_rank': er,
            'category_label': clbl,
        }))

    rows_out.sort(key=lambda r: (
        r['event_date'] is None,
        -(r['event_date'].toordinal() if r['event_date'] else 0),
        r['event_name'] or '',
        r['category_label'] or '',
    ))

    totals = _totals_from_bucket(bucket)
    totals_row = _totals_row_generic(totals, {
        'event_name': 'ИТОГО',
        'event_date_display': '',
        'tournament_rank': '',
        'category_label': '',
    })

    out = _report_meta(session, mafk_id, cska_id)
    out.update({'rows': rows_out, 'totals_row': totals_row})
    return out
