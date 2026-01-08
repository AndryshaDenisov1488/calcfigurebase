#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для автоматического разрешения конфликтов Git в HTML шаблонах
и добавления CSRF токенов во все POST формы
"""

import os
import re
from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

def resolve_conflicts(content):
    """Разрешает конфликты Git, оставляя версию HEAD"""
    lines = content.split('\n')
    result = []
    i = 0
    
    while i < len(lines):
        if lines[i].startswith('<<<<<<< HEAD'):
            # Пропускаем маркер начала конфликта
            i += 1
            # Продолжаем до разделителя
            while i < len(lines) and not lines[i].startswith('======='):
                result.append(lines[i])
                i += 1
            # Пропускаем разделитель
            if i < len(lines) and lines[i].startswith('======='):
                i += 1
            # Пропускаем версию после ======= до маркера конца
            while i < len(lines) and not lines[i].startswith('>>>>>>>'):
                i += 1
            # Пропускаем маркер конца конфликта
            if i < len(lines) and lines[i].startswith('>>>>>>>'):
                i += 1
        else:
            result.append(lines[i])
            i += 1
    
    return '\n'.join(result)

def add_csrf_token(content):
    """Добавляет CSRF токены во все POST формы"""
    # Паттерн для поиска POST форм без CSRF токена
    # Ищем <form method="POST" или <form method='POST'
    pattern = r'(<form\s+method=["\']POST["\'][^>]*>)'
    
    def replace_form(match):
        form_tag = match.group(1)
        # Проверяем, нет ли уже csrf_token в форме
        if 'csrf_token' not in form_tag.lower():
            # Вставляем CSRF токен сразу после открывающего тега формы
            return form_tag + '\n                <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>'
        return form_tag
    
    # Заменяем все POST формы
    content = re.sub(pattern, replace_form, content, flags=re.IGNORECASE)
    
    return content

def fix_url_for(content):
    """Исправляет url_for без префиксов Blueprint"""
    # Исправляем url_for('upload_file') на url_for('upload.upload_file')
    content = re.sub(r"url_for\(['\"]upload_file['\"]\)", "url_for('upload.upload_file')", content)
    
    # Исправляем другие распространенные паттерны
    patterns = [
        (r"url_for\(['\"]index['\"]\)", "url_for('main.index')"),
        (r"url_for\(['\"]events['\"]\)", "url_for('main.events')"),
        (r"url_for\(['\"]athletes['\"]\)", "url_for('main.athletes')"),
        (r"url_for\(['\"]clubs['\"]\)", "url_for('main.clubs')"),
        (r"url_for\(['\"]categories['\"]\)", "url_for('main.categories')"),
        (r"url_for\(['\"]free_participation['\"]\)", "url_for('main.free_participation')"),
        (r"url_for\(['\"]analytics['\"]\)", "url_for('main.analytics')"),
    ]
    
    for pattern, replacement in patterns:
        content = re.sub(pattern, replacement, content)
    
    return content

def process_template(filepath):
    """Обрабатывает один шаблон"""
    print(f"Обработка {filepath.name}...")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # Разрешаем конфликты
    if '<<<<<<< HEAD' in content:
        content = resolve_conflicts(content)
        print(f"  ✓ Разрешены конфликты")
    
    # Добавляем CSRF токены
    if '<form method="POST"' in content or "<form method='POST'" in content:
        content = add_csrf_token(content)
        print(f"  ✓ Добавлены CSRF токены")
    
    # Исправляем url_for
    content = fix_url_for(content)
    
    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  ✓ Файл обновлен")
    else:
        print(f"  - Изменений не требуется")

def main():
    """Основная функция"""
    print("=" * 60)
    print("Исправление конфликтов и CSRF токенов в шаблонах")
    print("=" * 60)
    print()
    
    # Обрабатываем все HTML файлы в директории templates
    template_files = list(TEMPLATES_DIR.glob("*.html"))
    
    if not template_files:
        print("HTML файлы не найдены!")
        return
    
    for template_file in sorted(template_files):
        process_template(template_file)
        print()
    
    print("=" * 60)
    print("Готово!")
    print("=" * 60)

if __name__ == "__main__":
    main()

