from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prediction import Prediction


async def get_user_today_forecast_count(
    db: AsyncSession, user_id
) -> int:
    # 1. Берем текущее время в UTC
    now = datetime.now(timezone.utc)
    
    # 2. Создаем начало дня (00:00:00)
    # .replace(tzinfo=None) — КРИТИЧЕСКИ ВАЖНО: это делает дату "naive",
    # чтобы PostgreSQL не ругался на несовпадение типов (DataError)
    today_start = datetime(now.year, now.month, now.day).replace(tzinfo=None)
    tomorrow_start = today_start + timedelta(days=1)
    
    result = await db.execute(
        select(func.count(Prediction.id)).where(
            Prediction.user_id == user_id,
            Prediction.created_at >= today_start,
            Prediction.created_at < tomorrow_start,
        )
    )
    # Используем .scalar(), так как count всегда возвращает одно число
    return result.scalar() or 0


async def check_forecast_quota(
    db: AsyncSession, user, daily_limit: int
) -> None:
    # Премиум-пользователи не имеют лимитов
    if hasattr(user, "plan") and user.plan == "premium":
        return
        
    count = await get_user_today_forecast_count(db, user.id)
    
    if count >= daily_limit:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Daily forecast limit reached ({daily_limit}/{daily_limit}). "
                "Upgrade to premium for unlimited forecasts."
            ),
        )
    