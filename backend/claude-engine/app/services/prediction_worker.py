"""
Prediction Worker Service - Automated Prediction Generation

Generates automated predictions on an hourly schedule with 4-hour cycle management.
Each cycle consists of 4 hourly predictions that are later aggregated into a
4-hour decision.

Key Responsibilities:
- Manage 4-hour prediction cycles (get or create active cycle)
- Determine cycle hour (1-4) based on time since cycle start
- Generate predictions using existing prediction service
- Enforce UNIQUE constraint (one prediction per hour per symbol)
- Track costs and update cycle metadata
- Handle errors gracefully with logging

Author: Backend Architect
Date: 2025-11-12
Version: 1.0.0
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, Tuple
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import text, and_
from prometheus_client import Counter, Gauge, Histogram

from app.services.unified_data_client import UnifiedDataClient
from app.services.ai_provider_factory import get_ai_provider_factory, AIProviderFactory
from app.services.pattern_analyzer import get_pattern_context_for_prompt
from app.services.confidence_calibration import ConfidenceCalibrationService

logger = logging.getLogger(__name__)

# Singleton UnifiedDataClient to preserve MTF cache between requests
_unified_client_singleton: Optional[UnifiedDataClient] = None

def get_unified_client() -> UnifiedDataClient:
    """
    Get or create singleton UnifiedDataClient.

    Using a singleton ensures the MTF cache persists between prediction requests,
    reducing TAAPI API calls and avoiding rate limits.
    """
    global _unified_client_singleton
    if _unified_client_singleton is None:
        import os
        taapi_key = os.getenv('TAAPI_API_KEY')
        _unified_client_singleton = UnifiedDataClient(taapi_api_key=taapi_key)
        logger.info("Created singleton UnifiedDataClient (MTF cache will persist)")
    return _unified_client_singleton

# Prometheus Metrics
AUTOMATED_PREDICTIONS_GENERATED = Counter(
    'automated_predictions_generated_total',
    'Total automated predictions generated',
    ['symbol', 'strategy', 'cycle_hour', 'status']
)

AUTOMATED_PREDICTION_COST = Gauge(
    'automated_prediction_cost_usd',
    'Cost of last automated prediction in USD',
    ['symbol', 'strategy']
)

CYCLE_HOUR_DISTRIBUTION = Histogram(
    'automated_prediction_cycle_hour',
    'Distribution of predictions by cycle hour',
    buckets=[1, 2, 3, 4]
)

PREDICTION_GENERATION_TIME = Histogram(
    'automated_prediction_generation_seconds',
    'Time to generate automated prediction',
    ['symbol', 'strategy']
)


class PredictionWorker:
    """
    Worker service for generating automated predictions with cycle management
    """
    
    # Cycle configuration
    CYCLE_DURATION_HOURS = 4
    CYCLE_DURATION_SECONDS = CYCLE_DURATION_HOURS * 3600
    
    def __init__(
        self,
        db_session: Session,
        unified_client: Optional[UnifiedDataClient] = None,
        ai_provider_factory: Optional[AIProviderFactory] = None,
        ai_provider: Optional[str] = None
    ):
        """
        Initialize prediction worker

        Args:
            db_session: SQLAlchemy database session
            unified_client: Optional UnifiedDataClient instance (will create if None)
            ai_provider_factory: Optional AI provider factory (will use singleton if None)
            ai_provider: Optional AI provider to use ('claude' or 'gemini')
        """
        self.db = db_session
        self.unified_client = unified_client or get_unified_client()
        self.ai_factory = ai_provider_factory or get_ai_provider_factory()
        self.ai_provider = ai_provider  # None means use default from factory

        logger.info(f"PredictionWorker initialized (provider: {ai_provider or self.ai_factory.current_provider}, using singleton client)")
    
    def get_or_create_cycle(
        self,
        symbol: str = 'BTC/USDT'
    ) -> Tuple[UUID, int, datetime]:
        """
        Get active cycle or create new one if needed
        
        A cycle is a 4-hour window for predictions. If no active cycle exists
        or the current one is expired, create a new one.
        
        Args:
            symbol: Trading symbol (default: BTC/USDT)
            
        Returns:
            Tuple of (cycle_id, cycle_number, cycle_start)
            
        Raises:
            Exception if database operations fail
        """
        try:
            now = datetime.now(timezone.utc)
            
            # Query for active cycle for this symbol
            active_cycle_query = text("""
                SELECT id, cycle_number, cycle_start, cycle_end
                FROM trading_predictions.prediction_cycles
                WHERE symbol = :symbol
                  AND status = 'active'
                  AND cycle_end > :now
                ORDER BY cycle_start DESC
                LIMIT 1
            """)
            
            result = self.db.execute(
                active_cycle_query,
                {'symbol': symbol, 'now': now}
            ).fetchone()
            
            if result:
                cycle_id = result[0]
                cycle_number = result[1]
                cycle_start = result[2]
                
                logger.info(
                    f"Found active cycle: {cycle_id} "
                    f"(#{cycle_number}, started {cycle_start})"
                )
                
                return (cycle_id, cycle_number, cycle_start)
            
            # No active cycle found - create new one
            # Get the last cycle number for this symbol
            last_cycle_query = text("""
                SELECT COALESCE(MAX(cycle_number), 0) as last_number
                FROM trading_predictions.prediction_cycles
                WHERE symbol = :symbol
            """)
            
            last_number_result = self.db.execute(
                last_cycle_query,
                {'symbol': symbol}
            ).fetchone()
            
            last_cycle_number = last_number_result[0] if last_number_result else 0
            new_cycle_number = last_cycle_number + 1
            
            # Calculate cycle boundaries (align to 4-hour blocks: 00:00, 04:00, 08:00, etc.)
            cycle_start = self._calculate_cycle_start(now)
            cycle_end = cycle_start + timedelta(hours=self.CYCLE_DURATION_HOURS)
            
            # Create new cycle
            new_cycle_id = uuid4()
            insert_cycle_query = text("""
                INSERT INTO trading_predictions.prediction_cycles (
                    id, symbol, cycle_start, cycle_end, cycle_number, 
                    status, predictions_count, created_at, updated_at
                )
                VALUES (
                    :id, :symbol, :cycle_start, :cycle_end, :cycle_number,
                    'active', 0, :now, :now
                )
                RETURNING id, cycle_number, cycle_start
            """)
            
            result = self.db.execute(
                insert_cycle_query,
                {
                    'id': str(new_cycle_id),
                    'symbol': symbol,
                    'cycle_start': cycle_start,
                    'cycle_end': cycle_end,
                    'cycle_number': new_cycle_number,
                    'now': now
                }
            ).fetchone()
            
            self.db.commit()
            
            cycle_id = result[0]
            cycle_number = result[1]
            cycle_start = result[2]
            
            logger.info(
                f"Created new cycle: {cycle_id} "
                f"(#{cycle_number}, {cycle_start} to {cycle_end})"
            )
            
            return (cycle_id, cycle_number, cycle_start)
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error in get_or_create_cycle: {e}")
            raise Exception(f"Failed to get or create cycle: {str(e)}")
    
    def _calculate_cycle_start(self, now: datetime) -> datetime:
        """
        Calculate cycle start time aligned to 4-hour blocks
        
        Cycles start at: 00:00, 04:00, 08:00, 12:00, 16:00, 20:00 UTC
        
        Args:
            now: Current datetime
            
        Returns:
            Cycle start datetime (aligned to 4-hour block)
        """
        hour = now.hour
        aligned_hour = (hour // 4) * 4
        
        cycle_start = now.replace(
            hour=aligned_hour,
            minute=0,
            second=0,
            microsecond=0
        )
        
        return cycle_start
    
    def determine_cycle_hour(
        self,
        cycle_start: datetime,
        current_time: Optional[datetime] = None
    ) -> int:
        """
        Determine which hour (1-4) we're in within the cycle
        
        Args:
            cycle_start: Cycle start timestamp
            current_time: Current time (defaults to now)
            
        Returns:
            Cycle hour (1, 2, 3, or 4)
        """
        if current_time is None:
            current_time = datetime.now(timezone.utc)
        
        # Calculate elapsed time since cycle start
        elapsed_seconds = (current_time - cycle_start).total_seconds()
        
        # Convert to hour (1-4)
        elapsed_hours = elapsed_seconds / 3600
        cycle_hour = min(int(elapsed_hours) + 1, 4)  # Cap at 4
        
        logger.debug(
            f"Cycle hour calculation: "
            f"elapsed={elapsed_hours:.2f}h, hour={cycle_hour}"
        )
        
        return cycle_hour
    
    def check_prediction_exists(
        self,
        cycle_id: UUID,
        cycle_hour: int,
        symbol: str = 'BTC/USDT'
    ) -> bool:
        """
        Check if prediction already exists for this cycle hour
        
        Args:
            cycle_id: Prediction cycle ID
            cycle_hour: Hour within cycle (1-4)
            symbol: Trading symbol
            
        Returns:
            True if prediction exists, False otherwise
        """
        try:
            check_query = text("""
                SELECT 1
                FROM trading_predictions.automated_predictions
                WHERE symbol = :symbol
                  AND cycle_id = :cycle_id
                  AND cycle_hour = :cycle_hour
                LIMIT 1
            """)
            
            result = self.db.execute(
                check_query,
                {
                    'symbol': symbol,
                    'cycle_id': str(cycle_id),
                    'cycle_hour': cycle_hour
                }
            ).fetchone()
            
            exists = result is not None
            
            if exists:
                logger.info(
                    f"Prediction already exists: "
                    f"cycle={cycle_id}, hour={cycle_hour}"
                )
            
            return exists
            
        except SQLAlchemyError as e:
            logger.error(f"Error checking prediction existence: {e}")
            return False
    
    async def generate_automated_prediction(
        self,
        symbol: str = 'BTC/USDT',
        strategy: str = 'conservative',
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Generate automated prediction with cycle management
        
        Main workflow:
        1. Get or create active cycle
        2. Determine cycle hour (1-4)
        3. Check if prediction already exists (UNIQUE constraint)
        4. Fetch market data
        5. Call Claude API for prediction
        6. Store in automated_predictions table
        7. Update cycle metadata
        8. Track cost in daily_cost_summary
        
        Args:
            symbol: Trading symbol (default: BTC/USDT)
            strategy: Prediction strategy ('conservative' or 'aggressive')
            
        Returns:
            Dictionary with prediction_id, cost, and metadata
            
        Raises:
            Exception if any step fails
        """
        start_time = datetime.now(timezone.utc)
        
        try:
            logger.info(
                f"Starting automated prediction: "
                f"symbol={symbol}, strategy={strategy}"
            )
            
            # Step 1: Get or create cycle
            cycle_id, cycle_number, cycle_start = self.get_or_create_cycle(symbol)
            
            # Step 2: Determine cycle hour
            cycle_hour = self.determine_cycle_hour(cycle_start)
            CYCLE_HOUR_DISTRIBUTION.observe(cycle_hour)
            
            logger.info(
                f"Cycle context: id={cycle_id}, "
                f"number={cycle_number}, hour={cycle_hour}/4"
            )
            
            # Step 3: Check if prediction already exists (skip if force=True)
            if not force and self.check_prediction_exists(cycle_id, cycle_hour, symbol):
                logger.warning(
                    f"Prediction already exists for cycle {cycle_id} hour {cycle_hour}. "
                    f"Skipping generation."
                )
                AUTOMATED_PREDICTIONS_GENERATED.labels(
                    symbol=symbol,
                    strategy=strategy,
                    cycle_hour=cycle_hour,
                    status='duplicate'
                ).inc()

                return {
                    'status': 'duplicate',
                    'message': f'Prediction already exists for hour {cycle_hour}',
                    'cycle_id': str(cycle_id),
                    'cycle_hour': cycle_hour
                }

            if force:
                logger.info(f"Force mode: bypassing duplicate check for cycle {cycle_id} hour {cycle_hour}")
            
            # Step 4: Fetch market data
            try:
                market_snapshot = await self.unified_client.get_market_snapshot(symbol)
            except Exception as e:
                logger.error(f"Failed to fetch market data: {e}")
                self._record_cycle_error(cycle_id, f"Market data fetch failed: {str(e)}")
                AUTOMATED_PREDICTIONS_GENERATED.labels(
                    symbol=symbol,
                    strategy=strategy,
                    cycle_hour=cycle_hour,
                    status='market_data_error'
                ).inc()
                raise

            # Step 4b: Add historical pattern context
            try:
                pattern_context = get_pattern_context_for_prompt(
                    self.db,
                    market_snapshot,
                    days=30
                )
                market_snapshot['pattern_context'] = pattern_context
                logger.info(f"Added pattern context to market snapshot ({len(pattern_context)} chars)")
            except Exception as e:
                # Pattern context is optional - log but don't fail prediction
                logger.warning(f"Failed to add pattern context: {e}")
                market_snapshot['pattern_context'] = None

            # Step 4c: Add confidence calibration context
            try:
                calibration_service = ConfidenceCalibrationService(self.db)
                calibration_context = calibration_service.get_calibration_context_for_prompt(
                    symbol=symbol,
                    days=30
                )
                market_snapshot['calibration_context'] = calibration_context
                logger.info(f"Added calibration context to market snapshot ({len(calibration_context)} chars)")
            except Exception as e:
                # Calibration context is optional - log but don't fail prediction
                logger.warning(f"Failed to add calibration context: {e}")
                market_snapshot['calibration_context'] = None

            # Step 5: Generate prediction with AI provider (Gemini primary, Claude fallback)
            try:
                # Use fallback-enabled prediction generation
                # Primary: Gemini (fast, cheap), Fallback: Claude (reliable)
                prediction_result = await self.ai_factory.generate_prediction_with_fallback(
                    market_snapshot,
                    strategy=strategy,
                    primary_provider=self.ai_provider or "gemini",
                    fallback_provider="claude"
                )

                # Log which provider was used
                provider_used = prediction_result.get('ai_provider', 'unknown')
                fallback_used = prediction_result.get('fallback_used', False)
                if fallback_used:
                    primary_error = prediction_result.get('primary_error', 'unknown error')
                    logger.warning(
                        f"Used fallback provider ({provider_used}) due to primary failure: {primary_error}"
                    )
                else:
                    logger.info(f"Prediction generated successfully with primary provider: {provider_used}")

            except Exception as e:
                provider_name = self.ai_provider or self.ai_factory.current_provider
                logger.error(f"All AI providers failed: {e}")
                self._record_cycle_error(cycle_id, f"All AI providers failed: {str(e)}")
                AUTOMATED_PREDICTIONS_GENERATED.labels(
                    symbol=symbol,
                    strategy=strategy,
                    cycle_hour=cycle_hour,
                    status='ai_error'
                ).inc()
                raise
            
            # Step 6: Store in automated_predictions table
            # In force mode, delete existing prediction first
            if force:
                try:
                    delete_query = text("""
                        DELETE FROM trading_predictions.automated_predictions
                        WHERE symbol = :symbol AND cycle_id = :cycle_id AND cycle_hour = :cycle_hour
                    """)
                    self.db.execute(delete_query, {
                        'symbol': symbol,
                        'cycle_id': str(cycle_id),
                        'cycle_hour': cycle_hour
                    })
                    self.db.commit()
                    logger.info(f"Force mode: deleted existing prediction for cycle {cycle_id} hour {cycle_hour}")
                except Exception as e:
                    logger.warning(f"Force mode: no existing prediction to delete: {e}")
                    self.db.rollback()

            try:
                prediction_id = self._save_automated_prediction(
                    prediction_result,
                    cycle_id,
                    cycle_hour,
                    symbol,
                    strategy
                )
            except IntegrityError as e:
                # Handle race condition - another worker already created this prediction
                logger.warning(
                    f"Race condition detected: prediction already exists. {e}"
                )
                self.db.rollback()
                AUTOMATED_PREDICTIONS_GENERATED.labels(
                    symbol=symbol,
                    strategy=strategy,
                    cycle_hour=cycle_hour,
                    status='race_condition'
                ).inc()
                
                return {
                    'status': 'duplicate',
                    'message': 'Prediction created by another worker (race condition)',
                    'cycle_id': str(cycle_id),
                    'cycle_hour': cycle_hour
                }
            except Exception as e:
                logger.error(f"Failed to save prediction: {e}")
                self._record_cycle_error(cycle_id, f"Save failed: {str(e)}")
                AUTOMATED_PREDICTIONS_GENERATED.labels(
                    symbol=symbol,
                    strategy=strategy,
                    cycle_hour=cycle_hour,
                    status='save_error'
                ).inc()
                raise
            
            # Step 7: Update cycle metadata (predictions_count auto-increments via trigger)
            # No action needed - database trigger handles this
            
            # Step 8: Track metrics
            cost_usd = float(prediction_result['total_cost_usd'])
            AUTOMATED_PREDICTION_COST.labels(
                symbol=symbol,
                strategy=strategy
            ).set(cost_usd)
            
            elapsed_seconds = (datetime.now(timezone.utc) - start_time).total_seconds()
            PREDICTION_GENERATION_TIME.labels(
                symbol=symbol,
                strategy=strategy
            ).observe(elapsed_seconds)
            
            AUTOMATED_PREDICTIONS_GENERATED.labels(
                symbol=symbol,
                strategy=strategy,
                cycle_hour=cycle_hour,
                status='success'
            ).inc()
            
            logger.info(
                f"Automated prediction generated successfully: "
                f"id={prediction_id}, cycle={cycle_id}, hour={cycle_hour}/4, "
                f"type={prediction_result['prediction_type']}, "
                f"confidence={prediction_result['confidence']:.2f}, "
                f"cost=${cost_usd:.6f}, "
                f"time={elapsed_seconds:.2f}s"
            )
            
            return {
                'status': 'success',
                'prediction_id': str(prediction_id),
                'cycle_id': str(cycle_id),
                'cycle_number': cycle_number,
                'cycle_hour': cycle_hour,
                'prediction_type': prediction_result['prediction_type'],
                'confidence': prediction_result['confidence'],
                'cost_usd': cost_usd,
                'generation_time_seconds': elapsed_seconds,
                'claude_model': prediction_result['claude_model'],
                'prompt_version': prediction_result['prompt_version']
            }
            
        except Exception as e:
            logger.exception(f"Unexpected error in generate_automated_prediction: {e}")
            AUTOMATED_PREDICTIONS_GENERATED.labels(
                symbol=symbol,
                strategy=strategy,
                cycle_hour=0,
                status='unknown_error'
            ).inc()
            raise
    
    def _save_automated_prediction(
        self,
        prediction_result: Dict[str, Any],
        cycle_id: UUID,
        cycle_hour: int,
        symbol: str,
        strategy: str
    ) -> UUID:
        """
        Save automated prediction to database
        
        Args:
            prediction_result: Prediction result from ClaudeClient
            cycle_id: Prediction cycle ID
            cycle_hour: Hour within cycle (1-4)
            symbol: Trading symbol
            strategy: Prediction strategy
            
        Returns:
            Prediction ID (UUID)
            
        Raises:
            IntegrityError if duplicate (UNIQUE constraint violated)
            Exception for other database errors
        """
        try:
            prediction_id = uuid4()
            
            insert_query = text("""
                INSERT INTO trading_predictions.automated_predictions (
                    id, symbol, prediction_type, confidence, reasoning,
                    claude_model, prompt_version, strategy, market_context,
                    trend_analysis, indicator_alignment,
                    input_tokens, output_tokens, cached_tokens,
                    total_cost_usd, api_latency_ms,
                    cycle_id, cycle_hour,
                    created_at
                )
                VALUES (
                    :id, :symbol, :prediction_type, :confidence, :reasoning,
                    :claude_model, :prompt_version, :strategy, CAST(:market_context AS jsonb),
                    :trend_analysis, :indicator_alignment,
                    :input_tokens, :output_tokens, :cached_tokens,
                    :total_cost_usd, :api_latency_ms,
                    :cycle_id, :cycle_hour,
                    :created_at
                )
                RETURNING id
            """)
            
            result = self.db.execute(
                insert_query,
                {
                    'id': str(prediction_id),
                    'symbol': symbol,
                    'prediction_type': prediction_result['prediction_type'],
                    'confidence': Decimal(str(prediction_result['confidence'])),
                    'reasoning': prediction_result['reasoning'],
                    'claude_model': prediction_result['claude_model'],
                    'prompt_version': prediction_result['prompt_version'],
                    'strategy': strategy,
                    'market_context': json.dumps(prediction_result['market_context']),  # Proper JSON for JSONB cast
                    'trend_analysis': prediction_result.get('trend_analysis'),
                    'indicator_alignment': prediction_result.get('indicator_alignment'),
                    'input_tokens': prediction_result['input_tokens'],
                    'output_tokens': prediction_result['output_tokens'],
                    'cached_tokens': prediction_result['cached_tokens'],
                    'total_cost_usd': Decimal(str(prediction_result['total_cost_usd'])),
                    'api_latency_ms': prediction_result['api_latency_ms'],
                    'cycle_id': str(cycle_id),
                    'cycle_hour': cycle_hour,
                    'created_at': datetime.now(timezone.utc)
                }
            ).fetchone()
            
            self.db.commit()
            
            saved_id = result[0]
            
            logger.info(
                f"Saved automated prediction: {saved_id} "
                f"(cycle={cycle_id}, hour={cycle_hour})"
            )
            
            return saved_id
            
        except IntegrityError:
            # UNIQUE constraint violation - duplicate prediction
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error saving prediction: {e}")
            raise Exception(f"Failed to save prediction: {str(e)}")
    
    def _record_cycle_error(self, cycle_id: UUID, error_message: str):
        """
        Record error on prediction cycle
        
        Args:
            cycle_id: Cycle ID
            error_message: Error description
        """
        try:
            update_query = text("""
                UPDATE trading_predictions.prediction_cycles
                SET error_count = error_count + 1,
                    last_error = :error_message,
                    last_error_at = :now,
                    updated_at = :now
                WHERE id = :cycle_id
            """)
            
            self.db.execute(
                update_query,
                {
                    'cycle_id': str(cycle_id),
                    'error_message': error_message[:1000],  # Truncate if too long
                    'now': datetime.now(timezone.utc)
                }
            )
            
            self.db.commit()
            
            logger.info(f"Recorded error on cycle {cycle_id}: {error_message}")
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to record cycle error: {e}")


