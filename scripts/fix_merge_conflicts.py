#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для автоматического исправления конфликтов слияния Git в шаблонах
Использует версию после ======= (новая версия)
"""

import os
import re
import sys

def fix_merge_conflicts(file_path):
    """Исправляет конфликты слияния в файле, используя версию после ======="""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Проверяем есть ли конфликты
        if '<<<<<<< HEAD' not in content:
            return False
        
        # Разделяем по маркерам конфликта
        parts = re.split(r'<<<<<<< HEAD.*?=======', content, flags=re.DOTALL)
        
        if len(parts) < 2:
            return False
        
        # Берем часть после ======= и до >>>>>>>
        remaining = parts[-1]
        final_parts = re.split(r'>>>>>>>.*?\n', remaining, flags=re.DOTALL)
        
        if len(final_parts) < 2:
            return False
        
        # Собираем файл: часть до конфликта + новая версия + часть после конфликта
        new_content = parts[0] + final_parts[0] + ''.join(final_parts[1:])
        
        # Сохраняем
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        return True
    except Exception as e:
        print(f"Ошибка при обработке {file_path}: {e}")
        return False

def main():
    templates_dir = 'templates'
    if not os.path.exists(templates_dir):
        print(f"Директория {templates_dir} не найдена!")
        return
    
    fixed_count = 0
    for filename in os.listdir(templates_dir):
        if filename.endswith('.html'):
            file_path = os.path.join(templates_dir, filename)
            if fix_merge_conflicts(file_path):
                print(f"✅ Исправлен: {filename}")
                fixed_count += 1
            else:
                # Проверяем есть ли конфликты
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if '<<<<<<< HEAD' in content:
                        print(f"⚠️  Есть конфликт, но не удалось исправить автоматически: {filename}")
    
    print(f"\n✅ Исправлено файлов: {fixed_count}")
    return fixed_count

if __name__ == '__main__':
    fixed = main()
    sys.exit(0 if fixed > 0 else 1)

