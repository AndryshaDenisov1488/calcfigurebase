#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Date/time parsing helpers."""
from datetime import datetime

def parse_date(date_str):
    """Parse date from YYYYMMDD or pass-through date."""
    if not date_str:
        return None
    if hasattr(date_str, 'year') and hasattr(date_str, 'month') and hasattr(date_str, 'day'):
        return date_str
    if isinstance(date_str, str):
        if len(date_str) != 8:
            return None
        try:
            return datetime.strptime(date_str, '%Y%m%d').date()
        except ValueError:
            return None
    return None

def parse_time(time_str):
    """Parse time from HH:MM:SS."""
    if not time_str:
        return None
    try:
        return datetime.strptime(time_str, '%H:%M:%S').time()
    except ValueError:
        return None

def parse_datetime(datetime_str):
    """Parse datetime in YYYYMMDDHHMMSS or ISO fallback."""
    if not datetime_str:
        return None
    if isinstance(datetime_str, str):
        for fmt in ('%Y%m%d%H%M%S', '%Y-%m-%d %H:%M:%S'):
            try:
                return datetime.strptime(datetime_str, fmt)
            except ValueError:
                continue
    return None
