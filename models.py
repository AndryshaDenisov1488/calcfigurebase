#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модели базы данных для системы управления турнирами по фигурному катанию
"""

from datetime import datetime

from extensions import db

class Event(db.Model):
    """Модель события/турнира"""
    id = db.Column(db.Integer, primary_key=True)
    external_id = db.Column(db.String(50), index=True)  # НЕ unique! Разные XML могут иметь одинаковые ID
    name = db.Column(db.String(200), nullable=False, index=True)
    long_name = db.Column(db.String(500))
    place = db.Column(db.String(200))
    begin_date = db.Column(db.Date, index=True)
    end_date = db.Column(db.Date, index=True)
    venue = db.Column(db.String(200))
    language = db.Column(db.String(10))
    event_type = db.Column(db.String(50), index=True)
    competition_type = db.Column(db.String(50))
    status = db.Column(db.String(20), index=True)
    calculation_time = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    categories = db.relationship('Category', backref='event', lazy=True, cascade='all, delete-orphan')
    participants = db.relationship('Participant', backref='event', lazy=True, cascade='all, delete-orphan')
    
    # Составные индексы для оптимизации запросов
    __table_args__ = (
        db.Index('idx_event_name_date', 'name', 'begin_date'),
        db.Index('idx_event_type_status', 'event_type', 'status'),
        db.Index('idx_event_dates', 'begin_date', 'end_date'),
    )

class Category(db.Model):
    """Модель категории соревнований"""
    id = db.Column(db.Integer, primary_key=True)
    external_id = db.Column(db.String(50), index=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False, index=True)
    tv_name = db.Column(db.String(200))
    normalized_name = db.Column(db.String(200), index=True)  # Нормализованное название разряда
    num_entries = db.Column(db.Integer)
    num_participants = db.Column(db.Integer)
    level = db.Column(db.String(10), index=True)
    gender = db.Column(db.String(10), index=True)
    category_type = db.Column(db.String(10), index=True)
    status = db.Column(db.String(10), index=True)
    
    segments = db.relationship('Segment', backref='category', lazy=True, cascade='all, delete-orphan')
    participants = db.relationship('Participant', backref='category', lazy=True, cascade='all, delete-orphan')
    
    __table_args__ = (
        db.Index('idx_category_event_level', 'event_id', 'level'),
        db.Index('idx_category_gender_type', 'gender', 'category_type'),
    )

class Segment(db.Model):
    """Модель сегмента программы"""
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False, index=True)
    tv_name = db.Column(db.String(200))
    short_name = db.Column(db.String(50))
    segment_type = db.Column(db.String(10), index=True)
    factor = db.Column(db.Float)
    status = db.Column(db.String(10), index=True)
    
    performances = db.relationship('Performance', backref='segment', lazy=True, cascade='all, delete-orphan')
    judge_panels = db.relationship('JudgePanel', backref='segment', lazy=True, cascade='all, delete-orphan')

class Club(db.Model):
    """Модель клуба/организации"""
    id = db.Column(db.Integer, primary_key=True)
    external_id = db.Column(db.String(50), index=True)  # НЕ unique! Разные XML могут иметь одинаковые ID
    name = db.Column(db.String(200), nullable=False, index=True)
    short_name = db.Column(db.String(50))
    country = db.Column(db.String(3), index=True)
    city = db.Column(db.String(100))
    
    athletes = db.relationship('Athlete', backref='club', lazy=True)
    
    __table_args__ = (
        db.Index('idx_club_country', 'country'),
        db.Index('idx_club_name_country', 'name', 'country'),
    )

class Athlete(db.Model):
    """Модель спортсмена"""
    id = db.Column(db.Integer, primary_key=True)
    external_id = db.Column(db.String(50), index=True)
    first_name = db.Column(db.String(100), nullable=False, index=True)
    last_name = db.Column(db.String(100), nullable=False, index=True)
    patronymic = db.Column(db.String(100))
    full_name_xml = db.Column(db.String(300))  # Полное ФИО из XML
    lookup_key = db.Column(db.String(300), index=True)  # Ключ дедупликации
    birth_date = db.Column(db.Date, index=True)
    gender = db.Column(db.String(1), index=True)
    country = db.Column(db.String(3), index=True)
    club_id = db.Column(db.Integer, db.ForeignKey('club.id'), index=True)
    
    participants = db.relationship('Participant', backref='athlete', lazy=True, cascade='all, delete-orphan')
    
    @property
    def full_name(self):
        """Полное имя спортсмена - приоритет у full_name_xml (PCT_PLNAME из XML), иначе составное из частей"""
        # Используем full_name_xml (PCT_PLNAME) если есть - это правильное имя без дублирования
        if self.full_name_xml and self.full_name_xml.strip():
            return self.full_name_xml.strip()
        # Иначе формируем из частей, очищая от дублирования
        from utils.normalizers import remove_duplication
        parts = []
        if self.last_name:
            parts.append(remove_duplication(self.last_name))
        if self.first_name:
            parts.append(remove_duplication(self.first_name))
        if self.patronymic:
            parts.append(remove_duplication(self.patronymic))
        return ' '.join(parts) if parts else ''
    
    @property
    def short_name(self):
        """Краткое имя спортсмена - 'Фамилия И.'"""
        if not self.last_name or not self.first_name:
            return self.full_name
        from utils.normalizers import remove_duplication
        clean_last = remove_duplication(self.last_name)
        clean_first = remove_duplication(self.first_name)
        if not clean_first:
            return clean_last
        first_initial = clean_first[0] + '.' if clean_first else ''
        return f"{clean_last} {first_initial}".strip()
    
    __table_args__ = (
        db.Index('idx_athlete_name_birth', 'first_name', 'last_name', 'birth_date'),
        db.Index('idx_athlete_gender_country', 'gender', 'country'),
        db.Index('idx_athlete_club', 'club_id'),
        db.Index('idx_athlete_lookup_key', 'lookup_key'),
    )

class Participant(db.Model):
    """Модель участника турнира"""
    id = db.Column(db.Integer, primary_key=True)
    external_id = db.Column(db.String(50), index=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False, index=True)
    athlete_id = db.Column(db.Integer, db.ForeignKey('athlete.id'), nullable=False, index=True)
    bib_number = db.Column(db.Integer)
    total_place = db.Column(db.Integer, index=True)
    total_points = db.Column(db.Float, index=True)
    status = db.Column(db.String(10), index=True)
    status_segment1 = db.Column(db.String(10))
    status_segment2 = db.Column(db.String(10))
    status_segment3 = db.Column(db.String(10))
    status_segment4 = db.Column(db.String(10))
    status_segment5 = db.Column(db.String(10))
    status_segment6 = db.Column(db.String(10))
    pct_ppname = db.Column(db.String(50), index=True)
    coach = db.Column(db.String(200))  # Имя тренера (PCT_COANAM из XML)
    
    performances = db.relationship('Performance', backref='participant', lazy=True, cascade='all, delete-orphan')
    
    __table_args__ = (
        db.Index('idx_participant_event_category', 'event_id', 'category_id'),
        db.Index('idx_participant_athlete_event', 'athlete_id', 'event_id'),
        db.Index('idx_participant_place_points', 'total_place', 'total_points'),
        db.UniqueConstraint('event_id', 'category_id', 'athlete_id', name='uq_participant_event_category_athlete'),
    )

class Performance(db.Model):
    """Модель выступления в сегменте"""
    __tablename__ = 'performance'
    id = db.Column(db.Integer, primary_key=True)
    participant_id = db.Column(db.Integer, db.ForeignKey('participant.id'), nullable=False, index=True)
    segment_id = db.Column(db.Integer, db.ForeignKey('segment.id'), nullable=False, index=True)
    index = db.Column(db.Integer)
    status = db.Column(db.String(10), index=True)
    qualification = db.Column(db.String(10))
    start_time = db.Column(db.Time)
    duration = db.Column(db.Time)
    judge_time = db.Column(db.Time)
    place = db.Column(db.Integer, index=True)
    points = db.Column(db.Float, index=True)
    total_1 = db.Column(db.Float)
    result_1 = db.Column(db.Float)
    total_2 = db.Column(db.Float)
    result_2 = db.Column(db.Float)
    tes_total = db.Column(db.Integer)
    pcs_total = db.Column(db.Integer)
    deductions = db.Column(db.Integer)
    bonus = db.Column(db.Integer)
    judge_scores = db.Column(db.Text)  # JSON строка с оценками судей

    elements = db.relationship('Element', backref='performance', lazy=True, cascade='all, delete-orphan')
    components = db.relationship('ComponentScore', backref='performance', lazy=True, cascade='all, delete-orphan')
    
    __table_args__ = (
        db.Index('idx_performance_participant_segment', 'participant_id', 'segment_id'),
        db.Index('idx_performance_place_points', 'place', 'points'),
        db.UniqueConstraint('participant_id', 'segment_id', name='uq_performance_participant_segment'),
    )

class Element(db.Model):
    """Модель выполненного элемента выступления"""
    __tablename__ = 'element'
    id = db.Column(db.Integer, primary_key=True)
    performance_id = db.Column(db.Integer, db.ForeignKey('performance.id'), nullable=False, index=True)
    order_num = db.Column(db.Integer, index=True)
    planned_code = db.Column(db.String(20))
    executed_code = db.Column(db.String(20))
    info_code = db.Column(db.String(20))
    base_value = db.Column(db.Integer)
    goe_result = db.Column(db.Integer)
    penalty = db.Column(db.Integer)
    result = db.Column(db.Integer)
    judge_scores = db.Column(db.JSON)

class ComponentScore(db.Model):
    """Модель оценок компонентов программы"""
    __tablename__ = 'component_score'
    id = db.Column(db.Integer, primary_key=True)
    performance_id = db.Column(db.Integer, db.ForeignKey('performance.id'), nullable=False, index=True)
    component_type = db.Column(db.String(10))
    factor = db.Column(db.Float)
    judge_scores = db.Column(db.JSON)
    penalty = db.Column(db.Integer)
    result = db.Column(db.Integer)

class Judge(db.Model):
    """Модель судьи"""
    id = db.Column(db.Integer, primary_key=True)
    external_id = db.Column(db.String(50), index=True)
    first_name = db.Column(db.String(100), index=True)
    last_name = db.Column(db.String(100), index=True)
    full_name_xml = db.Column(db.String(300))
    short_name = db.Column(db.String(50))
    gender = db.Column(db.String(1), index=True)
    country = db.Column(db.String(3), index=True)
    city = db.Column(db.String(100))
    qualification = db.Column(db.String(100))

    __table_args__ = (
        db.Index('idx_judge_name', 'last_name', 'first_name'),
    )

class JudgePanel(db.Model):
    """Связь судьи с сегментом (судейская бригада)"""
    id = db.Column(db.Integer, primary_key=True)
    segment_id = db.Column(db.Integer, db.ForeignKey('segment.id'), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), index=True)
    judge_id = db.Column(db.Integer, db.ForeignKey('judge.id'), nullable=False, index=True)
    role_code = db.Column(db.String(10))
    panel_group = db.Column(db.String(10))
    order_num = db.Column(db.Integer)

    judge = db.relationship('Judge', backref='panel_assignments')

    __table_args__ = (
        db.UniqueConstraint('segment_id', 'judge_id', name='uq_judgepanel_segment_judge'),
    )

class Coach(db.Model):
    """Модель тренера"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, index=True)
    normalized_name = db.Column(db.String(200), index=True)  # Нормализованное имя для поиска
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    assignments = db.relationship('CoachAssignment', backref='coach', lazy=True, cascade='all, delete-orphan')
    
    __table_args__ = (
        db.Index('idx_coach_name', 'name'),
        db.Index('idx_coach_normalized', 'normalized_name'),
    )

class CoachAssignment(db.Model):
    """Модель назначения тренера спортсмену (отслеживание переходов)"""
    id = db.Column(db.Integer, primary_key=True)
    coach_id = db.Column(db.Integer, db.ForeignKey('coach.id'), nullable=False, index=True)
    athlete_id = db.Column(db.Integer, db.ForeignKey('athlete.id'), nullable=False, index=True)
    participant_id = db.Column(db.Integer, db.ForeignKey('participant.id'), nullable=False, index=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False, index=True)
    start_date = db.Column(db.Date, nullable=False, index=True)  # Дата начала работы с этим тренером
    end_date = db.Column(db.Date, index=True)  # Дата окончания (если спортсмен перешел к другому тренеру)
    is_current = db.Column(db.Boolean, default=True, index=True)  # Текущий тренер или нет
    
    athlete = db.relationship('Athlete', backref='coach_assignments')
    participant = db.relationship('Participant', backref='coach_assignment')
    event = db.relationship('Event', backref='coach_assignments')
    
    __table_args__ = (
        db.Index('idx_coach_assignment_athlete_date', 'athlete_id', 'start_date'),
        db.Index('idx_coach_assignment_current', 'athlete_id', 'is_current'),
    )
