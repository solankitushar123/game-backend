"""
Game model — catalog of mini-games available on the platform.
Each game has a server-side scoring validator (see app/games/).
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, Boolean, DateTime, Text, func, Uuid

from app.core.database import Base


class Game(Base):
    __tablename__ = "games"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    slug = Column(String(50), unique=True, nullable=False, index=True)  # e.g. 'reflex-run'
    name = Column(String(100), nullable=False)
    genre = Column(String(30), nullable=False)  # puzzle | arcade | trivia | strategy
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # higher_is_better: True for score-based games, False for time-based (lower=faster=better)
    higher_score_is_better = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
