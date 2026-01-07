#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from flask import Flask
from models import db, Club, Athlete
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///figure_skating.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

def check_mafkk_schools():
    """Проверяет, какие школы МАФКК есть в базе данных"""
    
    with app.app_context():
        print("🔍 Поиск школ МАФКК в базе данных...")
        print("=" * 50)
        
        # Список школ МАФКК для поиска
        mafkk_schools = [
            "МАФКК Олимп",
            "МАФКК Медведково", 
            "ГБУ ДО МАФКК, Школа \"Легенда\", отд. \"Косино\"",
            "ГБУ ДО МАФК, школа Сокольники",
            "ГБУ ДО МАФК, Школа \"Легенда\", отд. \"Снежные барсы\""
        ]
        
        # Целевое название
        target_name = "ГБУ ДО Московская академия фигурного катания на коньках"
        
        # Ищем целевой клуб
        target_club = Club.query.filter_by(name=target_name).first()
        
        print(f"🎯 Целевой клуб:")
        if target_club:
            athletes_count = Athlete.query.filter_by(club_id=target_club.id).count()
            print(f"   ✅ ID {target_club.id}: '{target_club.name}' - {athletes_count} спортсменов")
        else:
            print(f"   ❌ Клуб '{target_name}' не найден!")
        
        print(f"\n📋 Поиск школ МАФКК:")
        print("-" * 30)
        
        found_clubs = []
        total_athletes = 0
        
        for school_name in mafkk_schools:
            club = Club.query.filter_by(name=school_name).first()
            if club:
                athletes_count = Athlete.query.filter_by(club_id=club.id).count()
                found_clubs.append({
                    'id': club.id,
                    'name': club.name,
                    'athletes_count': athletes_count
                })
                total_athletes += athletes_count
                print(f"   ✅ ID {club.id}: '{club.name}' - {athletes_count} спортсменов")
            else:
                print(f"   ❌ '{school_name}' - не найден")
        
        print(f"\n📊 Статистика:")
        print(f"   Найдено клубов МАФКК: {len(found_clubs)}")
        print(f"   Всего спортсменов в клубах МАФКК: {total_athletes}")
        
        if target_club:
            target_athletes = Athlete.query.filter_by(club_id=target_club.id).count()
            print(f"   Спортсменов в целевом клубе: {target_athletes}")
            print(f"   Итого будет после объединения: {target_athletes + total_athletes}")
        
        # Поиск похожих названий
        print(f"\n🔍 Поиск похожих названий (содержащих 'МАФК' или 'Московская академия'):")
        print("-" * 30)
        
        similar_clubs = Club.query.filter(
            db.or_(
                Club.name.contains('МАФК'),
                Club.name.contains('Московская академия'),
                Club.name.contains('МАФКК')
            )
        ).all()
        
        for club in similar_clubs:
            athletes_count = Athlete.query.filter_by(club_id=club.id).count()
            print(f"   ID {club.id}: '{club.name}' - {athletes_count} спортсменов")
        
        return found_clubs, target_club

if __name__ == '__main__':
    check_mafkk_schools()
