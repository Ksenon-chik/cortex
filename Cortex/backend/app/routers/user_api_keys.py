import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.user_api_key import UserApiKey
from app.schemas.user_api_key import UserApiKeyCreate, UserApiKeyResponse
from app.services.crypto import encrypt_api_key
from app.services.csrf import validate_csrf
from app.services.dependencies import get_current_user

router = APIRouter()

_VALID_PROVIDERS = {"openrouter", "google", "groq", "tavily", "deepseek", "mistral", "cerebras", "fireworks", "nvidia"}


@router.get("/api-keys", response_model=list[UserApiKeyResponse])
async def list_user_api_keys(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List current user's API keys (never returns actual key values)."""
    result = await db.execute(
        select(UserApiKey)
        .where(UserApiKey.user_id == user.id)
        .order_by(UserApiKey.created_at.desc())
    )
    keys = result.scalars().all()
    return [
        UserApiKeyResponse(
            id=str(k.id),
            provider=k.provider,
            is_active=k.is_active,
            created_at=str(k.created_at),
        )
        for k in keys
    ]


@router.post("/api-keys", response_model=UserApiKeyResponse)
async def create_user_api_key(
    body: UserApiKeyCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    _csrf: None = Depends(validate_csrf),  # noqa: B008
):
    """Add a new API key for the current user."""
    if body.provider not in _VALID_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown provider '{body.provider}'. Allowed: {', '.join(sorted(_VALID_PROVIDERS))}",
        )
    if not body.api_key.strip():
        raise HTTPException(status_code=400, detail="API key cannot be empty")

    # Check if user already has a key for this provider — replace it
    existing = await db.execute(
        select(UserApiKey).where(
            UserApiKey.user_id == user.id,
            UserApiKey.provider == body.provider,
        )
    )
    existing_key = existing.scalar_one_or_none()
    encrypted = encrypt_api_key(body.api_key.strip())
    if existing_key:
        existing_key.api_key = encrypted
        existing_key.is_active = True
        await db.commit()
        await db.refresh(existing_key)
        return UserApiKeyResponse(
            id=str(existing_key.id),
            provider=existing_key.provider,
            is_active=existing_key.is_active,
            created_at=str(existing_key.created_at),
        )

    new_key = UserApiKey(
        user_id=user.id,
        provider=body.provider,
        api_key=encrypted,
    )
    db.add(new_key)
    await db.commit()
    await db.refresh(new_key)
    return UserApiKeyResponse(
        id=str(new_key.id),
        provider=new_key.provider,
        is_active=new_key.is_active,
        created_at=str(new_key.created_at),
    )


@router.delete("/api-keys/{key_id}", response_model=UserApiKeyResponse)
async def delete_user_api_key(
    key_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    _csrf: None = Depends(validate_csrf),  # noqa: B008
):
    """Delete one of the current user's API keys."""
    result = await db.execute(
        select(UserApiKey).where(
            UserApiKey.id == key_id,
            UserApiKey.user_id == user.id,
        )
    )
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")

    await db.delete(key)
    await db.commit()
    return UserApiKeyResponse(
        id=str(key.id),
        provider=key.provider,
        is_active=key.is_active,
        created_at=str(key.created_at),
    )
