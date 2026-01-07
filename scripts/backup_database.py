#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для создания бэкапа базы данных
Поддерживает автоматический режим для cron с очисткой старых бэкапов
"""

import os
import shutil
import sys
import logging
from datetime import datetime, timedelta

def setup_logging(log_file='backups/backup.log'):
    """Настройка логирования"""
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

def cleanup_old_backups(backup_dir='backups', days_to_keep=7):
    """Удаляет бэкапы старше указанного количества дней"""
    logger = logging.getLogger(__name__)
    logger.info("🗑️  Начало очистки старых бэкапов...")
    
    if not os.path.exists(backup_dir):
        logger.warning(f"Папка бэкапов не найдена: {backup_dir}")
        return
    
    now = datetime.now()
    cutoff_date = now - timedelta(days=days_to_keep)
    
    deleted_count = 0
    kept_count = 0
    
    backups = [f for f in os.listdir(backup_dir) if f.endswith('.db')]
    
    for backup_file in backups:
        backup_path = os.path.join(backup_dir, backup_file)
        
        # Получаем дату создания файла
        file_mtime = os.path.getmtime(backup_path)
        file_date = datetime.fromtimestamp(file_mtime)
        
        # Проверяем возраст файла
        if file_date < cutoff_date:
            try:
                os.remove(backup_path)
                logger.info(f"  ✅ Удален: {backup_file} (создан {file_date.strftime('%Y-%m-%d %H:%M:%S')})")
                deleted_count += 1
            except Exception as e:
                logger.error(f"  ❌ Ошибка удаления {backup_file}: {e}")
        else:
            kept_count += 1
    
    logger.info(f"📊 Очистка завершена: удалено {deleted_count}, оставлено {kept_count}")
    
    return deleted_count

def backup_database(auto_mode=False):
    """Создает бэкап базы данных
    
    Args:
        auto_mode: Если True, работает в автоматическом режиме для cron (без интерактива)
    """
    logger = logging.getLogger(__name__)
    
    if not auto_mode:
        print(f"\n{'='*80}")
        print(f"💾 СОЗДАНИЕ БЭКАПА БАЗЫ ДАННЫХ")
        print(f"{'='*80}\n")
    
    logger.info("="*80)
    logger.info("💾 СОЗДАНИЕ БЭКАПА БАЗЫ ДАННЫХ")
    logger.info("="*80)
    
    # Путь к БД
    db_path = 'instance/figure_skating.db'
    
    if not os.path.exists(db_path):
        error_msg = f"❌ База данных не найдена: {db_path}"
        logger.error(error_msg)
        if not auto_mode:
            print(error_msg)
        return False
    
    # Создаем папку для бэкапов
    backup_dir = 'backups'
    os.makedirs(backup_dir, exist_ok=True)
    
    # Имя файла с датой и временем
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_filename = f'figure_skating_backup_{timestamp}.db'
    backup_path = os.path.join(backup_dir, backup_filename)
    
    # Копируем файл
    logger.info(f"📂 Исходный файл: {db_path}")
    logger.info(f"📁 Путь бэкапа: {backup_path}")
    
    if not auto_mode:
        print(f"📂 Исходный файл: {db_path}")
        print(f"📁 Путь бэкапа: {backup_path}")
    
    try:
        # Получаем размер файла
        file_size = os.path.getsize(db_path)
        size_mb = file_size / (1024 * 1024)
        
        logger.info(f"📊 Размер БД: {size_mb:.2f} МБ")
        if not auto_mode:
            print(f"📊 Размер БД: {size_mb:.2f} МБ")
            print(f"⏳ Копирование...")
        
        shutil.copy2(db_path, backup_path)
        
        # Проверяем, что файл создан
        if os.path.exists(backup_path):
            backup_size = os.path.getsize(backup_path)
            if backup_size == file_size:
                success_msg = f"✅ Бэкап успешно создан: {backup_path}"
                logger.info(success_msg)
                
                if not auto_mode:
                    print(f"✅ Бэкап успешно создан!")
                    print(f"📁 Сохранено в: {backup_path}")
                    
                    # Показываем все бэкапы
                    print(f"\n📋 СПИСОК ВСЕХ БЭКАПОВ:")
                    print("-" * 80)
                    
                    backups = sorted([f for f in os.listdir(backup_dir) if f.endswith('.db')])
                    for i, backup in enumerate(backups, 1):
                        backup_full_path = os.path.join(backup_dir, backup)
                        backup_size_mb = os.path.getsize(backup_full_path) / (1024 * 1024)
                        mtime = os.path.getmtime(backup_full_path)
                        mtime_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
                        print(f"{i:2d}. {backup} ({backup_size_mb:.2f} МБ, {mtime_str})")
                
                return True
            else:
                error_msg = f"❌ Ошибка: размер бэкапа не совпадает с оригиналом!"
                logger.error(error_msg)
                if not auto_mode:
                    print(error_msg)
                return False
        else:
            error_msg = f"❌ Ошибка: файл бэкапа не создан!"
            logger.error(error_msg)
            if not auto_mode:
                print(error_msg)
            return False
            
    except Exception as e:
        error_msg = f"❌ Ошибка при создании бэкапа: {e}"
        logger.error(error_msg)
        if not auto_mode:
            print(error_msg)
        return False

def restore_database(backup_filename):
    """Восстанавливает БД из бэкапа"""
    print(f"\n{'='*80}")
    print(f"♻️  ВОССТАНОВЛЕНИЕ БАЗЫ ДАННЫХ ИЗ БЭКАПА")
    print(f"{'='*80}\n")
    
    db_path = 'instance/figure_skating.db'
    backup_path = os.path.join('backups', backup_filename)
    
    if not os.path.exists(backup_path):
        print(f"❌ Файл бэкапа не найден: {backup_path}")
        return False
    
    print(f"⚠️  ВНИМАНИЕ: Текущая БД будет заменена на бэкап!")
    print(f"📂 Бэкап: {backup_path}")
    print(f"📁 БД: {db_path}")
    
    # Подтверждение
    confirm = input(f"\nПродолжить? (yes/N): ")
    if confirm.lower() != 'yes':
        print(f"❌ Операция отменена")
        return False
    
    try:
        # Создаем бэкап текущей БД перед восстановлением
        if os.path.exists(db_path):
            print(f"\n💾 Создание бэкапа текущей БД перед восстановлением...")
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            temp_backup = f'backups/before_restore_{timestamp}.db'
            shutil.copy2(db_path, temp_backup)
            print(f"✅ Текущая БД сохранена в: {temp_backup}")
        
        # Восстанавливаем из бэкапа
        print(f"\n⏳ Восстановление из бэкапа...")
        shutil.copy2(backup_path, db_path)
        
        print(f"✅ База данных успешно восстановлена из бэкапа!")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при восстановлении: {e}")
        return False

def main():
    """Основная функция"""
    print(f"\n{'#'*80}")
    print(f"# УПРАВЛЕНИЕ БЭКАПАМИ БАЗЫ ДАННЫХ")
    print(f"{'#'*80}")
    
    print(f"\nВыберите действие:")
    print(f"1. Создать бэкап")
    print(f"2. Восстановить из бэкапа")
    print(f"3. Выход")
    
    choice = input(f"\nВаш выбор (1-3): ")
    
    if choice == '1':
        backup_database()
    elif choice == '2':
        # Показываем список бэкапов
        backup_dir = 'backups'
        if os.path.exists(backup_dir):
            backups = sorted([f for f in os.listdir(backup_dir) if f.endswith('.db')])
            if backups:
                print(f"\n📋 ДОСТУПНЫЕ БЭКАПЫ:")
                print("-" * 80)
                for i, backup in enumerate(backups, 1):
                    backup_path = os.path.join(backup_dir, backup)
                    size_mb = os.path.getsize(backup_path) / (1024 * 1024)
                    mtime = os.path.getmtime(backup_path)
                    mtime_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
                    print(f"{i:2d}. {backup} ({size_mb:.2f} МБ, {mtime_str})")
                
                backup_num = input(f"\nВведите номер бэкапа для восстановления: ")
                try:
                    backup_index = int(backup_num) - 1
                    if 0 <= backup_index < len(backups):
                        restore_database(backups[backup_index])
                    else:
                        print(f"❌ Неверный номер бэкапа")
                except ValueError:
                    print(f"❌ Неверный ввод")
            else:
                print(f"\n⚠️  Нет доступных бэкапов")
        else:
            print(f"\n⚠️  Папка с бэкапами не найдена")
    elif choice == '3':
        print(f"\n👋 До свидания!")
    else:
        print(f"\n❌ Неверный выбор")

if __name__ == '__main__':
    # Проверяем аргументы командной строки
    if '--auto' in sys.argv or '--cron' in sys.argv:
        # Автоматический режим для cron
        logger = setup_logging()
        logger.info("🤖 Запуск в автоматическом режиме (cron)")
        
        # Создаем бэкап
        success = backup_database(auto_mode=True)
        
        if success:
            # Очищаем старые бэкапы (старше 7 дней)
            cleanup_old_backups(days_to_keep=7)
            logger.info("✅ Автоматический бэкап завершен успешно")
            sys.exit(0)
        else:
            logger.error("❌ Автоматический бэкап завершился с ошибкой")
            sys.exit(1)
    else:
        # Интерактивный режим
        main()



