import uuid

import jwt as pyjwt
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.schemas.user import AuthResponse, UserLogin, UserRegister, UserResponse
from app.services.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.services.csrf import CSRF_COOKIE_NAME, new_csrf_token, validate_csrf
from app.services.dependencies import get_current_user
from app.services.rate_limit import enforce_rate_limit
from app.services.token_sessions import (
    get_active_refresh_session,
    purge_expired_refresh_sessions,
    revoke_refresh_session,
    revoke_user_refresh_sessions,
    store_refresh_session,
)

router = APIRouter()
_get_db = Depends(get_db)

REFRESH_COOKIE_NAME = "cortex_refresh_token"


def _set_auth_cookies(
    response: Response, access: str, refresh: str, csrf_token: str
) -> None:
    response.set_cookie(
        key=settings.cookie_name,
        value=access,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.jwt_access_token_expire_minutes * 60,
        domain=settings.cookie_domain or None,
    )
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.jwt_refresh_token_expire_days * 86400,
        domain=settings.cookie_domain or None,
    )
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.jwt_refresh_token_expire_days * 86400,
        domain=settings.cookie_domain or None,
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(
        key=settings.cookie_name, domain=settings.cookie_domain or None
    )
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME, domain=settings.cookie_domain or None
    )
    response.delete_cookie(
        key=CSRF_COOKIE_NAME, domain=settings.cookie_domain or None
    )


@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(
    body: UserRegister,
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    await enforce_rate_limit(
        request,
        "auth:register",
        settings.auth_rate_limit_attempts,
        settings.auth_rate_limit_window_seconds,
        actor=body.email.lower(),
    )
    email = body.email.lower()
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(email=email, hashed_password=hash_password(body.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return AuthResponse(
        user=UserResponse.model_validate(user),
        message="Registration successful. Your account is pending admin approval.",
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    body: UserLogin,
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    await enforce_rate_limit(
        request,
        "auth:login",
        settings.auth_rate_limit_attempts,
        settings.auth_rate_limit_window_seconds,
        actor=body.email.lower(),
    )
    email = body.email.lower()
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=401, detail="Invalid email or password"
        )
    if not user.is_active:
        raise HTTPException(
            status_code=403, detail="Account is deactivated"
        )
    if not user.whitelisted:
        raise HTTPException(
            status_code=403, detail="Account is pending approval"
        )

    access = create_access_token(str(user.id), user.email)
    refresh, refresh_expires_at = create_refresh_token(str(user.id))
    await revoke_user_refresh_sessions(db, user.id)
    await store_refresh_session(
        db,
        user_id=user.id,
        token=refresh,
        expires_at=refresh_expires_at,
    )
    await purge_expired_refresh_sessions(db)
    await db.commit()

    _set_auth_cookies(response, access, refresh, new_csrf_token())
    return AuthResponse(
        user=UserResponse.model_validate(user),
        message="Login successful",
    )


@router.post("/logout", status_code=204)
async def logout(
    response: Response,
    refresh_token: str | None = Cookie(None, alias=REFRESH_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(validate_csrf),  # noqa: B008
):
    if refresh_token:
        await revoke_refresh_session(db, refresh_token)
        await db.commit()
    _clear_auth_cookies(response)


@router.post("/refresh", response_model=AuthResponse)
async def refresh(
    response: Response,
    request: Request,
    refresh_token: str = Cookie(None, alias=REFRESH_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(validate_csrf),  # noqa: B008
):
    await enforce_rate_limit(
        request,
        "auth:refresh",
        settings.auth_rate_limit_attempts,
        settings.auth_rate_limit_window_seconds,
    )
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token")
    try:
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError("wrong type")
        user_id = payload["sub"]
    except (pyjwt.PyJWTError, ValueError, KeyError) as err:
        raise HTTPException(
            status_code=401, detail="Invalid or expired refresh token"
        ) from err

    session = await get_active_refresh_session(db, refresh_token)
    if not session:
        raise HTTPException(
            status_code=401, detail="Refresh session is invalid or expired"
        )

    result = await db.execute(
        select(User).where(User.id == uuid.UUID(user_id))
    )
    user = result.scalar_one_or_none()
    if not user or not user.is_active or not user.whitelisted:
        raise HTTPException(
            status_code=401, detail="User not found or inactive"
        )

    access = create_access_token(str(user.id), user.email)
    new_refresh, refresh_expires_at = create_refresh_token(str(user.id))
    await revoke_refresh_session(db, refresh_token)
    await store_refresh_session(
        db,
        user_id=user.id,
        token=new_refresh,
        expires_at=refresh_expires_at,
    )
    await purge_expired_refresh_sessions(db)
    await db.commit()

    _set_auth_cookies(response, access, new_refresh, new_csrf_token())
    return AuthResponse(
        user=UserResponse.model_validate(user),
        message="Session refreshed",
    )


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):  # noqa: B008
    return UserResponse.model_validate(user)
