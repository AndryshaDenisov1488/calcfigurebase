#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестовый скрипт для проверки Google Sheets экспорта
"""

import os
import sys

def test_credentials():
    """Проверяет наличие файла credentials"""
    print("🧪 ТЕСТ 1: Проверка файла credentials")
    print("-" * 60)
    
    if os.path.exists('google_credentials.json'):
        print("✅ Файл google_credentials.json найден!")
        
        # Проверяем размер файла
        size = os.path.getsize('google_credentials.json')
        print(f"   Размер файла: {size} байт")
        
        if size < 100:
            print("   ⚠️  Файл слишком маленький, возможно повреждён")
            return False
        
        return True
    else:
        print("❌ Файл google_credentials.json НЕ найден!")
        print("   Создайте Service Account и скачайте JSON ключ")
        print("   См. GOOGLE_SHEETS_SETUP.md")
        return False

def test_import():
    """Проверяет возможность импорта модулей"""
    print("\n🧪 ТЕСТ 2: Проверка установленных библиотек")
    print("-" * 60)
    
    try:
        import gspread
        print("✅ gspread установлен")
    except ImportError:
        print("❌ gspread НЕ установлен")
        print("   Установите: pip install gspread")
        return False
    
    try:
        import google.auth
        print("✅ google-auth установлен")
    except ImportError:
        print("❌ google-auth НЕ установлен")
        print("   Установите: pip install google-auth")
        return False
    
    return True

def test_connection():
    """Проверяет подключение к Google Sheets API"""
    print("\n🧪 ТЕСТ 3: Проверка подключения к Google API")
    print("-" * 60)
    
    try:
        from google_sheets_sync import get_google_sheets_client
        
        print("⏳ Подключение к Google Sheets API...")
        client = get_google_sheets_client()
        
        print("✅ Подключение успешно!")
        print(f"   Client: {type(client).__name__}")
        
        return True
        
    except FileNotFoundError as e:
        print(f"❌ Ошибка: {e}")
        print("   Файл google_credentials.json не найден")
        return False
        
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        print("   Проверьте правильность файла google_credentials.json")
        return False

def test_data_extraction():
    """Проверяет извлечение данных из БД"""
    print("\n🧪 ТЕСТ 4: Проверка извлечения данных из БД")
    print("-" * 60)
    
    try:
        from google_sheets_sync import get_athletes_data
        
        print("⏳ Получение данных из БД...")
        athletes_by_rank = get_athletes_data()
        
        total_athletes = sum(len(athletes) for athletes in athletes_by_rank.values())
        
        print(f"✅ Данные получены!")
        print(f"   Разрядов: {len(athletes_by_rank)}")
        print(f"   Всего спортсменов: {total_athletes}")
        
        # Показываем первые 3 разряда
        print("\n   Разряды:")
        for i, (rank, athletes) in enumerate(list(athletes_by_rank.items())[:3], 1):
            print(f"   {i}. {rank}: {len(athletes)} спортсменов")
        
        if len(athletes_by_rank) > 3:
            print(f"   ... и ещё {len(athletes_by_rank) - 3} разрядов")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_full_export():
    """Тестовый экспорт (создаёт новую таблицу)"""
    print("\n🧪 ТЕСТ 5: Полный экспорт в Google Sheets")
    print("-" * 60)
    
    response = input("Выполнить тестовый экспорт? (создаст новую таблицу) (y/N): ")
    
    if response.lower() != 'y':
        print("⏭️  Пропущено")
        return True
    
    try:
        from google_sheets_sync import export_to_google_sheets
        
        print("⏳ Экспорт в Google Sheets...")
        result = export_to_google_sheets()
        
        if result['success']:
            print(f"✅ {result['message']}")
            print(f"\n🔗 URL таблицы:")
            print(f"   {result['url']}")
            print(f"\n💡 Spreadsheet ID:")
            print(f"   {result['spreadsheet_id']}")
            print(f"\n   Сохраните ID в .env файл:")
            print(f"   GOOGLE_SHEETS_ID={result['spreadsheet_id']}")
            return True
        else:
            print(f"❌ {result['message']}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Запускает все тесты"""
    print("\n" + "="*60)
    print("🧪 ТЕСТИРОВАНИЕ GOOGLE SHEETS ЭКСПОРТА")
    print("="*60 + "\n")
    
    results = []
    
    # Тест 1: Credentials
    results.append(("Файл credentials", test_credentials()))
    
    # Тест 2: Импорт библиотек
    if results[-1][1]:  # Если предыдущий тест прошёл
        results.append(("Установка библиотек", test_import()))
    else:
        print("\n⏭️  Пропуск остальных тестов (нет credentials)")
        results.append(("Установка библиотек", None))
        results.append(("Подключение к API", None))
        results.append(("Извлечение данных", None))
        results.append(("Полный экспорт", None))
    
    # Тест 3: Подключение
    if results[-1][1]:
        results.append(("Подключение к API", test_connection()))
    else:
        print("\n⏭️  Пропуск остальных тестов")
        results.append(("Подключение к API", None))
        results.append(("Извлечение данных", None))
        results.append(("Полный экспорт", None))
    
    # Тест 4: Данные
    if results[-1][1]:
        results.append(("Извлечение данных", test_data_extraction()))
    else:
        results.append(("Извлечение данных", None))
        results.append(("Полный экспорт", None))
    
    # Тест 5: Экспорт
    if results[-1][1]:
        results.append(("Полный экспорт", test_full_export()))
    else:
        results.append(("Полный экспорт", None))
    
    # Итоги
    print("\n" + "="*60)
    print("📊 ИТОГИ ТЕСТИРОВАНИЯ")
    print("="*60 + "\n")
    
    passed = sum(1 for _, result in results if result is True)
    failed = sum(1 for _, result in results if result is False)
    skipped = sum(1 for _, result in results if result is None)
    total = len(results)
    
    for test_name, result in results:
        if result is True:
            status = "✅ ПРОЙДЕН"
        elif result is False:
            status = "❌ НЕ ПРОЙДЕН"
        else:
            status = "⏭️  ПРОПУЩЕН"
        
        print(f"   {status}: {test_name}")
    
    print(f"\n{'='*60}")
    print(f"Пройдено: {passed}/{total}")
    print(f"Не пройдено: {failed}/{total}")
    print(f"Пропущено: {skipped}/{total}")
    
    if failed == 0 and passed > 0:
        print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        print("\n✅ Готово к использованию:")
        print("   1. Запустите приложение: python app.py")
        print("   2. Откройте: http://localhost:5001/admin/login")
        print("   3. Перейдите: Экспорт в Google Sheets")
        print("   4. Нажмите кнопку 'Экспортировать'")
        return 0
    elif failed > 0:
        print("\n⚠️  Некоторые тесты не пройдены")
        print("   См. инструкцию: GOOGLE_SHEETS_SETUP.md")
        return 1
    else:
        print("\n⚠️  Тесты не выполнены")
        return 1

if __name__ == '__main__':
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⏹️  Прервано пользователем")
        sys.exit(1)


