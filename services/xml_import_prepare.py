#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Подготовка распарсенного XML к импорту (как в normalize_categories)."""

import logging
import os

from parsers.isu_calcfs_parser import ISUCalcFSParser

logger = logging.getLogger(__name__)


def iter_ready_parsers(parser_data, categories_analysis, deleted_indices):
    """
    Итерирует (parser, filepath, original_filename) как перед save_to_database.
    filepath — для удаления после успешного импорта; original_filename — исходное имя для архива.
    deleted_indices — множество индексов категорий (глобальных по categories_analysis).
    """
    if 'files' in parser_data:
        category_index = 0
        for file_info in parser_data['files']:
            filepath = file_info.get('filepath')
            if not filepath or not os.path.exists(filepath):
                # categories_analysis — общий плоский список по всем файлам.
                # Если пропустить файл без сдвига индекса, следующие файлы
                # получат чужие normalized_name (типичный кейс: повтор после
                # частичного импорта, когда первый XML уже удалён с диска).
                skip_n = file_info.get('categories_count')
                logger.warning(
                    'Пропуск файла без пути или файл отсутствует: %s (сдвиг индекса категорий на %s)',
                    file_info.get('filename'),
                    skip_n,
                )
                if skip_n is None:
                    raise FileNotFoundError(
                        'Файл импорта отсутствует, а categories_count не задан — '
                        f'нельзя безопасно выровнять индекс категорий: {file_info.get("filename")}'
                    )
                try:
                    category_index += int(skip_n)
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f'Некорректный categories_count для файла {file_info.get("filename")}: {skip_n!r}'
                    ) from exc
                continue
            parser = ISUCalcFSParser(filepath)
            parser.parse()

            categories_to_save = []
            deleted_category_ids = set()
            start_index = category_index

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

            expected = file_info.get('categories_count')
            if expected is not None:
                try:
                    expected_n = int(expected)
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f'Некорректный categories_count для файла {file_info.get("filename")}: {expected!r}'
                    ) from exc
                consumed = category_index - start_index
                if consumed != expected_n:
                    raise ValueError(
                        f'Файл {file_info.get("filename")}: в XML {consumed} категорий, '
                        f'в анализе {expected_n}. Импорт остановлен, чтобы не сдвинуть '
                        f'нормализацию следующих файлов.'
                    )

            parser.categories = categories_to_save
            if deleted_category_ids:
                parser.segments = [s for s in parser.segments if s.get('category_id') not in deleted_category_ids]
                parser.participants = [
                    p for p in parser.participants if p.get('category_id') not in deleted_category_ids
                ]

            if parser.categories:
                original_name = file_info.get('filename') or os.path.basename(filepath)
                yield parser, filepath, original_name
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
            original_name = parser_data.get('upload_original_filename') or os.path.basename(filepath)
            yield parser, filepath, original_name
