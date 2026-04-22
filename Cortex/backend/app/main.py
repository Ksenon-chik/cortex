import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine
from app.routers.admin import router as admin_router
from app.routers.auth import router as auth_router
from app.routers.events import router as events_router
from app.routers.forecasts import router as forecasts_router
from app.routers.user_api_keys import router as user_api_keys_router
from app.scheduler import create_scheduler, resolution_job
from app.services.polymarket import PolymarketClient

logger = logging.getLogger("cortex")


def create_app(testing: bool = False) -> FastAPI:
    """Create and configure the FastAPI application."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if testing:
            yield
            return

        logger.info("Cortex API starting")

        # Create Polymarket client
        poly_client = PolymarketClient(
            gamma_base_url=settings.polymarket_gamma_api_url,
            clob_base_url=settings.polymarket_clob_api_url,
        )
        app.state.poly_client = poly_client

        # Start scheduler with hourly resolution job (markets are added manually)
        scheduler = create_scheduler()
        scheduler.add_job(
            resolution_job,
            "interval",
            hours=1,
            id="resolve_events",
            replace_existing=True,
            kwargs={"poly_client": poly_client},
        )
        scheduler.start()
        app.state.scheduler = scheduler

        # Run initial resolution check in background (no auto market sync — manual only)
        async def _initial_bootstrap():
            logger.info("Running initial resolution check (background)...")
            try:
                await resolution_job(poly_client)
            except Exception:
                logger.exception("Initial resolution job failed — scheduler will retry in 1 hour")

        asyncio.create_task(_initial_bootstrap())

        yield

        # Shutdown
        logger.info("Shutting down scheduler...")
        scheduler.shutdown()
        await poly_client.aclose()
        logger.info("Cortex API shutting down")
        await engine.dispose()

    app = FastAPI(title="Cortex API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
    app.include_router(events_router, prefix="/api/events", tags=["events"])
    app.include_router(forecasts_router, prefix="/api/forecast", tags=["forecast"])
    app.include_router(admin_router, prefix="/api/admin", tags=["admin"])
    app.include_router(user_api_keys_router, prefix="/api/user", tags=["user"])

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response: Response = await call_next(request)
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; connect-src 'self'; img-src 'self' data: https:; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; script-src 'self' 'unsafe-inline'; "
            "frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
        )
        return response

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
