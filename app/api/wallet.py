import uuid

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.models.wallet import Wallet, WalletTransaction
from app.schemas.wallet import DepositRequest, WithdrawRequest, WalletResponse, TransactionResponse
from app.services.wallet_service import WalletService, InsufficientBalanceError, DuplicateTransactionError
from app.services.audit_service import AuditService
from app.api.deps import get_current_user, get_client_ip

router = APIRouter(prefix="/api/wallet", tags=["wallet"])


@router.get("/me", response_model=WalletResponse)
def get_my_wallet(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    wallet = WalletService.get_or_create_wallet(db, current_user.id)
    db.commit()
    return WalletResponse.from_wallet(wallet)


@router.post("/deposit", response_model=WalletResponse)
def deposit(
    body: DepositRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Simulated payment gateway deposit. In production this endpoint would instead
    create a payment-gateway order and credit the wallet only after a verified
    webhook callback (e.g. Razorpay payment.captured), never on the client's say-so.
    """
    idempotency_key = f"deposit:{current_user.id}:{uuid.uuid4()}"
    try:
        tx = WalletService.deposit(db, current_user.id, body.amount_paise, idempotency_key)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except DuplicateTransactionError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    AuditService.log(
        db, action="wallet.deposit", actor_user_id=current_user.id, actor_type="user",
        target_type="wallet", target_id=tx.wallet_id,
        metadata={"amount_paise": body.amount_paise}, ip_address=get_client_ip(request),
    )
    db.commit()

    wallet = db.query(Wallet).filter(Wallet.user_id == current_user.id).first()
    return WalletResponse.from_wallet(wallet)


@router.post("/withdraw")
def withdraw(
    body: WithdrawRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    idempotency_key = f"withdraw:{current_user.id}:{uuid.uuid4()}"
    try:
        tx = WalletService.withdraw(db, current_user.id, body.amount_paise, idempotency_key)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except InsufficientBalanceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except DuplicateTransactionError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    AuditService.log(
        db, action="wallet.withdraw", actor_user_id=current_user.id, actor_type="user",
        target_type="wallet", target_id=tx.wallet_id,
        metadata={"amount_paise": body.amount_paise}, ip_address=get_client_ip(request),
    )
    db.commit()

    return {"message": "Withdrawal initiated. It will proceed within 2 working days."}


@router.get("/transactions", response_model=list[TransactionResponse])
def get_transactions(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    wallet = db.query(Wallet).filter(Wallet.user_id == current_user.id).first()
    if wallet is None:
        return []
    txs = (
        db.query(WalletTransaction)
        .filter(WalletTransaction.wallet_id == wallet.id)
        .order_by(WalletTransaction.created_at.desc())
        .limit(min(limit, 200))
        .all()
    )
    return txs


@router.get("/reconcile", response_model=dict)
def reconcile_my_wallet(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Lets a user verify their own balance matches the immutable ledger sum."""
    return WalletService.reconcile(db, current_user.id)
