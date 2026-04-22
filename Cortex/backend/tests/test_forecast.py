import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.schemas import PredictionOutput
from app.models.event import Event
from app.models.prediction import Prediction


@pytest.fixture
async def sample_event(db_session):
    """Insert a test event into the database."""
    event = Event(
        id=uuid.uuid4(),
        polymarket_market_id="test-market-001",
        title="Will AI pass the Turing Test by 2026?",
        description="A test event about AI capabilities",
        category="technology",
        outcomes=["Yes", "No"],
        outcome_prices={"Yes": 0.3, "No": 0.7},
        active=True,
        closed=False,
        end_date=None,
    )
    db_session.add(event)
    await db_session.flush()
    return event


@pytest.fixture
def mock_forecast_output():
    return PredictionOutput(
        model_name="google/gemini-2.0-flash-exp:free",
        probability=0.75,
        verdict="yes",
        reasoning="test",
        sources=[],
        confidence_score=0.8,
    )


@pytest.fixture
def mock_agent(mock_forecast_output):
    """Patch PredictionAgent to return a mock generate_forecast result."""
    mock_instance = MagicMock()
    mock_instance.generate_forecast = AsyncMock(return_value=mock_forecast_output)
    with patch("app.routers.forecasts.PredictionAgent", return_value=mock_instance) as mock_cls:
        yield mock_cls


