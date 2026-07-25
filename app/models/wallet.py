"""
Wallet + WalletTransaction models.

CRITICAL MONEY-HANDLING RULE: all amounts are stored as INTEGER PAISE (1 INR = 100 paise),
never as float/NUMERIC-with-decimals-in-app-code. This eliminates float rounding errors
entirely. Display layers convert paise -> rupees only at render time.

Every wallet mutation (deposit, debit, credit, refund) creates an immutable
WalletTransaction row. Balance is never just "updated" in isolation — it is always
the sum of a debit/credit ledger, recomputed and cross-checked, so the system is
audit-safe and tamper-evident.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, BigInteger, Text, func, Uuid
from sqlalchemy.orm import relationship

from app.core.database import Base


class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid, ForeignKey("users.id"), unique=True, nullable=False)

    # Denormalized cached balance for fast reads. Always reconcilable against
    # the transaction ledger (see WalletService.reconcile()).
    balance_paise = Column(BigInteger, default=0, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="wallet")
    transactions = relationship("WalletTransaction", back_populates="wallet", order_by="WalletTransaction.created_at.desc()")


class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    wallet_id = Column(Uuid, ForeignKey("wallets.id"), nullable=False, index=True)

    # DEPOSIT | ENTRY_FEE | PRIZE | REFUND | WITHDRAWAL | ADJUSTMENT
    tx_type = Column(String(20), nullable=False)

    # Positive = credit to user, Negative = debit from user. Always in paise.
    amount_paise = Column(BigInteger, nullable=False)
    balance_after_paise = Column(BigInteger, nullable=False)

    # Where the money for a PRIZE transaction came from — kept explicit
    # so platform entry fees are never conflated with sponsor-funded prizes.
    funding_source = Column(String(30), nullable=True)  # 'sponsor' | 'platform' | 'user' | null

    reference_type = Column(String(30), nullable=True)  # 'tournament_entry' | 'tournament_prize' | 'deposit' | etc
    reference_id = Column(Uuid, nullable=True)

    description = Column(Text, nullable=True)
    idempotency_key = Column(String(120), unique=True, nullable=True, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    wallet = relationship("Wallet", back_populates="transactions")
