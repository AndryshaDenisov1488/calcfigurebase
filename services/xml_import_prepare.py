#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Подготовка распарсенного XML к импорту (как в normalize_categories)."""

import logging
import os

from parsers.isu_calcfs_parser import ISUCalcFSParser

logger = logging.getLogger(__name__)


def iter_ready_parsers(parser_data, categories_analysis, deleted_indices):
    """
    Итерирует пары (parser, filepath) в том же виде, что при save_to_database.
    filepath — для удаления после успешного импорта.
    deleted_indices — множество индексов категорий (глобальных по categories_analysis).
    """
    if 'files' in parser_data:
        category_index = 0
        for file_info in parser_data['files']:
            filepath = file_info.get('filepath')
            if not filepath or not os.path.exists(filepath):
                logger.warning('Пропуск файла без пути или файл отсутствует: %s', file_info.get('filename'))
                continue
            parser = ISUCalcFSParser(filepath)
            parser.parse()

            categories_to_save = []
            deleted_category_ids = set()

            for _i, category in enumerate(parser.categories):
                if category_index < len(categories_analysis):
                    if category_index not in deleted_indices:
                        category['normalized_name'] = categories_analysis[category_index]['normalized']
                        categories_to_save.append(category)
                    else:
                        deleted_category_ids.add(category.get('id'))
                    category_index += 1
                else:
                    categories_to_save.append(category)

            parser.categories = categories_to_save
            if deleted_category_ids:
                parser.segments = [s for s in parser.segments if s.get('category_id') not in deleted_category_ids]
                parser.participants = [
                    p for p in parser.participants if p.get('category_id') not in deleted_category_ids
                ]

            if parser.categories:
                yield parser, filepath
    else:
        filepath = parser_data.get('filepath')
        if not filepath or not os.path.exists(filepath):
            logger.error('Файл импорта не найден: %s', filepath)
            return
        parser = ISUCalcFSParser(filepath)
        parser.parse()

        categories_to_save = []
        deleted_category_ids = set()

        for i, category in enumerate(parser.categories):
            if i < len(categories_analysis):
                if i not in deleted_indices:
                    category['normalized_name'] = categories_analysis[i]['normalized']
                    categories_to_save.append(category)
                else:
                    deleted_category_ids.add(category.get('id'))
            else:
                categories_to_save.append(category)

        parser.categories = categories_to_save
        if deleted_category_ids:
            parser.segments = [s for s in parser.segments if s.get('category_id') not in deleted_category_ids]
            parser.participants = [
                p for p in parser.participants if p.get('category_id') not in deleted_category_ids
            ]

        if parser.categories:
            yield parser, filepath
