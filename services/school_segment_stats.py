#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Статистика участий по типу школы (МАФКК / ЦСКА Жук / коммерческие) и рангу турнира."""

from collections import defaultdict

from sqlalchemy import case, func, literal

from models import Athlete, Club, Event, Participant

# Точные названия клубов в БД (остальные считаются коммерческими; без школы — тоже «прочие»).
CLUB_NAME_MAFKK = 'ГБУ ДО Московская академия фигурного катания на коньках'
CLUB_NAME_CSKA = 'СШОР ЦСКА им.С.А.Жука по фигурному катанию на коньках'


def _pct(numerator: int, denominator: int) -> float:
    if not denominator:
        return 0.0
    return round(100.0 * numerator / denominator, 1)


def build_event_rank_school_segment_report(session):
    """
    По каждому рангу турнира (event.event_rank): число уникальных спортсменов и число участий
    (строк participant) в разрезе МАФКК / ЦСКА / остальные + проценты внутри ранга.

    Возвращает dict:
      mafk_club_id, cska_club_id — могут быть None, если клуб не найден
      rows — список строк для таблиц (отсортировано по убыванию суммарных участий)
      totals — агрегат по всем рангам
    """
    mafk_row = session.query(Club.id).filter(Club.name == CLUB_NAME_MAFKK).one_or_none()
    cska_row = session.query(Club.id).filter(Club.name == CLUB_NAME_CSKA).one_or_none()
    mafk_id = mafk_row[0] if mafk_row else None
    cska_id = cska_row[0] if cska_row else None

    rank_label = func.coalesce(func.nullif(func.trim(Event.event_rank), ''), 'Не указан')

    whens = []
    if mafk_id is not None:
        whens.append((Athlete.club_id == mafk_id, 'mafk'))
    if cska_id is not None:
        whens.append((Athlete.club_id == cska_id, 'cska'))
    segment = case(*whens, else_='commercial') if whens else literal('commercial')

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
        .group_by(rank_label, segment)
        .all()
    )

    bucket = defaultdict(
        lambda: {'mafk': {'athletes': 0, 'participations': 0},
                 'cska': {'athletes': 0, 'participations': 0},
                 'commercial': {'athletes': 0, 'participations': 0}}
    )
    for rank, seg, parts, ath in raw:
        bucket[rank][seg]['participations'] = int(parts or 0)
        bucket[rank][seg]['athletes'] = int(ath or 0)

    rows_out = []
    totals = {'mafk': {'athletes': 0, 'participations': 0},
              'cska': {'athletes': 0, 'participations': 0},
              'commercial': {'athletes': 0, 'participations': 0}}

    for rank in bucket:
        m = bucket[rank]['mafk']
        c = bucket[rank]['cska']
        k = bucket[rank]['commercial']
        ta = m['athletes'] + c['athletes'] + k['athletes']
        tp = m['participations'] + c['participations'] + k['participations']
        rows_out.append({
            'event_rank': rank,
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
        for key in ('mafk', 'cska', 'commercial'):
            totals[key]['athletes'] += bucket[rank][key]['athletes']
            totals[key]['participations'] += bucket[rank][key]['participations']

    rows_out.sort(key=lambda r: (-r['total_participations'], r['event_rank']))

    ta_tot = totals['mafk']['athletes'] + totals['cska']['athletes'] + totals['commercial']['athletes']
    tp_tot = totals['mafk']['participations'] + totals['cska']['participations'] + totals['commercial']['participations']

    totals_row = {
        'event_rank': 'ИТОГО',
        'mafk_athletes': totals['mafk']['athletes'],
        'mafk_athletes_pct': _pct(totals['mafk']['athletes'], ta_tot),
        'cska_athletes': totals['cska']['athletes'],
        'cska_athletes_pct': _pct(totals['cska']['athletes'], ta_tot),
        'commercial_athletes': totals['commercial']['athletes'],
        'commercial_athletes_pct': _pct(totals['commercial']['athletes'], ta_tot),
        'total_athletes': ta_tot,
        'mafk_parts': totals['mafk']['participations'],
        'mafk_parts_pct': _pct(totals['mafk']['participations'], tp_tot),
        'cska_parts': totals['cska']['participations'],
        'cska_parts_pct': _pct(totals['cska']['participations'], tp_tot),
        'commercial_parts': totals['commercial']['participations'],
        'commercial_parts_pct': _pct(totals['commercial']['participations'], tp_tot),
        'total_participations': tp_tot,
        'is_total': True,
    }

    return {
        'mafk_club_id': mafk_id,
        'cska_club_id': cska_id,
        'rows': rows_out,
        'totals_row': totals_row,
        'club_name_mafkk': CLUB_NAME_MAFKK,
        'club_name_cska': CLUB_NAME_CSKA,
    }
