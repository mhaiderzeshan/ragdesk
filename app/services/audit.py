import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog

async def log_action(
    db: AsyncSession,
    org_id: uuid.UUID,
    user_id: Optional[uuid.UUID],
    action: str,
    resource: str,
    metadata: dict = None,
):
    """
    Log an action to the audit_logs table.
    """
    log_entry = AuditLog(
        org_id=org_id,
        user_id=user_id,
        action=action,
        resource=resource,
        metadata_jsonb=metadata or {},
    )
    db.add(log_entry)
    await db.commit()
