#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модели базы данных для системы управления турнирами по фигурному катанию
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

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
    birth_date = db.Column(db.Date, index=True)
    gender = db.Column(db.String(1), index=True)
    country = db.Column(db.String(3), index=True)
    club_id = db.Column(db.Integer, db.ForeignKey('club.id'), index=True)
    
    participants = db.relationship('Participant', backref='athlete', lazy=True, cascade='all, delete-orphan')
    
    @property
    def full_name(self):
        """Полное имя спортсмена - всегда в формате 'Фамилия Имя Отчество'"""
        parts = [self.last_name, self.first_name]
        if self.patronymic:
            parts.append(self.patronymic)
        return ' '.join(parts)
    
    @property
    def short_name(self):
        """Краткое имя спортсмена - 'Фамилия И.'"""
        if not self.last_name or not self.first_name:
            return self.full_name
        first_initial = self.first_name[0] + '.' if self.first_name else ''
        return f"{self.last_name} {first_initial}".strip()
    
    __table_args__ = (
        db.Index('idx_athlete_name_birth', 'first_name', 'last_name', 'birth_date'),
        db.Index('idx_athlete_gender_country', 'gender', 'country'),
        db.Index('idx_athlete_club', 'club_id'),
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
    pct_ppname = db.Column(db.String(50), index=True)
    
    performances = db.relationship('Performance', backref='participant', lazy=True, cascade='all, delete-orphan')
    
    __table_args__ = (
        db.Index('idx_participant_event_category', 'event_id', 'category_id'),
        db.Index('idx_participant_athlete_event', 'athlete_id', 'event_id'),
        db.Index('idx_participant_place_points', 'total_place', 'total_points'),
    )

class Performance(db.Model):
    """Модель выступления в сегменте"""
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
    judge_scores = db.Column(db.Text)  # JSON строка с оценками судей
    
    __table_args__ = (
        db.Index('idx_performance_participant_segment', 'participant_id', 'segment_id'),
        db.Index('idx_performance_place_points', 'place', 'points'),
    )
