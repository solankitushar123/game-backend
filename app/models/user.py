"""
User model.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, Boolean, DateTime, Date, func, Uuid
from sqlalchemy.orm import relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    username = Column(String(32), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(15), unique=True, nullable=True, index=True)
    password_hash = Column(String(255), nullable=False)

    date_of_birth = Column(Date, nullable=False)
    is_age_verified = Column(Boolean, default=False, nullable=False)
    is_kyc_verified = Column(Boolean, default=False, nullable=False)
    kyc_status = Column(String(20), default="not_started", nullable=False)
    # not_started | pending | verified | rejected

    is_active = Column(Boolean, default=True, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    is_flagged = Column(Boolean, default=False, nullable=False)  # fraud/anti-cheat flag

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    wallet = relationship("Wallet", back_populates="user", uselist=False)
    entries = relationship("TournamentEntry", back_populates="user")
