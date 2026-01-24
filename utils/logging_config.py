#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Logging configuration helpers."""
import logging
import os

def setup_logging(log_level, log_file):
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, str(log_level).upper(), logging.INFO),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ],
    )
