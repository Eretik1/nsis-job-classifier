from sqlalchemy import Column, Integer, String, Boolean, Float, Text, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class ReferenceTitle(Base):
    __tablename__ = 'reference_titles'
    id = Column(Integer, primary_key=True)
    canonical_title = Column(Text, unique=True, nullable=False)
    cluster_id = Column(Integer)
    cluster_size = Column(Integer)
    created_at = Column(DateTime, default=func.now())

class JobTitle(Base):
    __tablename__ = 'job_titles'
    id = Column(Integer, primary_key=True)
    file_number = Column(Integer, nullable=False)
    line_number = Column(Integer, nullable=False)
    original_title = Column(Text, nullable=False)
    cleaned_title = Column(Text)
    normalized_title = Column(Text)
    is_ai_processed = Column(Boolean, default=False)
    processing_method = Column(String(20), default='algorithm')
    reference_id = Column(Integer, ForeignKey('reference_titles.id'))
    confidence = Column(Float)
    is_manual_verified = Column(Boolean, default=False)
    added_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

class AbbreviationDict(Base):
    __tablename__ = 'abbreviation_dict'
    id = Column(Integer, primary_key=True)
    abbreviation = Column(String(100), unique=True, nullable=False)
    expansion = Column(Text, nullable=False)
    category = Column(String(50))
    is_active = Column(Boolean, default=True)
    added_by = Column(String(50), default='system')
    created_at = Column(DateTime, default=func.now())

class StopPhrase(Base):
    __tablename__ = 'stop_phrases'
    id = Column(Integer, primary_key=True)
    phrase = Column(Text, unique=True, nullable=False)
    pattern_type = Column(String(20), default='literal')
    action = Column(String(20), default='remove')
    comment = Column(Text)
    created_at = Column(DateTime, default=func.now())