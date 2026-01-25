#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ISUCalcFS XML parser.
"""
import xml.etree.ElementTree as ET
from datetime import datetime
import logging

from utils.normalizers import normalize_string, fix_latin_to_cyrillic

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
        self.judges = []
        self.judge_panels = []

    @staticmethod
    def _decode_goe_xml(code):
        """Decode GOE code from XML to value (-5..+3).
        
        Расшифровка кодов GOE в XML файлах ISUCalcFS:
        - Коды 0-8: стандартная шкала (0→-5, 1→-4, 2→-3, 3→-2, 4→-1, 5→0, 6→+1, 7→+2, 8→+3)
        - Код 9: не используется (None)
        - Код 10: специальный случай для -5 (снятие)
        - Коды 11-15: альтернативное кодирование (11→-5, 12→-4, 13→-3, 14→-2, 15→-1)
        
        Args:
            code: Код GOE из XML (строка или число)
            
        Returns:
            Значение GOE от -5 до +3 или None
        """
        if code is None:
            return None
        code = str(code).strip()
        if not code or code == '9':
            return None
        try:
            code_int = int(code)
        except ValueError:
            return None
        
        # Код 9 - не используется
        if code_int == 9:
            return None
        
        # Код 10 - специальный случай (-5)
        if code_int == 10:
            return -5
        
        # Коды 0-8: стандартное кодирование
        if 0 <= code_int <= 8:
            return code_int - 5  # 0→-5, 1→-4, 2→-3, 3→-2, 4→-1, 5→0, 6→+1, 7→+2, 8→+3
        
        # Коды 11-15: альтернативное кодирование для отрицательных значений
        if 11 <= code_int <= 15:
            return code_int - 16  # 11→-5, 12→-4, 13→-3, 14→-2, 15→-1
        
        return None

    def parse(self):
        """Основной метод парсинга XML файла"""
        try:
            tree = ET.parse(self.xml_file_path)
            root = tree.getroot()

            self._parse_events(root)
            self._parse_categories(root)
            self._parse_segments(root)
            self._parse_judges(root)
            self._parse_persons(root)
            self._parse_clubs(root)
            self._parse_participants(root)
            self._parse_performances(root)

            logger.info(
                "Парсинг завершен: %s событий, %s категорий, %s сегментов, %s персон, %s клубов, %s участников, %s выступлений",
                len(self.events), len(self.categories), len(self.segments),
                len(self.persons), len(self.clubs), len(self.participants), len(self.performances)
            )
        except Exception as e:
            logger.error(f"Ошибка при парсинге XML: {e}")
            raise

    def _parse_events(self, root):
        """Парсинг событий"""
        for event in root.findall('.//Event'):
            begin_date = self._parse_date(event.get('EVT_BEGDAT'))
            end_date = self._parse_date(event.get('EVT_ENDDAT'))

            if not begin_date and end_date:
                begin_date = end_date

            event_data = {
                'id': event.get('EVT_ID'),
                'name': normalize_string(event.get('EVT_NAME')),
                'long_name': normalize_string(event.get('EVT_LNAME')),
                'place': normalize_string(event.get('EVT_PLACE')),
                'begin_date': begin_date,
                'end_date': end_date,
                'venue': normalize_string(event.get('EVT_R1NAM')),
                'language': normalize_string(event.get('EVT_PLANG')),
                'event_type': normalize_string(event.get('EVT_TYPE')),
                'competition_type': normalize_string(event.get('EVT_CMPTYP')),
                'status': normalize_string(event.get('EVT_STAT')),
                'calculation_time': normalize_string(event.get('EVT_CALCTM')),
                'external_id': normalize_string(event.get('EVT_EXTDT')),
            }
            self.events.append(event_data)

    def _parse_categories(self, root):
        """Парсинг категорий"""
        for category in root.findall('.//Category'):
            # Нормализуем название категории и исправляем латинские буквы на русские
            category_name = normalize_string(category.get('CAT_NAME'))
            category_name = fix_latin_to_cyrillic(category_name)
            
            category_data = {
                'id': category.get('CAT_ID'),
                'name': category_name,
                'short_name': normalize_string(category.get('CAT_TVNAME')),
                'event_id': category.get('EVT_ID'),
                'gender': normalize_string(category.get('CAT_GENDER')),
                'type': normalize_string(category.get('CAT_TYPE')),
                'status': normalize_string(category.get('CAT_STAT')),
                'external_id': normalize_string(category.get('CAT_EXTDT')),
                'level': normalize_string(category.get('CAT_LEVEL')),
                'num_entries': category.get('CAT_NENT'),
                'num_participants': category.get('CAT_NPAR'),
            }
            self.categories.append(category_data)

    def _parse_segments(self, root):
        """Парсинг сегментов"""
        for segment in root.findall('.//Segment'):
            component_factors = {}
            for idx in range(1, 6):
                factor_raw = segment.get(f'SCP_CRFR{idx:02d}')
                if factor_raw:
                    try:
                        component_factors[idx] = int(factor_raw) / 100
                    except ValueError:
                        continue
            segment_data = {
                'id': segment.get('SCP_ID'),
                'name': normalize_string(segment.get('SCP_NAME')),
                'tv_name': normalize_string(segment.get('SCP_TVNAME')),
                'short_name': normalize_string(segment.get('SCP_SNAM')),
                'category_id': segment.get('CAT_ID'),
                'type': normalize_string(segment.get('SCP_TYPE')),
                'factor': segment.get('SCP_FACTOR'),
                'status': normalize_string(segment.get('SCP_STAT')),
                'external_id': segment.get('SCP_ID'),
                'component_factors': component_factors,
            }
            self.segments.append(segment_data)

    def _parse_judges(self, root):
        """Парсинг судейских бригад по сегментам"""
        seen_judges = set()
        for segment in root.findall('.//Segment'):
            segment_id = segment.get('SCP_ID')
            category_id = segment.get('CAT_ID')
            judges_list = segment.find('Judges_List')
            if judges_list is None:
                continue
            for order_num, judge in enumerate(judges_list.findall('Person'), start=1):
                judge_id = judge.get('PCT_ID')
                judge_data = {
                    'id': judge_id,
                    'external_id': normalize_string(judge.get('PCT_EXTDT')),
                    'first_name': normalize_string(judge.get('PCT_GNAME')),
                    'last_name': normalize_string(judge.get('PCT_FNAMEC') or judge.get('PCT_FNAME')),
                    'full_name_xml': normalize_string(judge.get('PCT_CNAME')),
                    'short_name': normalize_string(judge.get('PCT_SNAME')),
                    'gender': normalize_string(judge.get('PCT_GENDER')),
                    'country': normalize_string(judge.get('PCT_NAT')),
                    'city': normalize_string(judge.get('PCT_CITY')),
                    'qualification': normalize_string(judge.get('PCT_COANAM')),
                }
                if judge_id and judge_id not in seen_judges:
                    self.judges.append(judge_data)
                    seen_judges.add(judge_id)
                self.judge_panels.append({
                    'segment_id': segment_id,
                    'category_id': category_id,
                    'judge_id': judge_id,
                    'role_code': normalize_string(judge.get('PCT_AFUNCT')),
                    'panel_group': normalize_string(judge.get('PCT_COMPOF')),
                    'order_num': order_num,
                })

    def _parse_persons(self, root):
        """Парсинг спортсменов (только основные записи, без дублирования из Team_Members)"""
        for person in root.findall('.//Participants_List//Person_Couple_Team'):
            person_type = person.get('PCT_TYPE')
            person_data = {
                'id': person.get('PCT_ID'),
                'external_id': normalize_string(person.get('PCT_EXTDT')),
                'type': normalize_string(person_type),
                'nationality': normalize_string(person.get('PCT_NAT')),
                'club_id': person.get('PCT_CLBID'),
                'birth_date': self._parse_date(person.get('PCT_BDAY')),
                'gender': normalize_string(person.get('PCT_GENDER')),
                'full_name_xml': normalize_string(person.get('PCT_CNAME')),  # PCT_CNAME - полное имя
                'coach': normalize_string(person.get('PCT_COANAM')),
                'music_sp': normalize_string(person.get('PCT_SPMNAM')),
                'music_fp': normalize_string(person.get('PCT_FSMNAM')),
                'full_name': None,  # PCT_PLNAME - имя для протоколов (приоритетное для вывода)
                'short_name': None,
                'first_name': None,
                'last_name': None,
                'patronymic': None,
                'first_name_cyrillic': None,
                'last_name_cyrillic': None,
                'patronymic_cyrillic': None,
            }

            if person_type == 'PER':
                person_data['first_name'] = normalize_string(person.get('PCT_GNAME'))
                person_data['first_name_cyrillic'] = normalize_string(person.get('PCT_GNAME'))
                person_data['last_name'] = normalize_string(person.get('PCT_FNAMEC') or person.get('PCT_FNAME'))
                person_data['last_name_cyrillic'] = normalize_string(person.get('PCT_FNAMEC'))
                person_data['patronymic'] = normalize_string(person.get('PCT_TLNAME'))
                person_data['patronymic_cyrillic'] = normalize_string(person.get('PCT_TLNAMEC'))
                person_data['full_name'] = normalize_string(person.get('PCT_PLNAME'))  # Имя для протоколов - приоритетное
                person_data['short_name'] = normalize_string(person.get('PCT_PSNAME'))
            elif person_type == 'COU':
                person_data['first_name'] = normalize_string(person.get('PCT_CNAME'))
                person_data['first_name_cyrillic'] = normalize_string(person.get('PCT_CNAME'))
                person_data['last_name'] = normalize_string(person.get('PCT_PSNAME'))
                person_data['last_name_cyrillic'] = normalize_string(person.get('PCT_PSNAME'))
                person_data['full_name'] = normalize_string(person.get('PCT_PLNAME'))
                person_data['short_name'] = normalize_string(person.get('PCT_CNAME'))
                person_data['patronymic'] = None
                person_data['patronymic_cyrillic'] = None
                person_data['gender'] = 'P'

            self.persons.append(person_data)

    def _parse_clubs(self, root):
        """Парсинг клубов (без дублирования)"""
        seen_clubs = set()

        for club in root.findall('.//Club'):
            club_id = club.get('PCT_ID')
            if not club_id:
                continue
            if club_id in seen_clubs:
                continue
            name = normalize_string(club.get('PCT_PLNAME') or club.get('PCT_CNAME'))
            if not name or name.strip() == '':
                continue
            seen_clubs.add(club_id)
            club_data = {
                'id': club_id,
                'external_id': normalize_string(club.get('PCT_EXTDT')),
                'name': name,
                'short_name': normalize_string(club.get('PCT_SNAME')),
                'country': normalize_string(club.get('PCT_NAT')),
                'city': normalize_string(club.get('PCT_CITY')),
            }
            self.clubs.append(club_data)

    def _parse_participants(self, root):
        """Парсинг участников"""
        for participant in root.findall('.//Participant'):
            pct_id = participant.get('PCT_ID')
            person = root.find(f'.//Person_Couple_Team[@PCT_ID=\"{pct_id}\"]')
            pct_ppname = person.get('PCT_PPNAME') if person is not None else None

            participant_data = {
                'id': participant.get('PAR_ID'),
                'external_id': participant.get('PAR_ID'),
                'category_id': participant.get('CAT_ID'),
                'person_id': participant.get('PCT_ID'),
                'bib_number': participant.get('PAR_ENTNUM'),
                'rank': participant.get('PAR_TPLACE'),
                'total_points': participant.get('PAR_TPOINT'),
                'total_rank_points': participant.get('PAR_TPLACE'),
                'club_id': participant.get('PAR_CLBID'),
                'pct_ppname': pct_ppname,
                'status': normalize_string(participant.get('PAR_STAT')),
                'status_segment1': normalize_string(participant.get('PAR_STAT1')),
                'status_segment2': normalize_string(participant.get('PAR_STAT2')),
                'status_segment3': normalize_string(participant.get('PAR_STAT3')),
                'status_segment4': normalize_string(participant.get('PAR_STAT4')),
                'status_segment5': normalize_string(participant.get('PAR_STAT5')),
                'status_segment6': normalize_string(participant.get('PAR_STAT6')),
            }
            self.participants.append(participant_data)

    def _parse_performances(self, root):
        """Парсинг выступлений"""
        segment_factors = {
            seg.get('id'): seg.get('component_factors', {}) for seg in self.segments
        }
        for performance in root.findall('.//Performance'):
            elements = []
            for i in range(1, 21):
                idx = f"{i:02d}"
                executed = performance.get(f'PRF_XNAE{idx}') or performance.get(f'PRF_INAE{idx}')
                if not executed or not str(executed).strip():
                    continue
                planned = performance.get(f'PRF_PNAE{idx}')
                planned_norm = performance.get(f'PRF_PNWE{idx}')
                info_code = performance.get(f'PRF_INAE{idx}')
                confirmed = performance.get(f'PRF_XCFE{idx}')
                time_code = performance.get(f'PRF_XTCE{idx}')
                base_value = performance.get(f'PRF_XBVE{idx}')
                penalty = performance.get(f'PRF_E{idx}PNL')
                result = performance.get(f'PRF_E{idx}RES')
                goe_result = penalty
                if goe_result is None and result and base_value:
                    try:
                        goe_result = int(result) - int(base_value)
                    except (ValueError, TypeError):
                        goe_result = None

                judge_scores = {}
                for j in range(1, 16):
                    jidx = f"{j:02d}"
                    code = performance.get(f'PRF_E{idx}J{jidx}')
                    judge_scores[f'J{jidx}'] = self._decode_goe_xml(code)

                elements.append({
                    'order_num': i,
                    'planned_code': normalize_string(planned),
                    'planned_norm': normalize_string(planned_norm),
                    'executed_code': normalize_string(executed),
                    'info_code': normalize_string(info_code),
                    'confirmed': normalize_string(confirmed),
                    'time_code': normalize_string(time_code),
                    'base_value': base_value,
                    'penalty': penalty,
                    'result': result,
                    'goe_result': goe_result,
                    'judge_scores': judge_scores,
                })

            components = []
            component_map = {
                1: 'CO',
                2: 'TR',
                3: 'PR',
                4: 'IN',
                5: 'SK',
            }
            for c in range(1, 6):
                cidx = f"{c:02d}"
                comp_res = performance.get(f'PRF_C{cidx}RES')
                if not comp_res:
                    continue
                comp_pnl = performance.get(f'PRF_C{cidx}PNL')
                judge_scores = {}
                for j in range(1, 16):
                    jidx = f"{j:02d}"
                    score = performance.get(f'PRF_C{cidx}J{jidx}')
                    judge_scores[f'J{jidx}'] = score
                factor = None
                if segment_factors.get(performance.get('SCP_ID')):
                    factor = segment_factors[performance.get('SCP_ID')].get(c)
                components.append({
                    'component_type': component_map.get(c, str(c)),
                    'factor': factor,
                    'judge_scores': judge_scores,
                    'penalty': comp_pnl,
                    'result': comp_res,
                })

            deductions = performance.get('PRF_DEDTOT')
            if deductions is None:
                total = 0
                for d in range(1, 18):
                    dval = performance.get(f'PRF_DED{d:02d}')
                    if dval:
                        try:
                            total += int(dval)
                        except ValueError:
                            continue
                deductions = total if total else None

            performance_data = {
                'id': performance.get('PRF_ID'),
                'segment_id': performance.get('SCP_ID'),
                'participant_id': performance.get('PAR_ID'),
                'rank': performance.get('PRF_PLACE'),
                'points': performance.get('PRF_POINTS'),
                'status': normalize_string(performance.get('PRF_STAT')),
                'qualification': performance.get('PRF_QUALIF'),
                'starting_number': performance.get('PRF_STNUM'),
                'start_group': performance.get('PRF_STGNUM'),
                'performance_index': performance.get('PRF_INDEX'),
                'locked': performance.get('PRF_LOCK'),
                'deductions': deductions,
                'factor': performance.get('SCP_FACTOR'),
                'tes_sum': performance.get('PRF_M1TOT'),
                'tes_result': performance.get('PRF_M1RES'),
                'pcs_sum': performance.get('PRF_M2TOT'),
                'pcs_result': performance.get('PRF_M2RES'),
                'tech_target': performance.get('PRF_PTOSKA'),
                'points_needed_1': performance.get('PRF_PNEED1'),
                'points_needed_2': performance.get('PRF_PNEED2'),
                'points_needed_3': performance.get('PRF_PNEED3'),
                'elements': elements,
                'components': components,
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
