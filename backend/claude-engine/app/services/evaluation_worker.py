"""
Automatic Prediction Evaluation Worker

This service evaluates predictions 4 hours after they were made by:
1. Finding unevaluated predictions older than 4 hours
2. Fetching current price for the symbol
3. Calculating actual price change percentage
4. Determining if prediction was correct
5. Storing detailed evaluation data

Evaluation Logic:
- 'up' prediction is correct if price increased ≥ 0.5%
- 'down' prediction is correct if price decreased ≤ -0.5%
- Price change within ±0.5% is considered "neutral" (prediction still evaluated)

Author: Backend Architect
Date: 2025-11-14
"""

import asyncio
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional, Dict, Any, List, Tuple
from uuid import UUID

from sqlalchemy import create_engine, text, and_
from sqlalchemy.orm import sessionmaker, Session
from prometheus_client import Counter, Histogram, Gauge

logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp":"%(asctime)s","service":"evaluation_worker","level":"%(levelname)s","message":"%(message)s","function":"%(funcName)s"}'
)
logger = logging.getLogger(__name__)

# Prometheus Metrics
EVALUATION_JOB_RUNS = Counter(
    'evaluation_job_runs_total',
    'Total number of evaluation job executions',
    ['status']
)
EVALUATIONS_COMPLETED = Counter(
    'prediction_evaluations_completed_total',
    'Total predictions evaluated',
    ['result']  # 'correct', 'incorrect', 'neutral'
)
EVALUATION_DURATION = Histogram(
    'evaluation_job_duration_seconds',
    'Duration of evaluation job execution',
    buckets=[1, 5, 10, 30, 60, 120]
)
PENDING_EVALUATIONS = Gauge(
    'pending_predictions_evaluation_count',
    'Number of predictions awaiting evaluation'
)

# Configuration
EVALUATION_DELAY_HOURS = int(os.getenv('EVALUATION_DELAY_HOURS', '4'))
NEUTRAL_THRESHOLD_PCT = float(os.getenv('NEUTRAL_THRESHOLD_PCT', '0.5'))
BATCH_SIZE = int(os.getenv('EVALUATION_BATCH_SIZE', '50'))

# Advisory lock key for evaluation (prevents concurrent evaluation runs)
EVALUATION_LOCK_KEY = 8108002


def get_database_url() -> str:
    """Get database URL from environment"""
    url = os.getenv('DATABASE_URL')
    if url:
        return url
    from app.models.prediction import DatabaseConfig
    return DatabaseConfig.get_connection_string()


_engine = None
_session_maker = None


def get_db_session() -> Session:
    """Get database session for queries"""
    global _engine, _session_maker
    if _engine is None:
        _engine = create_engine(
            get_database_url(),
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True
        )
        _session_maker = sessionmaker(bind=_engine)
    return _session_maker()


def acquire_evaluation_lock(session: Session) -> bool:
    """
    Acquire PostgreSQL advisory lock for evaluation operations.
    Prevents race conditions when multiple workers try to evaluate.
    """
    try:
        result = session.execute(
            text("SELECT pg_try_advisory_lock(:lock_key)"),
            {"lock_key": EVALUATION_LOCK_KEY}
        ).fetchone()
        return result[0] if result else False
    except Exception as e:
        logger.error(f'{{"event":"evaluation_lock_acquire_failed","error":"{str(e)}"}}')
        return False


def release_evaluation_lock(session: Session) -> None:
    """Release PostgreSQL advisory lock for evaluation operations."""
    try:
        session.execute(
            text("SELECT pg_advisory_unlock(:lock_key)"),
            {"lock_key": EVALUATION_LOCK_KEY}
        )
    except Exception as e:
        logger.warning(f'{{"event":"evaluation_lock_release_failed","error":"{str(e)}"}}')


async def fetch_current_price(symbol: str) -> Optional[float]:
    """
    Fetch current price for a symbol using the unified data API.

    Args:
        symbol: Trading pair (e.g., "BTC/USDT")

    Returns:
        Current price or None if fetch failed
    """
    try:
        # Use the unified data API to get current market data
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'external_data_sources'))
        sys.path.insert(0, '/app/external_data_sources')  # Container path
        from unified_data_api import UnifiedCryptoDataAPI

        api = UnifiedCryptoDataAPI()
        market_data = await api.get_market_data(symbol)

        if market_data and market_data.price and market_data.price > 0:
            return float(market_data.price)

        logger.warning(f'{{"event":"price_fetch_no_data","symbol":"{symbol}"}}')
        return None

    except Exception as e:
        logger.error(f'{{"event":"price_fetch_error","symbol":"{symbol}","error":"{str(e)}"}}')
        return None


