"""Audit log repository."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


class AuditRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def log(
        self,
        action: str,
        user_id: uuid.UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        metadata: dict | None = None,
        details: str | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            user_id=user_id,
            action=action,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata_json=metadata,
            details=details,
        )
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def list_by_user(
        self, user_id: uuid.UUID, limit: int = 50
    ) -> list[AuditLog]:
        result = await self.session.execute(
            select(AuditLog)
            .where(AuditLog.user_id == user_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_by_action(
        self, action: str, limit: int = 100
    ) -> list[AuditLog]:
        result = await self.session.execute(
            select(AuditLog)
            .where(AuditLog.action == action)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
