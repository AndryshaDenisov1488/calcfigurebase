#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Скрипт для синхронизации проекта с git репозиторием:
1. Отправляет изменения с сервера на git (push)
2. Обновляет локальный проект с git (pull)
"""
import subprocess
import sys
import os
from datetime import datetime

def run_git_command(command, check_error=True):
    """Выполняет git команду и выводит результат"""
    try:
        print(f"\n{'='*60}")
        print(f"Выполняю: git {command}")
        print('='*60)
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
            # stderr может содержать полезную информацию, не только ошибки
            if result.returncode != 0:
                print("ОШИБКА:", result.stderr, file=sys.stderr)
            else:
                print(result.stderr)
        
        if check_error and result.returncode != 0:
            return False
        
        return True
    except Exception as e:
        print(f"ОШИБКА при выполнении команды: {e}")
        return False

def main():
    print("=" * 60)
    print("СИНХРОНИЗАЦИЯ ПРОЕКТА С GIT РЕПОЗИТОРИЕМ")
    print("=" * 60)
    print(f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Проверяем, что мы в git репозитории
    if not os.path.exists('.git'):
        print("❌ ОШИБКА: Директория .git не найдена!")
        print("Убедитесь, что вы находитесь в корне git репозитория.")
        print("\n💡 Для инициализации git выполните:")
        print("   git init")
        print("   git remote add origin https://github.com/AndryshaDenisov1488/calcfigurebase.git")
        return 1
    
    # Проверяем наличие remote
    print("Проверяю настройки remote репозитория...")
    remote_result = subprocess.run(
        ['git', 'remote', '-v'],
        capture_output=True,
        text=True,
        encoding='utf-8'
    )
    if remote_result.stdout:
        print(remote_result.stdout)
    else:
        print("⚠️  Remote репозиторий не настроен!")
        print("💡 Выполните:")
        print("   git remote add origin https://github.com/AndryshaDenisov1488/calcfigurebase.git")
        print()
    
    # ============================================
    # ЧАСТЬ 1: ОТПРАВКА ИЗМЕНЕНИЙ НА GIT (PUSH)
    # ============================================
    print("\n" + "="*60)
    print("ЧАСТЬ 1: ОТПРАВКА ИЗМЕНЕНИЙ НА GIT")
    print("="*60)
    
    # Проверяем статус
    print("\n1. Проверяю статус репозитория...")
    if not run_git_command('status', check_error=False):
        print("⚠️  Предупреждение: не удалось получить статус")
    
    # Проверяем, есть ли изменения для коммита
    print("\n2. Проверяю наличие изменений...")
    result = subprocess.run(
        ['git', 'status', '--porcelain'],
        capture_output=True,
        text=True,
        encoding='utf-8'
    )
    
    has_changes = bool(result.stdout.strip())
    
    if has_changes:
        print("✅ Найдены изменения для коммита")
        print("\n3. Добавляю все изменения...")
        if not run_git_command('add .'):
            print("❌ Ошибка при добавлении файлов")
            return 1
        
        print("\n4. Создаю коммит...")
        commit_message = f"Обновление от {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        if not run_git_command(f'commit -m "{commit_message}"'):
            print("⚠️  Возможно, нет новых изменений для коммита")
    else:
        print("ℹ️  Нет изменений для коммита")
    
    # Отправляем на git
    print("\n5. Отправляю изменения на git (push)...")
    push_result = subprocess.run(
        ['git', 'remote', 'get-url', 'origin'],
        capture_output=True,
        text=True
    )
    
    if push_result.returncode != 0:
        print("⚠️  Remote 'origin' не настроен. Пропускаю push.")
        print("💡 Для настройки выполните:")
        print("   git remote add origin https://github.com/AndryshaDenisov1488/calcfigurebase.git")
    else:
        if not run_git_command('push'):
            print("❌ Ошибка при отправке на git")
            print("💡 Возможные причины:")
            print("   - Нет прав доступа")
            print("   - Требуется аутентификация (Personal Access Token)")
            print("   - Проверьте: git remote -v")
            print("⚠️  Продолжаю выполнение...")
        else:
            print("✅ Изменения успешно отправлены на git!")
    
    # ============================================
    # ЧАСТЬ 2: ОБНОВЛЕНИЕ С GIT (PULL)
    # ============================================
    print("\n" + "="*60)
    print("ЧАСТЬ 2: ОБНОВЛЕНИЕ ЛОКАЛЬНОГО ПРОЕКТА С GIT")
    print("="*60)
    
    # Получаем обновления
    print("\n1. Получаю информацию об обновлениях (fetch)...")
    if not run_git_command('fetch', check_error=False):
        print("⚠️  Предупреждение: не удалось получить информацию об обновлениях")
    
    # Обновляем локальную ветку
    print("\n2. Обновляю локальную ветку (pull)...")
    pull_result = subprocess.run(
        ['git', 'remote', 'get-url', 'origin'],
        capture_output=True,
        text=True
    )
    
    if pull_result.returncode != 0:
        print("⚠️  Remote 'origin' не настроен. Пропускаю pull.")
        print("💡 Для настройки выполните:")
        print("   git remote add origin https://github.com/AndryshaDenisov1488/calcfigurebase.git")
    else:
        if not run_git_command('pull'):
            print("⚠️  Ошибка при обновлении локальной ветки")
            print("💡 Возможные причины:")
            print("   - Есть конфликты, которые нужно разрешить вручную")
            print("   - Нет подключения к интернету")
            print("⚠️  Продолжаю выполнение...")
        else:
            print("✅ Локальный проект успешно обновлен!")
    
    # Финальный статус
    print("\n" + "="*60)
    print("3. Финальный статус репозитория:")
    print("="*60)
    run_git_command('status', check_error=False)
    
    print("\n" + "="*60)
    print("✅ СИНХРОНИЗАЦИЯ ЗАВЕРШЕНА УСПЕШНО!")
    print("="*60)
    return 0

if __name__ == '__main__':
    sys.exit(main())

