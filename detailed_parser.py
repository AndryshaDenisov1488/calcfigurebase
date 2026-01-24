#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compatibility wrapper for ISUCalcFS parser.
"""
from parsers.isu_calcfs_parser import ISUCalcFSParser, parse_date, parse_date_to_string

__all__ = ['ISUCalcFSParser', 'parse_date', 'parse_date_to_string']