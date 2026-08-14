#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Helpers for protocol/API score display.

Import stores Performance.points and Participant.total_points via _parse_score
(already divided by 100). TES/PCS/element fields stay in XML hundredths.
Judge GOE marks are stored as XML codes 0–15, where 0 means -5.
"""


def judge_mark_raw(judge_scores, judge_num):
    """Return the stored mark for judge N, preserving 0 (GOE code for -5).

    Looking up J01 with ``dict.get('J01') or dict.get('J1')`` drops a legitimate
    0 because 0 is falsy in Python.
    """
    if not isinstance(judge_scores, dict) or judge_num is None:
        return None
    try:
        n = int(judge_num)
    except (TypeError, ValueError):
        return None
    for key in (f'J{n:02d}', f'J{n}'):
        if key not in judge_scores:
            continue
        value = judge_scores[key]
        if value is not None:
            return value
    return None


def points_for_protocol_display(value):
    """Display points that are already /100 at import, with a legacy ×100 fallback.

    ``_parse_score`` stores 10100 as 101.0. Treating every integer > 100 as
    hundredths would show 101.00 as 1.01. Only values whose magnitude is above
    1000 (e.g. 10621) can safely be treated as leftover hundredths: a real
    skating score cannot be that high, and hundredths of a 10+ point program
    are always >= 1000.
    """
    if value is None:
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return value
    if abs(num) > 1000:
        return num / 100.0
    return num
