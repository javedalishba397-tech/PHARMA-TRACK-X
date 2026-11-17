from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional
from backend.app.models.entities import AuditLog

def log_audit(
    db: Session,
    action: str,
    user_id: Optional[int] = None,
    entity: Optional[str] = None,
    entity_id: Optional[str] = None,
    result: str = "Success",
    ip_address: Optional[str] = None,
):
    """SEC-7: An audit log shall record user, action, date and time, and result. Audit entries not editable."""
    audit_entry = AuditLog(
        user_id=user_id,
        action=action,
        entity=entity,
        entity_id=str(entity_id) if entity_id is not None else None,
        result=result,
        ip_address=ip_address,
        logged_at=datetime.utcnow(),
    )
    db.add(audit_entry)
    db.commit()
