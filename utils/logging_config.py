#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Настройка логирования с ротацией
"""

import os
import logging
from logging.handlers import RotatingFileHandler

def setup_logging(log_level='INFO', log_file='logs/app.log', max_bytes=10*1024*1024, backup_count=5):
    """
    Настраивает логирование с ротацией файлов
    
    Args:
        log_level: Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Путь к файлу лога
        max_bytes: Максимальный размер файла перед ротацией (по умолчанию 10MB)
        backup_count: Количество резервных файлов (по умолчанию 5)
    """
    # Создаем папку для логов
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    # Настраиваем формат
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Файловый handler с ротацией
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(getattr(logging, log_level.upper()))
    file_handler.setFormatter(formatter)
    
    # Консольный handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level.upper()))
    console_handler.setFormatter(formatter)
    
    # Настраиваем root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    return logging.getLogger(__name__)

