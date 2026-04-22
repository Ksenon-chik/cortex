import uuid

import pytest

from app.models.prediction import Prediction
from app.services.auth import hash_password


class TestRegistration:
    async def test_register_success(self, client):
        response = await client.post(
            "/api/auth/register",
            json={"email": "newuser@example.com", "password": "securepass123"},
        )
        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_register_duplicate_email(self, client, db_session, test_user):
        response = await client.post(
            "/api/auth/register",
            json={"email": "test@example.com", "password": "anotherpass123"},
        )
        assert response.status_code == 409

    async def test_register_weak_password(self, client):
        response = await client.post(
            "/api/auth/register",
            json={"email": "weak@example.com", "password": "short"},
        )
        assert response.status_code == 422

    async def test_register_invalid_email(self, client):
        response = await client.post(
            "/api/auth/register",
            json={"email": "not-an-email", "password": "securepass123"},
        )
        assert response.status_code == 422

    async def test_password_hashed_in_db(self, client, db_session):
        await client.post(
            "/api/auth/register",
            json={"email": "hashcheck@example.com", "password": "securepass123"},
        )
        from sqlalchemy import select
        from app.models.user import User

        result = await db_session.execute(
            select(User).where(User.email == "hashcheck@example.com")
        )
        user = result.scalar_one()
        assert user.hashed_password != "securepass123"
        assert user.hashed_password.startswith("$2")  # bcrypt prefix


class TestLogin:
    async def test_login_success(self, client, db_session, test_user):
        response = await client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "testpassword"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    async def test_login_wrong_password(self, client, db_session, test_user):
        response = await client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "wrongpassword"},
        )
        assert response.status_code == 401

    async def test_login_nonexistent_user(self, client):
        response = await client.post(
            "/api/auth/login",
            json={"email": "nobody@example.com", "password": "testpassword"},
        )
        assert response.status_code == 401

    async def test_login_case_insensitive_email(self, client, db_session, test_user):
        response = await client.post(
            "/api/auth/login",
            json={"email": "TEST@EXAMPLE.COM", "password": "testpassword"},
        )
        assert response.status_code == 200


class TestLogout:
    async def test_logout_success(self, client, db_session, test_user):
        response = await client.post("/api/auth/logout")
        assert response.status_code == 204

    async def test_logout_idempotent(self, client):
        response = await client.post("/api/auth/logout")
        assert response.status_code == 204


class TestMe:
    async def test_me_authenticated(self, auth_client):
        response = await auth_client.get("/api/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["plan"] == "free"

    async def test_me_unauthenticated(self, client):
        response = await client.get("/api/auth/me")
        assert response.status_code == 401

    async def test_me_deactivated_user(self, client, db_session):
        from app.models.user import User
        from sqlalchemy import select

        user = User(
            id=uuid.uuid4(),
            email="deactivated@example.com",
            hashed_password=hash_password("testpassword"),
            is_active=False,
        )
        db_session.add(user)
        await db_session.flush()

        response = await client.post(
            "/api/auth/login",
            json={"email": "deactivated@example.com", "password": "testpassword"},
        )
        assert response.status_code == 403


class TestRefresh:
    async def test_refresh_valid_token(self, auth_client):
        response = await auth_client.post("/api/auth/refresh")
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    async def test_refresh_no_token(self, client):
        response = await client.post("/api/auth/refresh")
        assert response.status_code == 401


class TestAuthProtection:
    async def test_forecast_without_auth_returns_401(self, client, db_session):
        from app.models.event import Event

        event = Event(
            id=uuid.uuid4(),
            polymarket_market_id="auth-test-1",
            title="Auth test event",
            category="test",
            outcomes=["Yes", "No"],
            outcome_prices={"Yes": 0.5, "No": 0.5},
            active=True,
            closed=False,
        )
        db_session.add(event)
        await db_session.flush()

        response = await client.post(
            "/api/forecast",
            json={"event_id": str(event.id), "model": "google/gemini-2.0-flash-exp:free"},
        )
        assert response.status_code == 401

    async def test_public_endpoints_still_accessible(self, client):
        resp1 = await client.get("/api/forecast/models")
        assert resp1.status_code == 200

        resp2 = await client.get("/api/forecast/leaderboard")
        assert resp2.status_code == 200


class TestQuota:
    async def test_free_user_within_limit(self, auth_client, db_session, test_user):
        """Free user with 0 predictions today should be able to forecast."""
        from app.services.quota import check_forecast_quota

        await check_forecast_quota(db_session, test_user, 5)  # should not raise

    async def test_free_user_at_limit_returns_429(self, auth_client, db_session, test_user):
        """Free user at daily limit gets 429."""
        from app.models.event import Event
        from app.services.quota import check_forecast_quota

        event = Event(
            id=uuid.uuid4(),
            polymarket_market_id="quota-test-1",
            title="Quota test",
            category="test",
            outcomes=["Yes", "No"],
            outcome_prices={},
            active=False,
            closed=False,
        )
        db_session.add(event)
        await db_session.flush()

        # Create 5 predictions for today (at limit)
        for _ in range(5):
            pred = Prediction(
                event_id=event.id,
                model_name="test-model",
                probability=0.5,
                verdict="yes",
                reasoning="test",
                sources=[],
                user_id=test_user.id,
            )
            db_session.add(pred)
        await db_session.flush()

        with pytest.raises(Exception) as exc_info:
            await check_forecast_quota(db_session, test_user, 5)
        assert exc_info.value.status_code == 429

    async def test_premium_user_unlimited(self, auth_client, db_session, test_user):
        """Premium users bypass quota check."""
        from app.services.quota import check_forecast_quota

        test_user.plan = "premium"
        await db_session.flush()

        # Should not raise even with many predictions
        await check_forecast_quota(db_session, test_user, 5)
