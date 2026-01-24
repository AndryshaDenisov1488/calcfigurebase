#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Application entrypoint."""
from app_factory import create_app
from extensions import db

app = create_app()

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=7000, debug=False)
