#!/usr/bin/env python3
"""
WSGI файл для развертывания на Beget
"""

import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(__file__))

from app import app

if __name__ == "__main__":
    app.run()