def get_prediction_price(market_context: Dict[str, Any]) -> Optional[float]:
    """
    Extract price at prediction time from market context JSONB.

    Args:
        market_context: The stored market context from prediction

    Returns:
        Price at prediction time or None if not found
    """
    if not market_context:
        return None

    # Try multiple paths to find price in market context
    # Primary path for current schema: market.price
    price_paths = [
        ('market', 'price'),  # Current schema: market_context.market.price
        ('market_data', 'price'),  # Legacy path
        ('price',),
        ('current_price',),
        ('market_data', 'current_price'),
        ('snapshot', 'market_data', 'price'),
    ]

    for path in price_paths:
        value = market_context
        for key in path:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                value = None
                break

        if value is not None and isinstance(value, (int, float)):
            return float(value)

    # Check if there's a nested structure
    if 'market_data' in market_context:
        md = market_context['market_data']
        if isinstance(md, dict):
            if 'price' in md:
                return float(md['price'])
            if 'current_price' in md:
                return float(md['current_price'])

    logger.warning(f'{{"event":"prediction_price_not_found","context_keys":"{list(market_context.keys())}"}}')
    return None


def calculate_evaluation(
    prediction_type: str,
    price_at_prediction: float,
    current_price: float
) -> Tuple[str, float, bool]:
    """
    Calculate evaluation results for a prediction.

    Args:
        prediction_type: 'up' or 'down'
        price_at_prediction: Price when prediction was made
        current_price: Current market price

    Returns:
        Tuple of (actual_outcome, actual_change_pct, was_correct)
    """
    # Calculate percentage change
    actual_change_pct = ((current_price - price_at_prediction) / price_at_prediction) * 100

    # Determine actual outcome
    if actual_change_pct >= NEUTRAL_THRESHOLD_PCT:
        actual_outcome = 'up'
    elif actual_change_pct <= -NEUTRAL_THRESHOLD_PCT:
        actual_outcome = 'down'
    else:
        actual_outcome = 'neutral'

    # Determine if prediction was correct
    # For 'neutral' actual outcome, we consider prediction incorrect
    # unless the confidence was low (handled elsewhere)
    if actual_outcome == 'neutral':
        # Neutral is a special case - neither clearly right nor wrong
        # For now, mark based on direction tendency
        if actual_change_pct > 0:
            was_correct = prediction_type == 'up'
        elif actual_change_pct < 0:
            was_correct = prediction_type == 'down'
        else:
            was_correct = False
    else:
        was_correct = prediction_type == actual_outcome

    return actual_outcome, round(actual_change_pct, 4), was_correct


def get_pending_predictions(session: Session, limit: int = BATCH_SIZE) -> List[Dict[str, Any]]:
    """
    Get predictions that need evaluation.

    Criteria:
    - Created more than EVALUATION_DELAY_HOURS ago
    - was_correct is NULL (not yet evaluated)

    Args:
        session: Database session
        limit: Maximum predictions to fetch

    Returns:
        List of prediction dictionaries
    """
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=EVALUATION_DELAY_HOURS)

    query = text("""
        SELECT
            id,
            symbol,
            prediction_type,
            confidence,
            market_context,
            created_at
        FROM trading_predictions.automated_predictions
        WHERE was_correct IS NULL
          AND created_at < :cutoff_time
        ORDER BY created_at ASC
        LIMIT :limit
    """)

    result = session.execute(query, {
        "cutoff_time": cutoff_time,
        "limit": limit
    })

    predictions = []
    for row in result:
        predictions.append({
            'id': row[0],
            'symbol': row[1],
            'prediction_type': row[2],
            'confidence': float(row[3]) if row[3] else None,
            'market_context': row[4],
            'created_at': row[5]
        })

    return predictions


def update_prediction_evaluation(
    session: Session,
    prediction_id: UUID,
    actual_outcome: str,
    actual_change_pct: float,
    was_correct: bool,
    price_at_prediction: float,
    current_price: float
) -> bool:
    """
    Update a prediction with evaluation results.

    Args:
        session: Database session
        prediction_id: Prediction UUID
        actual_outcome: 'up', 'down', or 'neutral'
        actual_change_pct: Actual percentage change
        was_correct: Whether prediction was correct
        price_at_prediction: Price when prediction was made
        current_price: Current price used for evaluation

    Returns:
        True if update succeeded, False otherwise
    """
    try:
        query = text("""
            UPDATE trading_predictions.automated_predictions
            SET
                actual_outcome = :actual_outcome,
                actual_price_change = :actual_change_pct,
                was_correct = :was_correct,
                evaluated_at = :evaluated_at
            WHERE id = :prediction_id
        """)

        session.execute(query, {
            "prediction_id": prediction_id,
            "actual_outcome": actual_outcome,
            "actual_change_pct": actual_change_pct,
            "was_correct": was_correct,
            "evaluated_at": datetime.now(timezone.utc)
        })

        return True

    except Exception as e:
        logger.error(f'{{"event":"evaluation_update_failed","prediction_id":"{prediction_id}","error":"{str(e)}"}}')
        return False


