import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.core.database import get_db
from app.models.user import User
from app.models.tournament import Tournament, TournamentEntry
from app.models.game import Game
from app.models.audit_log import AuditLog
from app.models.wallet import Wallet, WalletTransaction
from app.schemas.tournament import TournamentResponse, TournamentCreateRequest
from app.services.tournament_service import TournamentService
from app.services.audit_service import AuditService
from app.api.deps import get_current_admin, get_client_ip

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/overview")
def overview(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    total_users = db.query(func.count(User.id)).scalar()
    live_tournaments = db.query(func.count(Tournament.id)).filter(Tournament.status == "live").scalar()
    total_entries = db.query(func.count(TournamentEntry.id)).scalar()
    flagged_users = db.query(func.count(User.id)).filter(User.is_flagged == True).scalar()
    total_wallet_balance = db.query(func.coalesce(func.sum(Wallet.balance_paise), 0)).scalar()
    total_prizes_paid = db.query(
        func.coalesce(func.sum(WalletTransaction.amount_paise), 0)
    ).filter(WalletTransaction.tx_type == "PRIZE").scalar()

    return {
        "total_users": total_users,
        "live_tournaments": live_tournaments,
        "total_entries": total_entries,
        "flagged_users": flagged_users,
        "total_wallet_balance_paise": int(total_wallet_balance),
        "total_prizes_paid_paise": int(total_prizes_paid),
    }


@router.post("/tournaments", response_model=TournamentResponse, status_code=status.HTTP_201_CREATED)
def create_tournament(
    body: TournamentCreateRequest,
    request: Request,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    game = db.query(Game).filter(Game.id == body.game_id).first()
    if not game:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Game not found")

    if body.funding_source not in ("sponsor", "platform"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="funding_source must be 'sponsor' or 'platform'")
    if body.funding_source == "sponsor" and not body.sponsor_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="sponsor_name is required when funding_source is 'sponsor'")
    if body.ends_at <= body.starts_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ends_at must be after starts_at")

    payout_total = sum(t.amount_paise * (t.rank_to - t.rank_from + 1) for t in body.payout_structure)
    if payout_total > body.prize_pool_paise:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payout structure totals {payout_total} paise, exceeds declared prize pool {body.prize_pool_paise} paise",
        )

    t = Tournament(
        game_id=body.game_id,
        name=body.name,
        entry_fee_paise=body.entry_fee_paise,
        prize_pool_paise=body.prize_pool_paise,
        funding_source=body.funding_source,
        sponsor_name=body.sponsor_name,
        payout_structure=[p.model_dump() for p in body.payout_structure],
        max_paid_ranks=body.max_paid_ranks,
        starts_at=body.starts_at,
        ends_at=body.ends_at,
        status="scheduled",
    )
    db.add(t)
    db.flush()

    AuditService.log(
        db, action="admin.tournament_created", actor_user_id=admin.id, actor_type="admin",
        target_type="tournament", target_id=t.id,
        metadata={"name": t.name, "prize_pool_paise": t.prize_pool_paise, "funding_source": t.funding_source},
        ip_address=get_client_ip(request),
    )
    db.commit()
    db.refresh(t)

    resp = TournamentResponse.model_validate(t)
    resp.entry_count = 0
    return resp


@router.post("/tournaments/{tournament_id}/settle")
def settle_tournament(
    tournament_id: uuid.UUID,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    try:
        result = TournamentService.settle_tournament(db, tournament_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return result


@router.get("/users")
def list_users(
    limit: int = 50,
    flagged_only: bool = False,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    q = db.query(User)
    if flagged_only:
        q = q.filter(User.is_flagged == True)
    users = q.order_by(desc(User.created_at)).limit(min(limit, 200)).all()
    return [
        {
            "id": str(u.id),
            "username": u.username,
            "email": u.email,
            "kyc_status": u.kyc_status,
            "is_flagged": u.is_flagged,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat(),
        }
        for u in users
    ]


@router.post("/users/{user_id}/flag")
def flag_user(
    user_id: uuid.UUID,
    reason: str,
    request: Request,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.is_flagged = True
    AuditService.log(
        db, action="admin.user_flagged", actor_user_id=admin.id, actor_type="admin",
        target_type="user", target_id=user_id,
        metadata={"reason": reason}, ip_address=get_client_ip(request),
    )
    db.commit()
    return {"ok": True}


@router.get("/audit-log")
def get_audit_log(
    limit: int = 100,
    action: str | None = None,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    q = db.query(AuditLog)
    if action:
        q = q.filter(AuditLog.action == action)
    logs = q.order_by(desc(AuditLog.created_at)).limit(min(limit, 500)).all()
    return [
        {
            "id": str(l.id),
            "actor_user_id": str(l.actor_user_id) if l.actor_user_id else None,
            "actor_type": l.actor_type,
            "action": l.action,
            "target_type": l.target_type,
            "target_id": str(l.target_id) if l.target_id else None,
            "metadata": l.metadata_json,
            "created_at": l.created_at.isoformat(),
        }
        for l in logs
    ]