# Convenience function for standalone usage (async)
async def generate_prediction(
    db_session: Session,
    symbol: str = 'BTC/USDT',
    strategy: str = 'conservative',
    force: bool = False,
    ai_provider: Optional[str] = None
) -> Dict[str, Any]:
    """
    Async convenience function to generate automated prediction

    Args:
        db_session: SQLAlchemy database session
        symbol: Trading symbol
        strategy: Prediction strategy
        force: If True, bypass duplicate check (for manual triggers)
        ai_provider: AI provider to use ('claude' or 'gemini'), None for default

    Returns:
        Prediction result dictionary
    """
    worker = PredictionWorker(db_session, ai_provider=ai_provider)
    return await worker.generate_automated_prediction(symbol, strategy, force=force)


# Synchronous wrapper for scheduler service
def generate_automated_prediction(
    symbol: str = 'BTC/USDT',
    strategy: str = 'conservative',
    db_session: Optional[Session] = None,
    force: bool = False,
    ai_provider: Optional[str] = None
) -> Dict[str, Any]:
    """
    Synchronous wrapper function for the scheduler to generate predictions.

    Creates its own database session if none provided, runs the async worker
    method in an event loop, and returns the result.

    Args:
        symbol: Trading symbol (default: BTC/USDT)
        strategy: Prediction strategy (default: conservative)
        db_session: Optional SQLAlchemy session (creates one if not provided)
        force: If True, bypass duplicate check (for test mode)
        ai_provider: AI provider to use ('claude' or 'gemini'), None for default

    Returns:
        Prediction result dictionary
    """
    import asyncio
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    import os

    session_to_close = None

    try:
        # Create session if not provided
        if db_session is None:
            db_url = os.getenv('DATABASE_URL')
            if not db_url:
                from app.models.prediction import DatabaseConfig
                db_url = DatabaseConfig.get_connection_string()

            engine = create_engine(
                db_url,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True
            )
            SessionLocal = sessionmaker(bind=engine)
            db_session = SessionLocal()
            session_to_close = db_session

        # Create worker with session and AI provider
        worker = PredictionWorker(db_session, ai_provider=ai_provider)

        # Run async method in event loop
        # Check if there's already a running event loop
        try:
            loop = asyncio.get_running_loop()
            # If we're already in an async context, create a new loop
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    worker.generate_automated_prediction(symbol, strategy, force=force)
                )
                result = future.result(timeout=300)  # 5 minute timeout
        except RuntimeError:
            # No running loop, we can use asyncio.run directly
            result = asyncio.run(
                worker.generate_automated_prediction(symbol, strategy, force=force)
            )

        return result

    except Exception as e:
        logger.exception(f"Error in generate_automated_prediction: {e}")
        raise

    finally:
        # Only close session if we created it
        if session_to_close:
            session_to_close.close()


# Example usage
if __name__ == "__main__":
    import asyncio
    from app.models import init_database, get_db_session
    
    async def test_worker():
        """Test prediction worker"""
        
        # Initialize database
        engine = init_database()
        session = get_db_session(engine)
        
        try:
            # Create worker
            worker = PredictionWorker(session)
            
            # Generate prediction
            result = await worker.generate_automated_prediction(
                symbol='BTC/USDT',
                strategy='conservative'
            )
            
            print("\nPrediction Result:")
            print(f"Status: {result['status']}")
            
            if result['status'] == 'success':
                print(f"Prediction ID: {result['prediction_id']}")
                print(f"Cycle: #{result['cycle_number']} (hour {result['cycle_hour']}/4)")
                print(f"Type: {result['prediction_type']}")
                print(f"Confidence: {result['confidence']:.2%}")
                print(f"Cost: ${result['cost_usd']:.6f}")
                print(f"Time: {result['generation_time_seconds']:.2f}s")
            
        except Exception as e:
            print(f"Error: {e}")
        finally:
            session.close()
    
    # Run test
    asyncio.run(test_worker())
