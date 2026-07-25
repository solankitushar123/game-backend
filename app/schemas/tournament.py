from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel


class GameResponse(BaseModel):
    id: UUID
    slug: str
    name: str
    genre: str
    description: Optional[str]
    higher_score_is_better: bool

    class Config:
        from_attributes = True


class PayoutTier(BaseModel):
    rank_from: int
    rank_to: int
    amount_paise: int


class TournamentResponse(BaseModel):
    id: UUID
    game_id: UUID
    name: str
    format: str
    entry_fee_paise: int
    prize_pool_paise: int
    funding_source: str
    sponsor_name: Optional[str]
    payout_structure: List[dict]
    max_paid_ranks: int
    starts_at: datetime
    ends_at: datetime
    status: str
    entry_count: Optional[int] = 0

    class Config:
        from_attributes = True


class TournamentCreateRequest(BaseModel):
    game_id: UUID
    name: str
    entry_fee_paise: int = 0
    prize_pool_paise: int
    funding_source: str  # 'sponsor' | 'platform'
    sponsor_name: Optional[str] = None
    payout_structure: List[PayoutTier]
    max_paid_ranks: int = 50
    starts_at: datetime
    ends_at: datetime


class LeaderboardEntry(BaseModel):
    rank: int
    username: str
    score: int
    user_id: UUID
    is_you: bool = False


class JoinTournamentResponse(BaseModel):
    entry_id: UUID
    tournament_id: UUID
    entry_fee_paid_paise: int
    new_wallet_balance_paise: int


class ScoreSubmitRequest(BaseModel):
    session_token: str
    score: int
    session_data: Optional[dict] = None


class ScoreSubmitResponse(BaseModel):
    accepted: bool
    best_score: int
    rejection_reason: Optional[str] = None
