#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Архивация XML после успешного импорта в каталог uploads/xml_archive/."""

import os
import shutil
from datetime import datetime

from werkzeug.utils import secure_filename

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def archive_imported_xml(filepath: str, original_filename: str, upload_folder: str = 'uploads') -> str | None:
    """
    Копирует файл в uploads/xml_archive/ с меткой времени в имени.
    Отключить: SAVE_XML_IMPORT_ARCHIVE=0 в окружении.
    Возвращает путь к копии или None при пропуске / ошибке.
    """
    flag = (os.environ.get('SAVE_XML_IMPORT_ARCHIVE') or '1').strip().lower()
    if flag in ('0', 'false', 'no', 'off'):
        return None
    if not filepath or not os.path.isfile(filepath):
        return None
    rel_up = (upload_folder or 'uploads').strip('/\\')
    archive_root = os.path.normpath(os.path.join(_PROJECT_ROOT, rel_up, 'xml_archive'))
    try:
        os.makedirs(archive_root, mode=0o755, exist_ok=True)
    except OSError:
        return None
    safe = secure_filename(original_filename or '') or 'upload.xml'
    if safe.lower().endswith('.zip'):
        pass
    elif not safe.lower().endswith('.xml'):
        safe = f'{safe}.xml'
    ts = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    dest_name = f'{ts}_{safe}'
    dest_path = os.path.join(archive_root, dest_name)
    try:
        shutil.copy2(filepath, dest_path)
        return dest_path
    except OSError:
        return None
