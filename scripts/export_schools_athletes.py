#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для выгрузки всех названий школ и количества детей (спортсменов)
Результат сохраняется в CSV файл и выводится в консоль
"""

import os
import sys
import csv
from datetime import datetime

# Добавляем текущую директорию в путь
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app import app, db
from models import Club, Athlete


def export_schools_athletes(output_format='csv'):
    """
    Выгружает все школы и количество детей в каждой школе
    
    Args:
        output_format: формат вывода ('csv', 'console', 'both')
    
    Returns:
        list: список словарей с данными о школах
    """
    
    with app.app_context():
        print("=" * 80)
        print("ВЫГРУЗКА ШКОЛ И КОЛИЧЕСТВА ДЕТЕЙ")
        print("=" * 80)
        print()
        
        # Получаем все клубы (школы)
        all_clubs = Club.query.order_by(Club.name).all()
        total_clubs = len(all_clubs)
        
        print(f"📊 Всего школ в базе: {total_clubs}")
        print()
        
        # Собираем данные о школах и количестве детей
        schools_data = []
        total_athletes = 0
        
        print("📋 Обработка школ...")
        print("-" * 80)
        
        for club in all_clubs:
            # Подсчитываем количество спортсменов (детей) в этой школе
            athletes_count = Athlete.query.filter_by(club_id=club.id).count()
            total_athletes += athletes_count
            
            school_info = {
                'id': club.id,
                'name': club.name,
                'short_name': club.short_name or '',
                'city': club.city or '',
                'country': club.country or '',
                'athletes_count': athletes_count
            }
            
            schools_data.append(school_info)
            
            # Выводим информацию в консоль
            city_info = f" ({club.city})" if club.city else ""
            print(f"  {club.id:4d} | {athletes_count:4d} детей | {club.name}{city_info}")
        
        # Сортируем по количеству детей (по убыванию)
        schools_data.sort(key=lambda x: x['athletes_count'], reverse=True)
        
        print()
        print("=" * 80)
        print("ИТОГОВАЯ СТАТИСТИКА")
        print("=" * 80)
        print(f"Всего школ: {total_clubs}")
        print(f"Всего детей (спортсменов): {total_athletes}")
        print(f"Среднее количество детей на школу: {total_athletes / total_clubs:.2f}" if total_clubs > 0 else "Нет данных")
        print()
        
        # Топ-10 школ по количеству детей
        print("=" * 80)
        print("ТОП-10 ШКОЛ ПО КОЛИЧЕСТВУ ДЕТЕЙ")
        print("=" * 80)
        for i, school in enumerate(schools_data[:10], 1):
            city_info = f" ({school['city']})" if school['city'] else ""
            print(f"  {i:2d}. {school['athletes_count']:4d} детей | {school['name']}{city_info}")
        print()
        
        # Сохраняем в CSV файл
        if output_format in ('csv', 'both'):
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = os.path.join(project_root, f'schools_export_{timestamp}.csv')
            
            try:
                with open(output_file, 'w', newline='', encoding='utf-8-sig') as csvfile:
                    fieldnames = ['id', 'name', 'short_name', 'city', 'country', 'athletes_count']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    
                    # Записываем заголовки
                    writer.writeheader()
                    
                    # Записываем данные
                    for school in schools_data:
                        writer.writerow(school)
                
                print("=" * 80)
                print(f"✅ Данные успешно сохранены в файл: {output_file}")
                print("=" * 80)
                print()
                
            except Exception as e:
                print(f"❌ Ошибка при сохранении файла: {e}", file=sys.stderr)
                import traceback
                traceback.print_exc()
        
        return schools_data


def main():
    """Основная функция"""
    try:
        # По умолчанию сохраняем в CSV и выводим в консоль
        schools_data = export_schools_athletes(output_format='both')
        return 0
    except Exception as e:
        print(f"❌ Ошибка: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())

