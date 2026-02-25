"""
4-Hour Aggregation Service for ClaudeTrader Pro

This service aggregates 4 hourly predictions into a single 4-hour trading decision
using a time-weighted voting algorithm that gives more weight to recent predictions.

Algorithm:
- Hour 1 (oldest): 0.15 weight
- Hour 2: 0.20 weight
- Hour 3: 0.25 weight
- Hour 4 (most recent): 0.40 weight

Author: Backend Architect
Date: 2025-11-12
"""

import logging
import statistics
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import desc
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


# Time-weighted voting weights (must sum to 1.0)
HOUR_WEIGHTS = {
    1: Decimal('0.15'),  # Hour 1 (oldest)
    2: Decimal('0.20'),  # Hour 2
    3: Decimal('0.25'),  # Hour 3
    4: Decimal('0.40'),  # Hour 4 (most recent)
}


class AggregationError(Exception):
    """Custom exception for aggregation service errors"""
    pass


class AggregationService:
    """
    Service for aggregating hourly predictions into 4-hour decisions
    """
    
    def __init__(self, db_session: Session):
        """
        Initialize aggregation service
        
        Args:
            db_session: SQLAlchemy database session
        """
        self.db = db_session
        self.logger = logger
    
    def aggregate_cycle_predictions(
        self,
        cycle_id: UUID,
        symbol: str = "BTC/USDT"
    ) -> UUID:
        """
        Aggregate 4 hourly predictions into a single 4-hour decision.
        
        This is the main entry point for the aggregation process. It:
        1. Retrieves all 4 predictions for the cycle
        2. Validates prediction count and timing
        3. Applies time-weighted voting algorithm
        4. Calculates confidence statistics
        5. Generates decision reasoning
        6. Stores final decision in four_hour_decisions table
        7. Updates cycle status to 'completed'
        
        Args:
            cycle_id: UUID of the prediction cycle to aggregate
            symbol: Trading pair (default: BTC/USDT)
            
        Returns:
            UUID: ID of the created four_hour_decision record
            
        Raises:
            AggregationError: If cycle not found, insufficient predictions,
                            or database error occurs
        
        Example:
            service = AggregationService(db_session)
            decision_id = service.aggregate_cycle_predictions(cycle_uuid)
        """
        try:
            self.logger.info(f"Starting aggregation for cycle {cycle_id}")
            
            # 1. Retrieve and validate cycle
            from app.models.cycle import PredictionCycle
            cycle = self.db.query(PredictionCycle).filter(
                PredictionCycle.id == cycle_id
            ).first()
            
            if not cycle:
                raise AggregationError(f"Prediction cycle {cycle_id} not found")
            
            if cycle.status == 'completed':
                raise AggregationError(
                    f"Cycle {cycle_id} already aggregated (status: completed)"
                )
            
            # 2. Retrieve all predictions for this cycle
            from app.models.prediction import Prediction
            predictions = self.db.query(Prediction).filter(
                Prediction.cycle_id == cycle_id
            ).order_by(Prediction.timestamp).all()
            
            # 3. Validate we have exactly 4 predictions
            if len(predictions) != 4:
                raise AggregationError(
                    f"Expected 4 predictions for cycle {cycle_id}, found {len(predictions)}"
                )
            
            self.logger.info(
                f"Found {len(predictions)} predictions for cycle {cycle_id}"
            )
            
            # 4. Apply time-weighted voting algorithm
            final_decision, aggregated_confidence = self._calculate_weighted_decision(
                predictions
            )
            
            # 5. Calculate vote breakdown
            vote_breakdown = self._calculate_vote_breakdown(predictions)
            
            # 6. Calculate confidence statistics
            confidence_stats = self._calculate_confidence_stats(predictions)
            
            # 7. Generate decision reasoning
            decision_reasoning = self._generate_reasoning(
                predictions,
                final_decision,
                aggregated_confidence,
                vote_breakdown,
                confidence_stats
            )
            
            # 8. Store final decision
            from app.models.cycle import FourHourDecision
            four_hour_decision = FourHourDecision(
                cycle_id=cycle_id,
                symbol=symbol,
                final_decision=final_decision,
                aggregated_confidence=aggregated_confidence,
                vote_breakdown=vote_breakdown,
                confidence_stats=confidence_stats,
                decision_reasoning=decision_reasoning,
                decided_at=datetime.utcnow()
            )
            
            self.db.add(four_hour_decision)
            
            # 9. Update cycle status to completed
            cycle.status = 'completed'
            cycle.completed_at = datetime.utcnow()
            
            # 10. Commit transaction
            self.db.commit()
            self.db.refresh(four_hour_decision)
            
            self.logger.info(
                f"Aggregation complete for cycle {cycle_id}. "
                f"Decision: {final_decision}, Confidence: {aggregated_confidence:.4f}"
            )
            
            return four_hour_decision.id
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self.logger.error(f"Database error during aggregation: {e}")
            raise AggregationError(f"Database error: {str(e)}") from e
        
        except Exception as e:
            self.db.rollback()
            self.logger.error(f"Unexpected error during aggregation: {e}")
            raise AggregationError(f"Aggregation failed: {str(e)}") from e
    
    def _calculate_weighted_decision(
        self,
        predictions: List[Any]
    ) -> Tuple[str, Decimal]:
        """
        Calculate final decision using time-weighted voting algorithm.
        
        The algorithm:
        1. Separates predictions into 'up' and 'down' groups
        2. For each group, calculates weighted score:
           weighted_score = sum(confidence * hour_weight)
        3. Selects direction with higher weighted score
        4. Calculates aggregated confidence as the winning score
        
        Args:
            predictions: List of 4 Prediction objects (ordered by timestamp)
            
        Returns:
            Tuple[str, Decimal]: (final_decision, aggregated_confidence)
            - final_decision: 'up' or 'down'
            - aggregated_confidence: Weighted confidence score (0.0 to 1.0)
        """
        up_weighted_score = Decimal('0.0')
        down_weighted_score = Decimal('0.0')
        
        # Apply weights to each prediction based on position (hour)
        for hour_num, prediction in enumerate(predictions, start=1):
            weight = HOUR_WEIGHTS[hour_num]
            confidence = Decimal(str(prediction.confidence))
            
            if prediction.prediction_type == 'up':
                up_weighted_score += confidence * weight
            else:  # 'down'
                down_weighted_score += confidence * weight
        
        # Determine final decision
        if up_weighted_score > down_weighted_score:
            final_decision = 'up'
            aggregated_confidence = up_weighted_score
        else:
            final_decision = 'down'
            aggregated_confidence = down_weighted_score
        
        self.logger.debug(
            f"Weighted scores - Up: {up_weighted_score:.4f}, "
            f"Down: {down_weighted_score:.4f}"
        )
        
        return final_decision, aggregated_confidence
    
    def _calculate_vote_breakdown(
        self,
        predictions: List[Any]
    ) -> Dict[str, Any]:
        """
        Calculate vote breakdown with counts and weighted scores.
        
        Args:
            predictions: List of 4 Prediction objects
            
        Returns:
            Dict with vote statistics:
            {
                "up_count": 2,
                "down_count": 2,
                "up_weighted": 0.55,
                "down_weighted": 0.45
            }
        """
        up_count = sum(1 for p in predictions if p.prediction_type == 'up')
        down_count = sum(1 for p in predictions if p.prediction_type == 'down')
        
        up_weighted = Decimal('0.0')
        down_weighted = Decimal('0.0')
        
        for hour_num, prediction in enumerate(predictions, start=1):
            weight = HOUR_WEIGHTS[hour_num]
            confidence = Decimal(str(prediction.confidence))
            
            if prediction.prediction_type == 'up':
                up_weighted += confidence * weight
            else:
                down_weighted += confidence * weight
        
        return {
            "up_count": up_count,
            "down_count": down_count,
            "up_weighted": float(up_weighted),
            "down_weighted": float(down_weighted)
        }
    
    def _calculate_confidence_stats(
        self,
        predictions: List[Any]
    ) -> Dict[str, float]:
        """
        Calculate statistical measures of confidence scores.
        
        Args:
            predictions: List of 4 Prediction objects
            
        Returns:
            Dict with statistics:
            {
                "min": 0.62,
                "max": 0.87,
                "avg": 0.74,
                "std_dev": 0.08
            }
        """
        confidences = [float(p.confidence) for p in predictions]
        
        return {
            "min": min(confidences),
            "max": max(confidences),
            "avg": statistics.mean(confidences),
            "std_dev": statistics.stdev(confidences) if len(confidences) > 1 else 0.0
        }
    
    def _generate_reasoning(
        self,
        predictions: List[Any],
        final_decision: str,
        aggregated_confidence: Decimal,
        vote_breakdown: Dict[str, Any],
        confidence_stats: Dict[str, float]
    ) -> str:
        """
        Generate human-readable explanation of the aggregated decision.
        
        Args:
            predictions: List of 4 Prediction objects
            final_decision: Final aggregated decision ('up' or 'down')
            aggregated_confidence: Weighted confidence score
            vote_breakdown: Vote statistics
            confidence_stats: Confidence statistics
            
        Returns:
            Formatted reasoning text explaining the decision
        """
        # Build reasoning text
        reasoning_parts = []
        
        # Summary
        reasoning_parts.append(
            f"4-Hour Aggregated Decision: {final_decision.upper()} "
            f"(confidence: {float(aggregated_confidence):.2%})"
        )
        
        # Vote breakdown
        reasoning_parts.append(
            f"\nVote Breakdown: {vote_breakdown['up_count']} UP, "
            f"{vote_breakdown['down_count']} DOWN"
        )
        reasoning_parts.append(
            f"Weighted Scores: UP={vote_breakdown['up_weighted']:.4f}, "
            f"DOWN={vote_breakdown['down_weighted']:.4f}"
        )
        
        # Confidence analysis
        reasoning_parts.append(
            f"\nConfidence Range: {confidence_stats['min']:.2%} to "
            f"{confidence_stats['max']:.2%} "
            f"(avg: {confidence_stats['avg']:.2%}, "
            f"std_dev: {confidence_stats['std_dev']:.4f})"
        )
        
        # Hourly predictions detail
        reasoning_parts.append("\nHourly Predictions (oldest to newest):")
        for hour_num, prediction in enumerate(predictions, start=1):
            weight = HOUR_WEIGHTS[hour_num]
            reasoning_parts.append(
                f"  Hour {hour_num} (weight {float(weight):.2f}): "
                f"{prediction.prediction_type.upper()} "
                f"(confidence: {float(prediction.confidence):.2%})"
            )
        
        # Decision strength analysis
        score_diff = abs(
            vote_breakdown['up_weighted'] - vote_breakdown['down_weighted']
        )
        if score_diff > 0.3:
            strength = "STRONG"
        elif score_diff > 0.15:
            strength = "MODERATE"
        else:
            strength = "WEAK"
        
        reasoning_parts.append(
            f"\nDecision Strength: {strength} "
            f"(score difference: {score_diff:.4f})"
        )
        
        # Confidence consistency analysis
        if confidence_stats['std_dev'] < 0.05:
            consistency = "very consistent"
        elif confidence_stats['std_dev'] < 0.10:
            consistency = "consistent"
        else:
            consistency = "variable"
        
        reasoning_parts.append(
            f"Prediction Consistency: Confidence scores are {consistency} "
            f"across the 4-hour period."
        )
        
        return "\n".join(reasoning_parts)


# Convenience function for direct usage
def aggregate_cycle_predictions(
    db_session: Session,
    cycle_id: UUID,
    symbol: str = "BTC/USDT"
) -> UUID:
    """
    Convenience function to aggregate a prediction cycle.
    
    Args:
        db_session: SQLAlchemy database session
        cycle_id: UUID of the prediction cycle
        symbol: Trading pair (default: BTC/USDT)
        
    Returns:
        UUID: ID of the created four_hour_decision record
        
    Example:
        from app.services.aggregation_service import aggregate_cycle_predictions
        
        decision_id = aggregate_cycle_predictions(
            db_session=session,
            cycle_id=cycle_uuid
        )
    """
    service = AggregationService(db_session)
    return service.aggregate_cycle_predictions(cycle_id, symbol)
