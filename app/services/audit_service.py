import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


class AuditService:

    @staticmethod
    def log(
        db: Session,
        action: str,
        actor_user_id: Optional[uuid.UUID] = None,
        actor_type: str = "user",
        target_type: Optional[str] = None,
        target_id: Optional[uuid.UUID] = None,
        metadata: Optional[dict] = None,
        ip_address: Optional[str] = None,
    ) -> AuditLog:
        entry = AuditLog(
            actor_user_id=actor_user_id,
            actor_type=actor_type,
            action=action,
            target_type=target_type,
            target_id=target_id,
            metadata_json=metadata,
            ip_address=ip_address,
        )
        db.add(entry)
        db.flush()
        return entry
