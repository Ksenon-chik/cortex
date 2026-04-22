import logging
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event
from app.models.prediction import Prediction
from app.services.polymarket import PolymarketClient

logger = logging.getLogger("cortex.resolution")


async def resolve_events(poly_client: PolymarketClient, session: AsyncSession) -> int:
    """Fetch resolved markets from Polymarket and update local events.

    For each resolved market that hasn't been resolved locally:
    1. Update event.closed = True and event.resolved_outcome
    2. Calculate Brier Score for all predictions on that event

    Returns the number of events resolved.
    """
    logger.info("Fetching resolved markets from Polymarket...")
    resolved_markets = await poly_client.fetch_resolved_markets()

    if not resolved_markets:
        logger.info("No resolved markets found")
        return 0

    # Get market IDs we already resolved
    result = await session.execute(
        select(Event.polymarket_market_id).where(Event.resolved_outcome.isnot(None))
    )
    already_resolved = set(result.scalars().all())

    resolved_count = 0
    for market in resolved_markets:
        if market.id in already_resolved:
            continue
        if not market.closed:
            continue

        # Determine the winning outcome from outcomePrices
        # The outcome with price closest to 1.0 is the winner
        winning_outcome = _determine_winner(market.outcomes, market.outcome_prices)
        if not winning_outcome:
            logger.warning(
                "Could not determine winner for market %s (%s)",
                market.id,
                market.question,
            )
            continue

        updated = await resolve_event_by_market_id(
            session=session,
            market_id=market.id,
            winning_outcome=winning_outcome,
        )
        if updated:
            resolved_count += 1

    if resolved_count:
        await session.commit()

    logger.info("Resolved %d events", resolved_count)
    return resolved_count


def _determine_winner(outcomes: list[str], outcome_prices: list[float]) -> str | None:
    """Determine the winning outcome from prices.

    The outcome with the highest price (closest to 1.0) is the winner.
    """
    if not outcomes or not outcome_prices or len(outcomes) != len(outcome_prices):
        return None

    max_price = -1.0
    winner = None
    for outcome, price in zip(outcomes, outcome_prices):
        if price > max_price:
            max_price = price
            winner = outcome
    return winner


def determine_predicted_outcome(
    *,
    verdict: str,
    probability: float,
    outcomes: list[str],
) -> str | None:
    if not outcomes:
        return None

    normalized_verdict = (verdict or "").strip().lower()
    for outcome in outcomes:
        if normalized_verdict == outcome.strip().lower():
            return outcome

    if len(outcomes) == 2:
        return outcomes[0] if probability >= 0.5 else outcomes[1]

    return None


async def resolve_event_by_market_id(
    *,
    session: AsyncSession,
    market_id: str,
    winning_outcome: str,
) -> int:
    result = await session.execute(
        select(Event).where(Event.polymarket_market_id == market_id)
    )
    event = result.scalar_one_or_none()
    if not event:
        logger.warning("No local event found for market %s", market_id)
        return 0

    event.closed = True
    event.active = False
    event.resolved_outcome = winning_outcome
    event.updated_at = datetime.now(UTC).replace(tzinfo=None)
    return await _calculate_prediction_results(
        session=session,
        event=event,
        winning_outcome=winning_outcome,
    )


async def _calculate_prediction_results(
    *,
    session: AsyncSession,
    event: Event,
    winning_outcome: str,
) -> int:
    """Calculate statuses and Brier Score for all predictions on a resolved event.

    Returns the number of predictions updated.
    """
    result = await session.execute(
        select(Prediction).where(Prediction.event_id == event.id)
    )
    predictions = result.scalars().all()

    updated = 0
    for pred in predictions:
        predicted_outcome = pred.predicted_outcome or determine_predicted_outcome(
            verdict=pred.verdict,
            probability=pred.probability,
            outcomes=event.outcomes,
        )
        pred.predicted_outcome = predicted_outcome

        outcome_matches = (
            predicted_outcome is not None
            and predicted_outcome.lower() == winning_outcome.lower()
        )
        actual = 1.0 if outcome_matches else 0.0
        predicted_prob = 0.5 if pred.verdict.lower() == "uncertain" else pred.probability

        brier_score = (predicted_prob - actual) ** 2
        pred.brier_score = round(brier_score, 6)
        pred.result_status = "won" if outcome_matches else "lost"
        updated += 1

    logger.info("Updated %d predictions for event %s", updated, event.id)
    return updated