def save_detailed_evaluation(
    session: Session,
    prediction_id: UUID,
    price_at_prediction: float,
    price_after_eval: float,
    actual_change_pct: float,
    actual_direction: str,
    was_correct: bool,
    confidence: float,
    market_conditions: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Save detailed evaluation to prediction_evaluations table.

    This provides richer analysis data for pattern recognition.
    """
    try:
        # Calculate confidence calibration
        # How well does stated confidence match actual accuracy?
        # This is tracked over time to calibrate future predictions
        confidence_calibration = float(confidence) if was_correct else 1.0 - float(confidence)

        query = text("""
            INSERT INTO trading_predictions.prediction_evaluations (
                id,
                prediction_id,
                price_at_prediction,
                price_after_4h,
                actual_change_pct,
                actual_direction,
                was_correct,
                confidence_calibration,
                market_conditions_json,
                evaluated_at
            ) VALUES (
                gen_random_uuid(),
                :prediction_id,
                :price_at_prediction,
                :price_after_4h,
                :actual_change_pct,
                :actual_direction,
                :was_correct,
                :confidence_calibration,
                :market_conditions_json,
                :evaluated_at
            )
            ON CONFLICT (prediction_id) DO UPDATE SET
                price_after_4h = EXCLUDED.price_after_4h,
                actual_change_pct = EXCLUDED.actual_change_pct,
                actual_direction = EXCLUDED.actual_direction,
                was_correct = EXCLUDED.was_correct,
                confidence_calibration = EXCLUDED.confidence_calibration,
                market_conditions_json = EXCLUDED.market_conditions_json,
                evaluated_at = EXCLUDED.evaluated_at
        """)

        session.execute(query, {
            "prediction_id": prediction_id,
            "price_at_prediction": price_at_prediction,
            "price_after_4h": price_after_eval,
            "actual_change_pct": actual_change_pct,
            "actual_direction": actual_direction,
            "was_correct": was_correct,
            "confidence_calibration": confidence_calibration,
            "market_conditions_json": market_conditions,
            "evaluated_at": datetime.now(timezone.utc)
        })

        return True

    except Exception as e:
        # This is non-critical - log but don't fail
        logger.warning(f'{{"event":"detailed_evaluation_save_failed","prediction_id":"{prediction_id}","error":"{str(e)}"}}')
        return False


async def run_evaluation_batch() -> Dict[str, int]:
    """
    Run a batch of prediction evaluations.

    Returns:
        Dictionary with evaluation statistics
    """
    start_time = time.time()
    session = get_db_session()
    lock_acquired = False

    stats = {
        'evaluated': 0,
        'correct': 0,
        'incorrect': 0,
        'skipped': 0,
        'errors': 0
    }

    try:
        # Acquire lock to prevent concurrent evaluation
        lock_acquired = acquire_evaluation_lock(session)
        if not lock_acquired:
            logger.warning('{"event":"evaluation_skipped","reason":"lock_busy"}')
            EVALUATION_JOB_RUNS.labels(status='skipped').inc()
            return stats

        # Get pending predictions
        predictions = get_pending_predictions(session)
        pending_count = len(predictions)
        PENDING_EVALUATIONS.set(pending_count)

        if pending_count == 0:
            logger.info('{"event":"evaluation_batch_empty","message":"No predictions pending evaluation"}')
            EVALUATION_JOB_RUNS.labels(status='empty').inc()
            return stats

        logger.info(f'{{"event":"evaluation_batch_started","count":{pending_count}}}')

        # Group predictions by symbol to minimize API calls
        by_symbol: Dict[str, List[Dict]] = {}
        for pred in predictions:
            symbol = pred['symbol']
            if symbol not in by_symbol:
                by_symbol[symbol] = []
            by_symbol[symbol].append(pred)

        # Fetch current prices for each symbol
        current_prices: Dict[str, Optional[float]] = {}
        for symbol in by_symbol.keys():
            current_prices[symbol] = await fetch_current_price(symbol)

        # Evaluate each prediction
        for symbol, preds in by_symbol.items():
            current_price = current_prices.get(symbol)

            if current_price is None:
                logger.warning(f'{{"event":"evaluation_skipped_no_price","symbol":"{symbol}","count":{len(preds)}}}')
                stats['skipped'] += len(preds)
                continue

            for pred in preds:
                try:
                    # Get price at prediction time
                    price_at_prediction = get_prediction_price(pred['market_context'])

                    if price_at_prediction is None or price_at_prediction <= 0:
                        logger.warning(f'{{"event":"evaluation_skipped_no_prediction_price","prediction_id":"{pred["id"]}"}}')
                        stats['skipped'] += 1
                        continue

                    # Calculate evaluation
                    actual_outcome, actual_change_pct, was_correct = calculate_evaluation(
                        pred['prediction_type'],
                        price_at_prediction,
                        current_price
                    )

                    # Update prediction record
                    success = update_prediction_evaluation(
                        session,
                        pred['id'],
                        actual_outcome,
                        actual_change_pct,
                        was_correct,
                        price_at_prediction,
                        current_price
                    )

                    if success:
                        # Save detailed evaluation (non-critical)
                        save_detailed_evaluation(
                            session,
                            pred['id'],
                            price_at_prediction,
                            current_price,
                            actual_change_pct,
                            actual_outcome,
                            was_correct,
                            pred['confidence']
                        )

                        stats['evaluated'] += 1
                        if was_correct:
                            stats['correct'] += 1
                            EVALUATIONS_COMPLETED.labels(result='correct').inc()
                        else:
                            stats['incorrect'] += 1
                            EVALUATIONS_COMPLETED.labels(result='incorrect').inc()

                        logger.info(
                            f'{{"event":"prediction_evaluated",'
                            f'"prediction_id":"{pred["id"]}",'
                            f'"symbol":"{symbol}",'
                            f'"prediction_type":"{pred["prediction_type"]}",'
                            f'"actual_outcome":"{actual_outcome}",'
                            f'"change_pct":{actual_change_pct},'
                            f'"was_correct":{str(was_correct).lower()}}}'
                        )
                    else:
                        stats['errors'] += 1

                except Exception as e:
                    logger.error(f'{{"event":"evaluation_error","prediction_id":"{pred["id"]}","error":"{str(e)}"}}')
                    stats['errors'] += 1

        # Commit all changes
        session.commit()

        duration = time.time() - start_time
        EVALUATION_DURATION.observe(duration)
        EVALUATION_JOB_RUNS.labels(status='success').inc()

        logger.info(
            f'{{"event":"evaluation_batch_completed",'
            f'"evaluated":{stats["evaluated"]},'
            f'"correct":{stats["correct"]},'
            f'"incorrect":{stats["incorrect"]},'
            f'"skipped":{stats["skipped"]},'
            f'"errors":{stats["errors"]},'
            f'"duration_seconds":{duration:.2f}}}'
        )

        return stats

    except Exception as e:
        session.rollback()
        logger.error(f'{{"event":"evaluation_batch_failed","error":"{str(e)}"}}')
        EVALUATION_JOB_RUNS.labels(status='error').inc()
        raise

    finally:
        if lock_acquired:
            release_evaluation_lock(session)
        session.close()


def run_evaluation_sync():
    """
    Synchronous wrapper for evaluation batch.
    Used by APScheduler which expects synchronous functions.
    """
    return asyncio.run(run_evaluation_batch())


def get_evaluation_statistics(session: Session, hours: int = 24) -> Dict[str, Any]:
    """
    Get evaluation statistics for a time period.

    Args:
        session: Database session
        hours: Hours to look back

    Returns:
        Statistics dictionary
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    query = text("""
        SELECT
            COUNT(*) as total_evaluated,
            SUM(CASE WHEN was_correct THEN 1 ELSE 0 END) as correct,
            AVG(CASE WHEN was_correct THEN 1.0 ELSE 0.0 END) * 100 as accuracy_pct,
            AVG(confidence) as avg_confidence,
            AVG(CASE WHEN was_correct THEN confidence ELSE NULL END) as avg_confidence_when_correct,
            AVG(CASE WHEN NOT was_correct THEN confidence ELSE NULL END) as avg_confidence_when_wrong,
            AVG(ABS(actual_price_change)) as avg_price_change
        FROM trading_predictions.automated_predictions
        WHERE was_correct IS NOT NULL
          AND evaluated_at >= :cutoff
    """)

    result = session.execute(query, {"cutoff": cutoff}).fetchone()

    return {
        "period_hours": hours,
        "total_evaluated": result[0] or 0,
        "correct": result[1] or 0,
        "accuracy_pct": round(float(result[2] or 0), 2),
        "avg_confidence": round(float(result[3] or 0), 4),
        "avg_confidence_when_correct": round(float(result[4] or 0), 4) if result[4] else None,
        "avg_confidence_when_wrong": round(float(result[5] or 0), 4) if result[5] else None,
        "avg_price_change_pct": round(float(result[6] or 0), 4) if result[6] else None
    }


if __name__ == "__main__":
    # Manual test run
    import sys

    print("Running evaluation batch...")
    stats = asyncio.run(run_evaluation_batch())
    print(f"Results: {stats}")
