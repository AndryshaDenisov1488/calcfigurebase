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

def unify_mafkk_schools():
    """Объединяет все школы МАФКК под единое название"""
    
    with app.app_context():
        print("🔍 Поиск школ МАФКК для объединения...")
        
        # Список школ МАФКК для объединения
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
        
        if not target_club:
            print(f"❌ Целевой клуб '{target_name}' не найден!")
            return
        
        print(f"✅ Найден целевой клуб: ID {target_club.id}, '{target_club.name}'")
        
        # Статистика до объединения
        total_athletes_before = 0
        clubs_to_merge = []
        
        for school_name in mafkk_schools:
            club = Club.query.filter_by(name=school_name).first()
            if club:
                athletes_count = Athlete.query.filter_by(club_id=club.id).count()
                clubs_to_merge.append({
                    'club': club,
                    'athletes_count': athletes_count
                })
                total_athletes_before += athletes_count
                print(f"📋 Найден клуб: ID {club.id}, '{club.name}' - {athletes_count} спортсменов")
            else:
                print(f"⚠️  Клуб '{school_name}' не найден в БД")
        
        if not clubs_to_merge:
            print("❌ Не найдено клубов для объединения!")
            return
        
        print(f"\n📊 Статистика объединения:")
        print(f"   Клубов для объединения: {len(clubs_to_merge)}")
        print(f"   Спортсменов для переноса: {total_athletes_before}")
        print(f"   Целевой клуб: ID {target_club.id}")
        
        # Подтверждение
        print(f"\n🔄 Начинаем объединение...")
        
        # Переносим спортсменов
        transferred_count = 0
        for club_info in clubs_to_merge:
            club = club_info['club']
            athletes_count = club_info['athletes_count']
            
            print(f"   Переносим {athletes_count} спортсменов из клуба '{club.name}'...")
            
            # Обновляем club_id у всех спортсменов
            updated = Athlete.query.filter_by(club_id=club.id).update({
                'club_id': target_club.id
            })
            
            transferred_count += updated
            print(f"   ✅ Перенесено {updated} спортсменов")
        
        # Удаляем старые клубы
        print(f"\n🗑️  Удаляем старые клубы...")
        deleted_clubs = []
        for club_info in clubs_to_merge:
            club = club_info['club']
            print(f"   Удаляем клуб ID {club.id}: '{club.name}'")
            db.session.delete(club)
            deleted_clubs.append(club.name)
        
        # Сохраняем изменения
        print(f"\n💾 Сохранение изменений...")
        db.session.commit()
        
        # Проверяем результат
        final_athletes_count = Athlete.query.filter_by(club_id=target_club.id).count()
        
        print(f"\n✅ Объединение завершено!")
        print(f"📊 Результат:")
        print(f"   Перенесено спортсменов: {transferred_count}")
        print(f"   Удалено клубов: {len(deleted_clubs)}")
        print(f"   Итоговое количество спортсменов в целевом клубе: {final_athletes_count}")
        
        print(f"\n🗑️  Удаленные клубы:")
        for club_name in deleted_clubs:
            print(f"   - {club_name}")
        
        print(f"\n🎉 Все школы МАФКК объединены под названием:")
        print(f"   '{target_name}' (ID {target_club.id})")

if __name__ == '__main__':
    unify_mafkk_schools()
