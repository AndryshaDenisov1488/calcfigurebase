#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль для парсинга XML-файлов ISUCalcFS.
"""

import xml.etree.ElementTree as ET
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class ISUCalcFSParser:
    """Парсер для XML файлов ISUCalcFS"""
    
    def __init__(self, xml_file_path):
        self.xml_file_path = xml_file_path
        self.events = []
        self.categories = []
        self.segments = []
        self.persons = []
        self.clubs = []
        self.participants = []
        self.performances = []
        
    def parse(self):
        """Основной метод парсинга XML файла"""
        try:
            tree = ET.parse(self.xml_file_path)
            root = tree.getroot()
            
            # Парсим все секции
            self._parse_events(root)
            self._parse_categories(root)
            self._parse_segments(root)
            self._parse_persons(root)
            self._parse_clubs(root)
            self._parse_participants(root)
            self._parse_performances(root)
            
            logger.info(f"Парсинг завершен: {len(self.events)} событий, {len(self.categories)} категорий, {len(self.segments)} сегментов, {len(self.persons)} персон, {len(self.clubs)} клубов, {len(self.participants)} участников, {len(self.performances)} выступлений")
            
        except Exception as e:
            logger.error(f"Ошибка при парсинге XML: {e}")
            raise
    
    def _parse_events(self, root):
        """Парсинг событий"""
        for event in root.findall('.//Event'):
            event_data = {
                'id': event.get('EVT_ID'),
                'name': event.get('EVT_NAME'),
                'long_name': event.get('EVT_LNAME'),
                'place': event.get('EVT_PLACE'),
                'begin_date': self._parse_date(event.get('EVT_BEGDAT')),
                'end_date': self._parse_date(event.get('EVT_ENDDAT')),
                'venue': event.get('EVT_R1NAM'),
                'language': event.get('EVT_PLANG'),
                'event_type': event.get('EVT_TYPE'),
                'competition_type': event.get('EVT_CMPTYP'),
                'status': event.get('EVT_STAT'),
                'calculation_time': event.get('EVT_CALCTM'),
                'external_id': event.get('EVT_EXTDT')
            }
            self.events.append(event_data)
    
    def _parse_categories(self, root):
        """Парсинг категорий"""
        for category in root.findall('.//Category'):
            category_data = {
                'id': category.get('CAT_ID'),
                'name': category.get('CAT_NAME'),
                'short_name': category.get('CAT_TVNAME'),
                'event_id': category.get('EVT_ID'),
                'gender': category.get('CAT_GENDER'),
                'type': category.get('CAT_TYPE'),
                'status': category.get('CAT_STAT'),
                'external_id': category.get('CAT_EXTDT')
            }
            self.categories.append(category_data)
    
    def _parse_segments(self, root):
        """Парсинг сегментов"""
        for segment in root.findall('.//Segment'):
            segment_data = {
                'id': segment.get('SCP_ID'),
                'name': segment.get('SCP_NAME'),
                'short_name': segment.get('SCP_TVNAME'),
                'category_id': segment.get('CAT_ID'),
                'type': segment.get('SCP_TYPE'),
                'factor': segment.get('SCP_FACTOR'),
                'external_id': segment.get('SCP_ID')
            }
            self.segments.append(segment_data)
    
    def _parse_persons(self, root):
        """Парсинг спортсменов (только из Participants_List)"""
        # Парсим только спортсменов из Participants_List
        for person in root.findall('.//Participants_List//Person_Couple_Team'):
            person_type = person.get('PCT_TYPE')
            person_data = {
                'id': person.get('PCT_ID'),
                'external_id': person.get('PCT_EXTDT'),
                'type': person_type,
                'nationality': person.get('PCT_NAT'),
                'club_id': person.get('PCT_CLBID'),
                'birth_date': self._parse_date(person.get('PCT_BDAY')),
                'gender': person.get('PCT_GENDER'),
                'full_name': None,
                'short_name': None,
                'first_name': None,
                'last_name': None,
                'patronymic': None,
                'first_name_cyrillic': None,
                'last_name_cyrillic': None,
                'patronymic_cyrillic': None,
            }

            if person_type == 'PER':  # Single skater
                person_data['first_name'] = person.get('PCT_GNAME')
                person_data['first_name_cyrillic'] = person.get('PCT_GNAME')
                person_data['last_name'] = person.get('PCT_FNAMEC') or person.get('PCT_FNAME')
                person_data['last_name_cyrillic'] = person.get('PCT_FNAMEC')
                person_data['patronymic'] = person.get('PCT_TLNAME')
                person_data['patronymic_cyrillic'] = person.get('PCT_TLNAMEC')
                person_data['full_name'] = person.get('PCT_PLNAME')
                person_data['short_name'] = person.get('PCT_PSNAME')
            elif person_type == 'COU':  # Pair/Ice Dance
                # Для пар и танцев используем специальные поля
                person_data['first_name'] = person.get('PCT_CNAME')  # Имя пары
                person_data['first_name_cyrillic'] = person.get('PCT_CNAME')
                person_data['last_name'] = person.get('PCT_PSNAME')  # Краткое имя пары
                person_data['last_name_cyrillic'] = person.get('PCT_PSNAME')
                person_data['full_name'] = person.get('PCT_PLNAME')  # Полное имя пары
                person_data['short_name'] = person.get('PCT_CNAME')  # Имя пары как короткое
                # Для пар не используем patronymic
                person_data['patronymic'] = None
                person_data['patronymic_cyrillic'] = None
            
            self.persons.append(person_data)

    def _parse_clubs(self, root):
        """Парсинг клубов"""
        for club in root.findall('.//Club'):
            # Получаем название клуба
            name = club.get('PCT_PLNAME') or club.get('PCT_CNAME')
            
            # Пропускаем клубы без названия
            if not name or name.strip() == '':
                continue
                
            club_data = {
                'id': club.get('PCT_ID'),
                'external_id': club.get('PCT_EXTDT'),
                'name': name,
                'short_name': club.get('PCT_SNAME'),
                'country': club.get('PCT_NAT'),
                'city': club.get('PCT_CITY'),
            }
            self.clubs.append(club_data)

    def _parse_participants(self, root):
        """Парсинг участников"""
        for participant in root.findall('.//Participant'):
            # Получаем PCT_ID для поиска соответствующей персоны
            pct_id = participant.get('PCT_ID')
            
            # Ищем соответствующую персону для получения PCT_PPNAME
            person = root.find(f'.//Person_Couple_Team[@PCT_ID="{pct_id}"]')
            pct_ppname = person.get('PCT_PPNAME') if person is not None else None
            
            participant_data = {
                'id': participant.get('PAR_ID'),
                'external_id': participant.get('PAR_ID'),
                'event_id': participant.get('EVT_ID'),
                'category_id': participant.get('CAT_ID'),
                'person_id': participant.get('PCT_ID'),
                'bib_number': participant.get('PAR_ENTNUM'),
                'rank': participant.get('PAR_TPLACE'),
                'total_points': participant.get('PAR_TPOINT'),
                'total_rank_points': participant.get('PAR_TPLACE'),
                'club_id': participant.get('PAR_CLBID'),
                'pct_ppname': pct_ppname,  # Добавляем поле для отслеживания бесплатных выступлений
            }
            self.participants.append(participant_data)

    def _parse_performances(self, root):
        """Парсинг выступлений"""
        for performance in root.findall('.//Performance'):
            performance_data = {
                'id': performance.get('PRF_ID'),
                'segment_id': performance.get('SCP_ID'),
                'participant_id': performance.get('PAR_ID'),
                'rank': performance.get('PRF_PLACE'),
                'points': performance.get('PRF_POINTS'),
                'starting_number': performance.get('PRF_STNUM'),
                'deductions': performance.get('PRF_DEDUCTIONS'),
                'factor': performance.get('SCP_FACTOR'),
            }
            self.performances.append(performance_data)
    
    def _parse_date(self, date_str):
        """Парсит дату из строки в формате YYYYMMDD"""
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, '%Y%m%d').date()
        except ValueError:
            return None
    
    def get_athletes_with_results(self):
        """Возвращает список спортсменов с результатами"""
        return self.persons

def parse_date(date_str):
    """Парсит дату из строки в формате YYYYMMDD"""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, '%Y%m%d').date()
    except ValueError:
        return None

def parse_date_to_string(date_str):
    """Парсит дату из строки в формате YYYYMMDD и возвращает в формате YYYY-MM-DD"""
    if not date_str:
        return None
    try:
        date_obj = datetime.strptime(date_str, '%Y%m%d').date()
        return date_obj.strftime('%Y-%m-%d')
    except ValueError:
        return None