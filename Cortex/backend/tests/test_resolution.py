import uuid

import pytest

from app.models.event import Event
from app.models.prediction import Prediction
from app.services.resolution import (
    _calculate_brier_scores,
    _determine_winner,
    resolve_events,
)


class TestDetermineWinner:
    def test_clear_winner(self):
        assert _determine_winner(["Yes", "No"], [0.85, 0.15]) == "Yes"

    def test_close_prices(self):
        assert _determine_winner(["Yes", "No"], [0.51, 0.49]) == "Yes"

    def test_empty_outcomes(self):
        assert _determine_winner([], []) is None

    def test_mismatched_lengths(self):
        assert _determine_winner(["Yes", "No"], [0.8]) is None


class TestBrierScoreCalculation:
    async def test_yes_verdict_correct(self, db_session):
        """Verdict yes, outcome yes → low Brier Score."""
        event = Event(
            id=uuid.uuid4(),
            polymarket_market_id="test-yes-1",
            title="Test",
            category="test",
            outcomes=["Yes", "No"],
            outcome_prices={},
            active=False,
            closed=True,
            resolved_outcome="Yes",
        )
        db_session.add(event)
        await db_session.flush()

        pred = Prediction(
            event_id=event.id,
            model_name="test-model",
            probability=0.8,
            verdict="yes",
            reasoning="test",
            sources=[],
        )
        db_session.add(pred)
        await db_session.flush()

        scored = await _calculate_brier_scores(db_session, "test-yes-1", "Yes")
        assert scored == 1
        # predicted_prob = 0.8 (verdict yes), actual = 1.0
        # brier = (0.8 - 1.0)^2 = 0.04
        assert round(pred.brier_score, 4) == 0.04

    async def test_yes_verdict_wrong(self, db_session):
        """Verdict yes, outcome no → high Brier Score."""
        event = Event(
            id=uuid.uuid4(),
            polymarket_market_id="test-yes-2",
            title="Test",
            category="test",
            outcomes=["Yes", "No"],
            outcome_prices={},
            active=False,
            closed=True,
            resolved_outcome="No",
        )
        db_session.add(event)
        await db_session.flush()

        pred = Prediction(
            event_id=event.id,
            model_name="test-model",
            probability=0.9,
            verdict="yes",
            reasoning="test",
            sources=[],
        )
        db_session.add(pred)
        await db_session.flush()

        scored = await _calculate_brier_scores(db_session, "test-yes-2", "No")
        assert scored == 1
        # predicted_prob = 0.9 (verdict yes), actual = 0.0
        # brier = (0.9 - 0.0)^2 = 0.81
        assert round(pred.brier_score, 4) == 0.81

    async def test_no_verdict_correct(self, db_session):
        """Verdict no, outcome no → low Brier Score."""
        event = Event(
            id=uuid.uuid4(),
            polymarket_market_id="test-no-1",
            title="Test",
            category="test",
            outcomes=["Yes", "No"],
            outcome_prices={},
            active=False,
            closed=True,
            resolved_outcome="No",
        )
        db_session.add(event)
        await db_session.flush()

        pred = Prediction(
            event_id=event.id,
            model_name="test-model",
            probability=0.7,
            verdict="no",
            reasoning="test",
            sources=[],
        )
        db_session.add(pred)
        await db_session.flush()

        scored = await _calculate_brier_scores(db_session, "test-no-1", "No")
        assert scored == 1
        # predicted_prob = 1 - 0.7 = 0.3 (verdict no), actual = 0.0
        # brier = (0.3 - 0.0)^2 = 0.09
        assert round(pred.brier_score, 4) == 0.09

    async def test_uncertain_verdict(self, db_session):
        """Verdict uncertain → 0.5 probability."""
        event = Event(
            id=uuid.uuid4(),
            polymarket_market_id="test-unc-1",
            title="Test",
            category="test",
            outcomes=["Yes", "No"],
            outcome_prices={},
            active=False,
            closed=True,
            resolved_outcome="Yes",
        )
        db_session.add(event)
        await db_session.flush()

        pred = Prediction(
            event_id=event.id,
            model_name="test-model",
            probability=0.6,
            verdict="uncertain",
            reasoning="test",
            sources=[],
        )
        db_session.add(pred)
        await db_session.flush()

        scored = await _calculate_brier_scores(db_session, "test-unc-1", "Yes")
        assert scored == 1
        # predicted_prob = 0.5 (uncertain), actual = 0.0
        # brier = (0.5 - 0.0)^2 = 0.25
        assert round(pred.brier_score, 4) == 0.25

    async def test_skips_already_scored(self, db_session):
        """Predictions with existing brier_score are not re-scored."""
        event = Event(
            id=uuid.uuid4(),
            polymarket_market_id="test-skip-1",
            title="Test",
            category="test",
            outcomes=["Yes", "No"],
            outcome_prices={},
            active=False,
            closed=True,
            resolved_outcome="Yes",
        )
        db_session.add(event)
        await db_session.flush()

        pred = Prediction(
            event_id=event.id,
            model_name="test-model",
            probability=0.8,
            verdict="yes",
            reasoning="test",
            sources=[],
            brier_score=0.1,
        )
        db_session.add(pred)
        await db_session.flush()

        scored = await _calculate_brier_scores(db_session, "test-skip-1", "Yes")
        assert scored == 0
        assert pred.brier_score == 0.1


class TestResolveEvents:
    async def test_resolves_unresolved_event(self, db_session):
        """Event without resolved_outcome gets resolved."""
        event = Event(
            id=uuid.uuid4(),
            polymarket_market_id="resolve-1",
            title="Will X happen?",
            category="test",
            outcomes=["Yes", "No"],
            outcome_prices={"Yes": 0.3, "No": 0.7},
            active=True,
            closed=False,
        )
        db_session.add(event)
        await db_session.flush()

        mock_market = type(
            "MockMarket",
            (),
            {
                "id": "resolve-1",
                "question": "Will X happen?",
                "outcomes": ["Yes", "No"],
                "outcome_prices": [0.1, 0.9],
                "closed": True,
            },
        )()

        async def fake_fetch(_self):
            return [mock_market]

        mock_client = type("MockClient", (), {
            "fetch_resolved_markets": fake_fetch,
        })

        resolved = await resolve_events(mock_client(), db_session)
        assert resolved == 1

        from sqlalchemy import select

        result = await db_session.execute(
            select(Event).where(Event.polymarket_market_id == "resolve-1")
        )
        updated = result.scalar_one()
        assert updated.resolved_outcome == "No"
        assert updated.closed is True
        assert updated.active is False

    async def test_skips_already_resolved(self, db_session):
        """Event with existing resolved_outcome is not re-resolved."""
        event = Event(
            id=uuid.uuid4(),
            polymarket_market_id="resolve-2",
            title="Already resolved",
            category="test",
            outcomes=["Yes", "No"],
            outcome_prices={},
            active=False,
            closed=True,
            resolved_outcome="Yes",
        )
        db_session.add(event)
        await db_session.flush()

        mock_market = type(
            "MockMarket",
            (),
            {
                "id": "resolve-2",
                "question": "Already resolved",
                "outcomes": ["Yes", "No"],
                "outcome_prices": [0.1, 0.9],
                "closed": True,
            },
        )()

        async def fake_fetch(_self):
            return [mock_market]

        mock_client = type("MockClient", (), {
            "fetch_resolved_markets": fake_fetch,
        })

        resolved = await resolve_events(mock_client(), db_session)
        assert resolved == 0
