import uuid
from datetime import datetime
from app.core.time_utils import now_utc

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.models.user import User
from app.models.tournament import Tournament, TournamentEntry, GameScoreSubmission
from app.models.game import Game
from app.schemas.tournament import (
    TournamentResponse, JoinTournamentResponse, LeaderboardEntry,
    ScoreSubmitRequest, ScoreSubmitResponse,
)
from app.services.wallet_service import WalletService, InsufficientBalanceError
from app.services.leaderboard_service import LeaderboardService
from app.services.audit_service import AuditService
from app.games.session import create_session_token, validate_and_consume_session
from app.api.deps import get_current_user, get_client_ip

router = APIRouter(prefix="/api/tournaments", tags=["tournaments"])


@router.get("", response_model=list[TournamentResponse])
def list_tournaments(status_filter: str | None = None, db: Session = Depends(get_db)):
    q = db.query(Tournament)
    if status_filter:
        q = q.filter(Tournament.status == status_filter)
    tournaments = q.order_by(Tournament.starts_at.desc()).all()

    results = []
    for t in tournaments:
        entry_count = db.query(func.count(TournamentEntry.id)).filter(
            TournamentEntry.tournament_id == t.id
        ).scalar()
        resp = TournamentResponse.model_validate(t)
        resp.entry_count = entry_count
        results.append(resp)
    return results


@router.get("/{tournament_id}", response_model=TournamentResponse)
def get_tournament(tournament_id: uuid.UUID, db: Session = Depends(get_db)):
    t = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found")
    entry_count = db.query(func.count(TournamentEntry.id)).filter(
        TournamentEntry.tournament_id == t.id
    ).scalar()
    resp = TournamentResponse.model_validate(t)
    resp.entry_count = entry_count
    return resp


@router.post("/{tournament_id}/join", response_model=JoinTournamentResponse)
def join_tournament(
    tournament_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    t = db.query(Tournament).filter(Tournament.id == tournament_id).with_for_update().first()
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found")

    if t.status not in ("scheduled", "live"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tournament is not open for entry")
    if t.ends_at <= now_utc():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tournament has already ended")

    existing = db.query(TournamentEntry).filter(
        TournamentEntry.tournament_id == tournament_id,
        TournamentEntry.user_id == current_user.id,
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already joined this tournament")

    if not current_user.is_age_verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Age verification required")

    try:
        if t.entry_fee_paise > 0:
            tx = WalletService.debit_entry_fee(db, current_user.id, t.entry_fee_paise, tournament_id)
            fee_paid = t.entry_fee_paise
        else:
            fee_paid = 0
    except InsufficientBalanceError:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Insufficient wallet balance")

    entry = TournamentEntry(
        tournament_id=tournament_id,
        user_id=current_user.id,
        entry_fee_paid_paise=fee_paid,
    )
    db.add(entry)
    db.flush()

    if t.status == "scheduled":
        t.status = "live"

    AuditService.log(
        db, action="tournament.joined", actor_user_id=current_user.id, actor_type="user",
        target_type="tournament", target_id=tournament_id,
        metadata={"entry_fee_paise": fee_paid}, ip_address=get_client_ip(request),
    )
    db.commit()

    from app.models.wallet import Wallet
    wallet = db.query(Wallet).filter(Wallet.user_id == current_user.id).first()

    return JoinTournamentResponse(
        entry_id=entry.id,
        tournament_id=tournament_id,
        entry_fee_paid_paise=fee_paid,
        new_wallet_balance_paise=wallet.balance_paise,
    )


@router.get("/{tournament_id}/leaderboard", response_model=list[LeaderboardEntry])
def get_leaderboard(
    tournament_id: uuid.UUID,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    t = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found")

    top = LeaderboardService.get_top(tournament_id, limit)
    if not top:
        # cache miss -> rehydrate from Postgres
        entries = db.query(TournamentEntry).filter(TournamentEntry.tournament_id == tournament_id).all()
        LeaderboardService.rebuild_from_db(tournament_id, [(str(e.user_id), e.best_score) for e in entries])
        top = LeaderboardService.get_top(tournament_id, limit)

    user_ids = [uuid.UUID(uid) for uid, _ in top]
    users = {u.id: u.username for u in db.query(User).filter(User.id.in_(user_ids)).all()} if user_ids else {}

    return [
        LeaderboardEntry(
            rank=idx + 1,
            username=users.get(uuid.UUID(uid), "unknown"),
            score=int(score),
            user_id=uuid.UUID(uid),
        )
        for idx, (uid, score) in enumerate(top)
    ]


@router.post("/{tournament_id}/session/start")
def start_game_session(
    tournament_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    t = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found")

    entry = db.query(TournamentEntry).filter(
        TournamentEntry.tournament_id == tournament_id,
        TournamentEntry.user_id == current_user.id,
    ).first()
    if not entry:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Join the tournament before playing")

    if t.ends_at <= now_utc():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tournament has ended")

    game = db.query(Game).filter(Game.id == t.game_id).first()
    token = create_session_token(current_user.id, tournament_id, game.slug)
    return {"session_token": token, "seed_game_slug": game.slug}


@router.post("/{tournament_id}/score", response_model=ScoreSubmitResponse)
def submit_score(
    tournament_id: uuid.UUID,
    body: ScoreSubmitRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    t = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found")

    entry = db.query(TournamentEntry).filter(
        TournamentEntry.tournament_id == tournament_id,
        TournamentEntry.user_id == current_user.id,
    ).first()
    if not entry:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Join the tournament before playing")

    game = db.query(Game).filter(Game.id == t.game_id).first()

    result = validate_and_consume_session(
        token_hex=body.session_token,
        expected_user_id=current_user.id,
        expected_tournament_id=tournament_id,
        game_slug=game.slug,
        claimed_score=body.score,
    )

    submission = GameScoreSubmission(
        tournament_entry_id=entry.id,
        user_id=current_user.id,
        submitted_score=body.score,
        is_valid=result.is_valid,
        rejection_reason=result.reason,
        session_token=body.session_token[:64],
        raw_session_data=body.session_data,
        client_ip=get_client_ip(request),
    )
    db.add(submission)

    if not result.is_valid:
        db.commit()
        return ScoreSubmitResponse(accepted=False, best_score=entry.best_score, rejection_reason=result.reason)

    entry.attempts_used += 1
    if body.score > entry.best_score:
        entry.best_score = body.score
        LeaderboardService.update_score(tournament_id, current_user.id, body.score)

    db.commit()
    return ScoreSubmitResponse(accepted=True, best_score=entry.best_score)
