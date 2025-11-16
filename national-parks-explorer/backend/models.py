"""
Optional SQLAlchemy models and lightweight dataclasses.

Currently ingestion uses direct SQL for simplicity. Enable SQLAlchemy by
creating an engine and Base metadata if desired.
"""
from dataclasses import dataclass
from typing import Optional, List
import os

# SQLAlchemy optional usage:
from sqlalchemy import (
    Column, Integer, String, Text, ForeignKey, DECIMAL, JSON, TIMESTAMP, Boolean
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()
Base = declarative_base()

def get_engine(echo: bool = False):
    """
    Return SQLAlchemy engine. Not mandatory for current direct-MySQL usage.
    """
    user = os.getenv("DB_USER", "root")
    password = os.getenv("DB_PASSWORD", "")
    host = os.getenv("DB_HOST", "127.0.0.1")
    port = os.getenv("DB_PORT", "3306")
    db = os.getenv("DB_NAME", "parksdb")
    url = f"mysql+mysqlconnector://{user}:{password}@{host}:{port}/{db}"
    return create_engine(url, echo=echo)

# Example model (subset). Add others as needed.
class Park(Base):
    __tablename__ = "park"
    id = Column(Integer, primary_key=True)
    park_code = Column(String(20), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    designation = Column(String(255))
    description = Column(Text)
    latitude = Column(DECIMAL(9, 6))
    longitude = Column(DECIMAL(9, 6))

    # relationships (optional)
    activities = relationship("Activity", secondary="park_activity", back_populates="parks")

class Activity(Base):
    __tablename__ = "activity"
    id = Column(Integer, primary_key=True)
    activity_code = Column(String(40), unique=True)
    name = Column(String(200), nullable=False)

    parks = relationship("Park", secondary="park_activity", back_populates="activities")

# Dataclass examples for functions not tied to ORM usage.
@dataclass
class ParkDTO:
    park_code: str
    name: str
    designation: Optional[str]
    description: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    states: List[str]

# TODO: Add more ORM mappings or remove if not using SQLAlchemy.
