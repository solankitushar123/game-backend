"""
AuditLog — immutable, append-only event log for every sensitive action
(wallet changes, KYC status changes, admin actions, tournament settlement, fraud flags).
No update/delete operations should ever be performed on this table at the application level.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, func, Uuid, JSON

from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)

    actor_user_id = Column(Uuid, nullable=True, index=True)  # null = system
    actor_type = Column(String(20), nullable=False, default="user")  # user | admin | system

    action = Column(String(60), nullable=False, index=True)
    # e.g. 'wallet.deposit', 'wallet.entry_fee_debit', 'tournament.settled',
    #      'kyc.status_changed', 'user.flagged', 'admin.tournament_created'

    target_type = Column(String(30), nullable=True)   # 'user' | 'tournament' | 'wallet' | ...
    target_id = Column(Uuid, nullable=True, index=True)

    metadata_json = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
