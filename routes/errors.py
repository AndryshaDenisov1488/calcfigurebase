#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Error handlers."""
import logging
from flask import render_template, request, redirect, url_for, flash
from extensions import db

logger = logging.getLogger(__name__)

def register_error_handlers(app):
    @app.errorhandler(404)
    def not_found_error(error):
        logger.warning(f"404 error: {request.url} from {request.remote_addr}")
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"500 error: {error} from {request.remote_addr}")
        db.session.rollback()
        return render_template('500.html'), 500

    @app.errorhandler(413)
    def too_large(error):
        logger.warning(f"File too large from {request.remote_addr}")
        flash('Файл слишком большой. Максимальный размер: 16MB', 'error')
        return redirect(url_for('admin.upload_file'))
