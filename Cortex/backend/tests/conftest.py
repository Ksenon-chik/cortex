import os

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import JSON
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Remove proxy env vars that httpx reads and can't handle
_PROXY_VARS = (
    "ALL_PROXY", "all_proxy", "HTTP_PROXY", "HTTPS_PROXY",
    "http_proxy", "https_proxy", "FTP_PROXY", "ftp_proxy",
    "NO_PROXY", "no_proxy",
)
for _v in _PROXY_VARS:
    os.environ.pop(_v, None)

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test_cortex.db"

# Patch postgresql JSONB -> generic JSON for SQLite compatibility
# MUST happen before any model imports
postgresql.JSONB = JSON

from app.database import Base, get_db
from app.models.user import User  # noqa: F401 — ensures users table is created
from app.services.auth import create_access_token, create_refresh_token, hash_password

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
test_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session", autouse=True)
async def setup_test_db():
    """Create test tables before tests, drop after."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client_and_session():
    """Test client with shared DB session for fixture visibility."""
    from app.main import create_app

    app = create_app()

    async with engine.connect() as conn:
        tx = await conn.begin()
        session = test_session(bind=conn)

        async def _get_test_db():
            yield session

        app.dependency_overrides[get_db] = _get_test_db

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac, session

        app.dependency_overrides.clear()
        await session.close()
        await tx.rollback()


@pytest.fixture
async def client(client_and_session):
    ac, _ = client_and_session
    return ac


@pytest.fixture
async def db_session(client_and_session):
    _, session = client_and_session
    return session


@pytest.fixture
async def test_user(db_session):
    """Create a test user and return it."""
    import uuid

    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        hashed_password=hash_password("testpassword"),
        plan="free",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def auth_client(client_and_session, test_user):
    """Test client with valid auth cookies."""
    ac, _ = client_and_session
    access = create_access_token(str(test_user.id), test_user.email)
    refresh = create_refresh_token(str(test_user.id))
    ac.cookies.set(name="cortex_access_token", value=access)
    ac.cookies.set(name="cortex_refresh_token", value=refresh)
    return ac
