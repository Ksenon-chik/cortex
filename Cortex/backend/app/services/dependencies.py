import uuid

import jwt as pyjwt
from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.services.auth import decode_token

_get_db = Depends(get_db)


async def get_current_user(
    access_token: str = Cookie(None, alias=settings.cookie_name),
    db: AsyncSession = _get_db,
) -> User:
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    try:
        payload = decode_token(access_token)
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=401, detail="Invalid token type"
            )
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=401, detail="Invalid token payload"
            )
    except pyjwt.PyJWTError as err:
        raise HTTPException(
            status_code=401, detail="Invalid or expired token"
        ) from err

    result = await db.execute(
        select(User).where(User.id == uuid.UUID(user_id))
    )
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=401, detail="User not found or inactive"
        )
    if not user.whitelisted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is pending approval",
        )
    return user


async def get_admin_user(
    user: User = Depends(get_current_user),  # noqa: B008
) -> User:
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return user


async def get_optional_user(
    access_token: str = Cookie(None, alias=settings.cookie_name),
    db: AsyncSession = _get_db,
) -> User | None:
    if not access_token:
        return None
    try:
        payload = decode_token(access_token)
        if payload.get("type") != "access":
            return None
        user_id = payload.get("sub")
        if not user_id:
            return None
    except pyjwt.PyJWTError:
        return None
    result = await db.execute(
        select(User).where(User.id == uuid.UUID(user_id))
    )
    user = result.scalar_one_or_none()
    if not user or not user.is_active or not user.whitelisted:
        return None
    return user