class TestForecastEndpoint:
    async def test_generate_forecast_success(self, auth_client, db_session, sample_event, mock_agent):
        response = await auth_client.post(
            "/api/forecast",
            json={"event_id": str(sample_event.id), "model": "google/gemini-2.0-flash-exp:free"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["probability"] == 0.75
        assert data["model_name"] == "google/gemini-2.0-flash-exp:free"
        assert data["reasoning"] == "test"
        assert data["verdict"] == "yes"
        assert data["confidence_score"] == 0.8

    async def test_generate_forecast_event_not_found(self, auth_client, mock_agent):
        response = await auth_client.post(
            "/api/forecast",
            json={"event_id": str(uuid.uuid4()), "model": "google/gemini-2.0-flash-exp:free"},
        )
        assert response.status_code == 404

    async def test_generate_forecast_invalid_model(self, auth_client, db_session, sample_event, mock_agent):
        response = await auth_client.post(
            "/api/forecast",
            json={"event_id": str(sample_event.id), "model": "nonexistent-model:paid"},
        )
        assert response.status_code == 400
        assert "not available" in response.json()["detail"].lower()

    async def test_generate_forecast_invalid_event_id_format(self, auth_client, mock_agent):
        response = await auth_client.post(
            "/api/forecast",
            json={"event_id": "not-a-uuid", "model": "google/gemini-2.0-flash-exp:free"},
        )
        assert response.status_code == 422

    async def test_forecast_stored_in_database(self, auth_client, db_session, sample_event, mock_agent):
        response = await auth_client.post(
            "/api/forecast",
            json={"event_id": str(sample_event.id), "model": "google/gemini-2.0-flash-exp:free"},
        )
        assert response.status_code == 200

        from sqlalchemy import select

        result = await db_session.execute(
            select(Prediction).where(Prediction.event_id == sample_event.id)
        )
        predictions = result.scalars().all()
        assert len(predictions) >= 1
        pred = predictions[0]
        assert pred.probability == 0.75
        assert pred.model_name == "google/gemini-2.0-flash-exp:free"
        assert pred.reasoning == "test"
        assert pred.confidence_score == 0.8


class TestModelListing:
    async def test_get_available_models(self, client):
        response = await client.get("/api/forecast/models")
        assert response.status_code == 200
        data = response.json()
        assert "models" in data
        assert len(data["models"]) >= 1
        for model in data["models"]:
            assert "id" in model
            assert "name" in model
            assert "tier" in model
            assert model["tier"] == "free"
        assert any(":free" in m["id"] for m in data["models"])

    async def test_get_available_models_matches_config(self, client):
        from app.config import settings

        response = await client.get("/api/forecast/models")
        data = response.json()
        returned_ids = [m["id"] for m in data["models"]]
        assert len(returned_ids) == len(settings.available_models)
        for model_id in returned_ids:
            assert model_id in settings.available_models


class TestPredictionJournal:
    async def test_get_event_predictions_empty(self, client, db_session, sample_event):
        response = await client.get(f"/api/forecast/events/{sample_event.id}/predictions")
        assert response.status_code == 200
        assert response.json()["predictions"] == []

    async def test_get_event_predictions_with_data(self, client, db_session, sample_event):
        pred1 = Prediction(
            event_id=sample_event.id,
            model_name="google/gemini-2.0-flash-exp:free",
            probability=0.6,
            verdict="yes",
            reasoning="first prediction",
            sources=[],
        )
        pred2 = Prediction(
            event_id=sample_event.id,
            model_name="meta-llama/llama-3.1-8b-instruct:free",
            probability=0.8,
            verdict="yes",
            reasoning="second prediction",
            sources=[],
        )
        db_session.add(pred1)
        db_session.add(pred2)
        await db_session.commit()

        response = await client.get(f"/api/forecast/events/{sample_event.id}/predictions")
        assert response.status_code == 200
        data = response.json()
        assert len(data["predictions"]) == 2
        returned_models = [p["model_name"] for p in data["predictions"]]
        assert "google/gemini-2.0-flash-exp:free" in returned_models
        assert "meta-llama/llama-3.1-8b-instruct:free" in returned_models
        for entry in data["predictions"]:
            assert all(k in entry for k in ["id", "model_name", "probability", "verdict", "reasoning", "sources", "created_at"])

    async def test_get_event_predictions_not_found(self, client):
        response = await client.get(f"/api/forecast/events/{uuid.uuid4()}/predictions")
        assert response.status_code == 404

    async def test_get_event_predictions_invalid_uuid(self, client):
        response = await client.get("/api/forecast/events/not-a-uuid/predictions")
        assert response.status_code == 422


class TestLeaderboard:
    async def test_leaderboard_empty(self, client):
        response = await client.get("/api/forecast/leaderboard")
        assert response.status_code == 200
        data = response.json()
        assert data["models"] == []

    async def test_leaderboard_with_resolved_predictions(self, client, db_session, sample_event):
        pred1 = Prediction(
            event_id=sample_event.id,
            model_name="google/gemini-2.0-flash-exp:free",
            probability=0.8,
            verdict="yes",
            reasoning="test",
            sources=[],
            brier_score=0.04,
        )
        pred2 = Prediction(
            event_id=sample_event.id,
            model_name="google/gemini-2.0-flash-exp:free",
            probability=0.7,
            verdict="yes",
            reasoning="test",
            sources=[],
            brier_score=0.09,
        )
        pred3 = Prediction(
            event_id=sample_event.id,
            model_name="meta-llama/llama-3.1-8b-instruct:free",
            probability=0.6,
            verdict="no",
            reasoning="test",
            sources=[],
            brier_score=0.25,
        )
        db_session.add_all([pred1, pred2, pred3])
        await db_session.commit()

        response = await client.get("/api/forecast/leaderboard")
        assert response.status_code == 200
        data = response.json()
        assert len(data["models"]) == 2

        # Sorted by mean Brier Score ascending (lower is better)
        gemini = data["models"][0]
        llama = data["models"][1]

        assert gemini["model_name"] == "google/gemini-2.0-flash-exp:free"
        assert gemini["total_predictions"] == 2
        assert gemini["resolved_predictions"] == 2
        assert round(gemini["mean_brier_score"], 4) == 0.065  # (0.04 + 0.09) / 2

        assert llama["model_name"] == "meta-llama/llama-3.1-8b-instruct:free"
        assert llama["total_predictions"] == 1
        assert llama["resolved_predictions"] == 1
        assert llama["mean_brier_score"] == 0.25

    async def test_leaderboard_excludes_unresolved(self, client, db_session, sample_event):
        """Predictions without brier_score don't appear in leaderboard."""
        unresolved = Prediction(
            event_id=sample_event.id,
            model_name="google/gemini-2.0-flash-exp:free",
            probability=0.5,
            verdict="uncertain",
            reasoning="test",
            sources=[],
        )
        db_session.add(unresolved)
        await db_session.commit()

        response = await client.get("/api/forecast/leaderboard")
        assert response.status_code == 200
        data = response.json()
        assert data["models"] == []
