#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Скрипт для обновления проекта из git репозитория
"""
import subprocess
import sys
import os

def run_git_command(command):
    """Выполняет git команду и выводит результат"""
    try:
        print(f"Выполняю: git {command}")
        result = subprocess.run(
            ['git'] + command.split(),
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        
        return result.returncode == 0
    except Exception as e:
        print(f"Ошибка при выполнении команды: {e}")
        return False

def main():
    print("=" * 50)
    print("Обновление проекта из git репозитория")
    print("=" * 50)
    print()
    
    # Проверяем, что мы в git репозитории
    if not os.path.exists('.git'):
        print("ОШИБКА: Директория .git не найдена!")
        print("Убедитесь, что вы находитесь в корне git репозитория.")
        return 1
    
    # Проверяем статус
    print("1. Проверяю статус репозитория...")
    if not run_git_command('status'):
        print("Предупреждение: не удалось получить статус")
    print()
    
    # Получаем обновления
    print("2. Получаю обновления из удаленного репозитория...")
    if not run_git_command('fetch'):
        print("ОШИБКА: не удалось получить обновления")
        return 1
    print()
    
    # Обновляем локальную ветку
    print("3. Обновляю локальную ветку...")
    if not run_git_command('pull'):
        print("ОШИБКА: не удалось обновить локальную ветку")
        return 1
    print()
    
    print("=" * 50)
    print("Обновление завершено успешно!")
    print("=" * 50)
    return 0

if __name__ == '__main__':
    sys.exit(main())

