"""
WalletService — all money movement goes through here. Never mutate
Wallet.balance_paise directly anywhere else in the codebase.

Design principles:
  1. Every mutation is wrapped in a DB transaction with the wallet row
     locked (SELECT ... FOR UPDATE) to prevent race conditions from
     concurrent requests (e.g. two tournament-entry clicks at once).
  2. Every mutation writes an immutable WalletTransaction ledger row.
  3. balance_paise is a cached projection of the ledger and can be
     reconciled/rebuilt from transactions at any time (see reconcile()).
  4. Idempotency keys prevent double-processing of the same logical
     operation (e.g. retried API calls).
"""
import uuid
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.wallet import Wallet, WalletTransaction
from app.core.config import settings


class InsufficientBalanceError(Exception):
    pass


class DuplicateTransactionError(Exception):
    pass


class WalletService:

    @staticmethod
    def get_or_create_wallet(db: Session, user_id: uuid.UUID) -> Wallet:
        wallet = db.query(Wallet).filter(Wallet.user_id == user_id).with_for_update().first()
        if wallet is None:
            wallet = Wallet(user_id=user_id, balance_paise=0)
            db.add(wallet)
            db.flush()
        return wallet

    @staticmethod
    def _apply_transaction(
        db: Session,
        wallet: Wallet,
        amount_paise: int,
        tx_type: str,
        funding_source: Optional[str] = None,
        reference_type: Optional[str] = None,
        reference_id: Optional[uuid.UUID] = None,
        description: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> WalletTransaction:
        if idempotency_key:
            existing = db.query(WalletTransaction).filter(
                WalletTransaction.idempotency_key == idempotency_key
            ).first()
            if existing:
                raise DuplicateTransactionError(f"Transaction {idempotency_key} already processed")

        new_balance = wallet.balance_paise + amount_paise
        if new_balance < 0:
            raise InsufficientBalanceError(
                f"Insufficient balance: have {wallet.balance_paise}, need {-amount_paise}"
            )

        wallet.balance_paise = new_balance

        tx = WalletTransaction(
            wallet_id=wallet.id,
            tx_type=tx_type,
            amount_paise=amount_paise,
            balance_after_paise=new_balance,
            funding_source=funding_source,
            reference_type=reference_type,
            reference_id=reference_id,
            description=description,
            idempotency_key=idempotency_key,
        )
        db.add(tx)
        db.flush()
        return tx

    @staticmethod
    def deposit(db: Session, user_id: uuid.UUID, amount_paise: int, idempotency_key: Optional[str] = None) -> WalletTransaction:
        if amount_paise < settings.MIN_DEPOSIT_PAISE:
            raise ValueError(f"Minimum deposit is {settings.MIN_DEPOSIT_PAISE} paise")
        if amount_paise > settings.MAX_DEPOSIT_PAISE:
            raise ValueError(f"Maximum single deposit is {settings.MAX_DEPOSIT_PAISE} paise")

        wallet = WalletService.get_or_create_wallet(db, user_id)
        return WalletService._apply_transaction(
            db, wallet, amount_paise,
            tx_type="DEPOSIT",
            funding_source="user",
            reference_type="deposit",
            description="Wallet top-up (simulated payment gateway)",
            idempotency_key=idempotency_key,
        )

    @staticmethod
    def withdraw(db: Session, user_id: uuid.UUID, amount_paise: int, idempotency_key: Optional[str] = None) -> WalletTransaction:
        if amount_paise < 100000:
            raise ValueError("Minimum withdrawal is 1000 rupees")
        
        wallet = WalletService.get_or_create_wallet(db, user_id)
        return WalletService._apply_transaction(
            db, wallet, -amount_paise,
            tx_type="WITHDRAWAL",
            funding_source=None,
            reference_type="withdrawal",
            description="Withdrawal request (processing in 2 working days)",
            idempotency_key=idempotency_key,
        )

    @staticmethod
    def debit_entry_fee(db: Session, user_id: uuid.UUID, amount_paise: int, tournament_id: uuid.UUID) -> WalletTransaction:
        if amount_paise <= 0:
            raise ValueError("Entry fee must be positive")
        wallet = WalletService.get_or_create_wallet(db, user_id)
        return WalletService._apply_transaction(
            db, wallet, -amount_paise,
            tx_type="ENTRY_FEE",
            funding_source=None,
            reference_type="tournament_entry",
            reference_id=tournament_id,
            description="Tournament entry fee (administration only — not pooled into prize)",
        )

    @staticmethod
    def credit_prize(
        db: Session,
        user_id: uuid.UUID,
        amount_paise: int,
        tournament_id: uuid.UUID,
        funding_source: str,
        idempotency_key: str,
    ) -> WalletTransaction:
        if amount_paise <= 0:
            raise ValueError("Prize amount must be positive")
        if funding_source not in ("sponsor", "platform"):
            raise ValueError("funding_source must be 'sponsor' or 'platform'")

        wallet = WalletService.get_or_create_wallet(db, user_id)
        return WalletService._apply_transaction(
            db, wallet, amount_paise,
            tx_type="PRIZE",
            funding_source=funding_source,
            reference_type="tournament_prize",
            reference_id=tournament_id,
            description=f"Tournament prize ({funding_source}-funded)",
            idempotency_key=idempotency_key,
        )

    @staticmethod
    def refund(db: Session, user_id: uuid.UUID, amount_paise: int, tournament_id: uuid.UUID, reason: str) -> WalletTransaction:
        wallet = WalletService.get_or_create_wallet(db, user_id)
        return WalletService._apply_transaction(
            db, wallet, amount_paise,
            tx_type="REFUND",
            funding_source=None,
            reference_type="tournament_entry",
            reference_id=tournament_id,
            description=f"Refund: {reason}",
        )

    @staticmethod
    def reconcile(db: Session, user_id: uuid.UUID) -> dict:
        """Recompute balance from the immutable ledger and compare to cached balance.
        Used by admin/ops tooling to detect drift/tampering."""
        wallet = db.query(Wallet).filter(Wallet.user_id == user_id).first()
        if not wallet:
            return {"ok": True, "message": "no wallet"}
        ledger_sum = sum(
            tx.amount_paise for tx in
            db.query(WalletTransaction).filter(WalletTransaction.wallet_id == wallet.id).all()
        )
        return {
            "ok": ledger_sum == wallet.balance_paise,
            "cached_balance_paise": wallet.balance_paise,
            "ledger_sum_paise": ledger_sum,
        }
