"""
Tournament + TournamentEntry models.

Format in v1: ASYNC_LADDER only (per blueprint's recommended fastest-to-launch format —
players play independently within a time window; ranked by best score). Bracket format
is modeled in the schema (format column) for future extension but not implemented yet.

Compliance-critical design choice: entry_fee_paise funds tournament administration only.
prize_pool_paise is explicitly tied to a funding_source ('sponsor' or 'platform') and is
NEVER computed as a function of pooled entry fees. This keeps the product in the
"skill-based gaming with sponsor-funded prizes" category rather than pooled-stake gambling.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, Integer, BigInteger, Boolean, DateTime, ForeignKey, Text, UniqueConstraint, func, Uuid, JSON
from sqlalchemy.orm import relationship

from app.core.database import Base


class Tournament(Base):
    __tablename__ = "tournaments"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    game_id = Column(Uuid, ForeignKey("games.id"), nullable=False, index=True)

    name = Column(String(150), nullable=False)
    format = Column(String(20), default="async_ladder", nullable=False)  # async_ladder | bracket

    entry_fee_paise = Column(BigInteger, default=0, nullable=False)

    # Prize pool funding — explicit and auditable
    prize_pool_paise = Column(BigInteger, default=0, nullable=False)
    funding_source = Column(String(30), nullable=False, default="platform")  # sponsor | platform
    sponsor_name = Column(String(150), nullable=True)

    # Payout structure: ordered list of {rank_from, rank_to, amount_paise} stored as JSON
    payout_structure = Column(JSON, nullable=False, default=list)

    max_paid_ranks = Column(Integer, default=50, nullable=False)

    starts_at = Column(DateTime(timezone=True), nullable=False)
    ends_at = Column(DateTime(timezone=True), nullable=False)

    status = Column(String(20), default="scheduled", nullable=False, index=True)
    # scheduled | live | ended | settled | cancelled

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    game = relationship("Game")
    entries = relationship("TournamentEntry", back_populates="tournament")


class TournamentEntry(Base):
    __tablename__ = "tournament_entries"
    __table_args__ = (UniqueConstraint("tournament_id", "user_id", name="uq_tournament_user"),)

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    tournament_id = Column(Uuid, ForeignKey("tournaments.id"), nullable=False, index=True)
    user_id = Column(Uuid, ForeignKey("users.id"), nullable=False, index=True)

    best_score = Column(BigInteger, default=0, nullable=False)
    attempts_used = Column(Integer, default=0, nullable=False)

    final_rank = Column(Integer, nullable=True)
    prize_awarded_paise = Column(BigInteger, default=0, nullable=False)
    prize_settled = Column(Boolean, default=False, nullable=False)

    entry_fee_paid_paise = Column(BigInteger, default=0, nullable=False)

    joined_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    tournament = relationship("Tournament", back_populates="entries")
    user = relationship("User", back_populates="entries")


class GameScoreSubmission(Base):
    """
    Immutable record of every score submission, including ones that fail
    server-side validation. Critical for anti-cheat audit trails.
    """
    __tablename__ = "game_score_submissions"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    tournament_entry_id = Column(Uuid, ForeignKey("tournament_entries.id"), nullable=False, index=True)
    user_id = Column(Uuid, ForeignKey("users.id"), nullable=False, index=True)

    submitted_score = Column(BigInteger, nullable=False)
    is_valid = Column(Boolean, nullable=False)
    rejection_reason = Column(String(200), nullable=True)

    # Server-side replay/session data used to validate the score
    session_token = Column(String(64), nullable=False)
    raw_session_data = Column(JSON, nullable=True)

    client_ip = Column(String(45), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
