from datetime import UTC, datetime
from hashlib import sha256

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.refresh_token_session import RefreshTokenSession


def hash_refresh_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


async def store_refresh_session(
    db: AsyncSession,
    *,
    user_id,
    token: str,
    expires_at: datetime,
) -> RefreshTokenSession:
    session = RefreshTokenSession(
        user_id=user_id,
        token_hash=hash_refresh_token(token),
        expires_at=expires_at.replace(tzinfo=None),
    )
    db.add(session)
    await db.flush()
    return session


async def get_active_refresh_session(
    db: AsyncSession,
    token: str,
) -> RefreshTokenSession | None:
    result = await db.execute(
        select(RefreshTokenSession).where(
            RefreshTokenSession.token_hash == hash_refresh_token(token),
            RefreshTokenSession.revoked_at.is_(None),
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        return None
    if session.expires_at <= datetime.now(UTC).replace(tzinfo=None):
        return None
    return session


async def revoke_refresh_session(
    db: AsyncSession,
    token: str,
) -> None:
    session = await get_active_refresh_session(db, token)
    if session and session.revoked_at is None:
        session.revoked_at = datetime.now(UTC).replace(tzinfo=None)


async def revoke_user_refresh_sessions(db: AsyncSession, user_id) -> None:
    result = await db.execute(
        select(RefreshTokenSession).where(
            RefreshTokenSession.user_id == user_id,
            RefreshTokenSession.revoked_at.is_(None),
        )
    )
    now = datetime.now(UTC).replace(tzinfo=None)
    for session in result.scalars().all():
        session.revoked_at = now


async def purge_expired_refresh_sessions(db: AsyncSession) -> None:
    await db.execute(
        delete(RefreshTokenSession).where(
            RefreshTokenSession.expires_at < datetime.now(UTC).replace(tzinfo=None)
        )
    )
