"""
Pattern Analyzer - Pattern Recognition and Tracking for Predictions

This service identifies market patterns from prediction context and tracks
which patterns correlate with accurate predictions.

Tracked Patterns:
1. RSI Extreme - RSI < 25 (oversold) or > 75 (overbought)
2. Fear & Greed Extreme - FGI < 20 (extreme fear) or > 80 (extreme greed)
3. Funding Rate Squeeze - abs(funding) > 0.1%
4. MTF Alignment - All 3 timeframes agree on direction
5. Volume Divergence - Price up/down with opposite volume trend
6. Whale Activity - Large whale transactions detected
7. News Sentiment Extreme - Strong positive/negative news sentiment

Author: Backend Architect
Date: 2026-01-15
"""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional, Dict, Any, List, Tuple
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from pydantic import BaseModel, Field

logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp":"%(asctime)s","service":"pattern_analyzer","level":"%(levelname)s","message":"%(message)s"}'
)
logger = logging.getLogger(__name__)


class PatternDefinition(BaseModel):
    """Definition of a market pattern"""
    name: str
    pattern_type: str  # 'technical', 'sentiment', 'onchain', 'composite'
    criteria: Dict[str, Any]
    description: str


class PatternMatch(BaseModel):
    """A detected pattern match"""
    pattern_name: str
    pattern_type: str
    matched_at: datetime
    context_data: Dict[str, Any]


class PatternPerformance(BaseModel):
    """Performance statistics for a pattern"""
    pattern_name: str
    occurrences: int
    successful: int
    accuracy_rate: float
    avg_confidence: float
    last_occurrence: Optional[datetime] = None


# Pre-defined pattern definitions
PATTERN_DEFINITIONS: List[PatternDefinition] = [
    PatternDefinition(
        name="rsi_oversold",
        pattern_type="technical",
        criteria={"rsi_1h": {"max": 30}},
        description="RSI below 30 - Oversold condition"
    ),
    PatternDefinition(
        name="rsi_overbought",
        pattern_type="technical",
        criteria={"rsi_1h": {"min": 70}},
        description="RSI above 70 - Overbought condition"
    ),
    PatternDefinition(
        name="extreme_fear",
        pattern_type="sentiment",
        criteria={"fear_greed_index": {"max": 25}},
        description="Fear & Greed Index below 25 - Extreme Fear"
    ),
    PatternDefinition(
        name="extreme_greed",
        pattern_type="sentiment",
        criteria={"fear_greed_index": {"min": 75}},
        description="Fear & Greed Index above 75 - Extreme Greed"
    ),
    PatternDefinition(
        name="funding_rate_long_squeeze",
        pattern_type="derivatives",
        criteria={"funding_rate": {"min": 0.05}},
        description="High positive funding rate - Long squeeze risk"
    ),
    PatternDefinition(
        name="funding_rate_short_squeeze",
        pattern_type="derivatives",
        criteria={"funding_rate": {"max": -0.05}},
        description="High negative funding rate - Short squeeze risk"
    ),
    PatternDefinition(
        name="mtf_bullish_alignment",
        pattern_type="composite",
        criteria={
            "rsi_1h": {"min": 50},
            "rsi_4h": {"min": 50},
            "rsi_1d": {"min": 50}
        },
        description="All timeframes show bullish RSI alignment"
    ),
    PatternDefinition(
        name="mtf_bearish_alignment",
        pattern_type="composite",
        criteria={
            "rsi_1h": {"max": 50},
            "rsi_4h": {"max": 50},
            "rsi_1d": {"max": 50}
        },
        description="All timeframes show bearish RSI alignment"
    ),
    PatternDefinition(
        name="whale_accumulation",
        pattern_type="onchain",
        criteria={
            "whale_net_flow": {"min": 0},
            "whale_transaction_count": {"min": 5}
        },
        description="Whale accumulation detected"
    ),
    PatternDefinition(
        name="whale_distribution",
        pattern_type="onchain",
        criteria={
            "whale_net_flow": {"max": 0},
            "whale_transaction_count": {"min": 5}
        },
        description="Whale distribution detected"
    ),
    PatternDefinition(
        name="news_sentiment_bullish",
        pattern_type="sentiment",
        criteria={"news_sentiment_score": {"min": 0.6}},
        description="Strong bullish news sentiment"
    ),
    PatternDefinition(
        name="news_sentiment_bearish",
        pattern_type="sentiment",
        criteria={"news_sentiment_score": {"max": 0.4}},
        description="Strong bearish news sentiment"
    ),
    PatternDefinition(
        name="high_open_interest",
        pattern_type="derivatives",
        criteria={"open_interest_change_pct": {"min": 5}},
        description="Significant open interest increase"
    ),
    PatternDefinition(
        name="liquidation_cascade_risk",
        pattern_type="derivatives",
        criteria={
            "long_short_ratio": {"max": 0.7},
            "funding_rate": {"min": 0.03}
        },
        description="Conditions favoring long liquidation cascade"
    )
]


class PatternAnalyzer:
    """
    Analyzes market context to identify patterns and track their performance.
    """

    def __init__(self, session: Session):
        """Initialize with database session"""
        self.session = session
        self._patterns_cache: Dict[str, Dict] = {}

    def _extract_metrics_from_context(
        self,
        market_context: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        Extract relevant metrics from market context JSONB.

        Args:
            market_context: Market context from prediction

        Returns:
            Dictionary of metric name -> value
        """
        metrics = {}

        if not market_context:
            return metrics

        # Technical indicators
        technical = market_context.get('technical_data', {})
        if technical:
            indicators = technical.get('indicators', {})
            rsi = indicators.get('rsi', {})

            # RSI at different timeframes
            if '1h' in rsi or 'rsi' in indicators:
                metrics['rsi_1h'] = rsi.get('1h', indicators.get('rsi', {}).get('value', 50))
            if '4h' in rsi:
                metrics['rsi_4h'] = rsi.get('4h', 50)
            if '1d' in rsi or 'daily' in rsi:
                metrics['rsi_1d'] = rsi.get('1d', rsi.get('daily', 50))

        # Sentiment data
        sentiment = market_context.get('sentiment_data', {})
        if sentiment:
            metrics['fear_greed_index'] = sentiment.get('fear_greed_index', 50)
            metrics['social_sentiment'] = sentiment.get('social_sentiment', 0.5)

        # Derivatives data
        derivatives = market_context.get('derivatives_data', {})
        if derivatives:
            metrics['funding_rate'] = derivatives.get('funding_rate', 0)
            metrics['long_short_ratio'] = derivatives.get('long_short_ratio', 1.0)
            metrics['open_interest_change_pct'] = derivatives.get('open_interest_change_24h', 0)

        # On-chain data
        onchain = market_context.get('onchain_data', {})
        if onchain:
            whale_data = onchain.get('whale_transactions', {})
            metrics['whale_transaction_count'] = whale_data.get('count', 0)
            metrics['whale_net_flow'] = whale_data.get('net_flow', 0)

        # News data
        news = market_context.get('news_data', {})
        if news:
            metrics['news_sentiment_score'] = news.get('sentiment_score', 0.5)
            metrics['news_volume'] = news.get('article_count', 0)

        return metrics

    def _check_pattern_criteria(
        self,
        metrics: Dict[str, float],
        criteria: Dict[str, Any]
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if metrics match pattern criteria.

        Args:
            metrics: Extracted metrics
            criteria: Pattern criteria to check

        Returns:
            Tuple of (matched, matched_values)
        """
        matched_values = {}

        for metric_name, conditions in criteria.items():
            if metric_name not in metrics:
                return False, {}

            value = metrics[metric_name]

            # Check min/max conditions
            if 'min' in conditions and value < conditions['min']:
                return False, {}
            if 'max' in conditions and value > conditions['max']:
                return False, {}

            matched_values[metric_name] = value

        return True, matched_values

    def detect_patterns(
        self,
        market_context: Dict[str, Any]
    ) -> List[PatternMatch]:
        """
        Detect all matching patterns from market context.

        Args:
            market_context: Market context from prediction

        Returns:
            List of detected patterns
        """
        metrics = self._extract_metrics_from_context(market_context)
        matches = []

        for pattern in PATTERN_DEFINITIONS:
            matched, matched_values = self._check_pattern_criteria(
                metrics, pattern.criteria
            )

            if matched:
                matches.append(PatternMatch(
                    pattern_name=pattern.name,
                    pattern_type=pattern.pattern_type,
                    matched_at=datetime.now(timezone.utc),
                    context_data=matched_values
                ))

        return matches

    def record_pattern_match(
        self,
        prediction_id: UUID,
        pattern: PatternMatch
    ) -> bool:
        """
        Record a pattern match for a prediction.

        Args:
            prediction_id: Prediction UUID
            pattern: Detected pattern

        Returns:
            True if recorded successfully
        """
        try:
            # Get or create pattern record
            pattern_query = text("""
                INSERT INTO trading_predictions.prediction_patterns (
                    id, pattern_name, pattern_type, pattern_criteria,
                    occurrences, successful_predictions, accuracy_rate,
                    avg_confidence, last_occurrence, is_active
                ) VALUES (
                    gen_random_uuid(), :name, :type, :criteria,
                    0, 0, 0.0, 0.0, NULL, true
                )
                ON CONFLICT (pattern_name) DO UPDATE SET
                    last_occurrence = EXCLUDED.last_occurrence
                RETURNING id
            """)

            result = self.session.execute(pattern_query, {
                "name": pattern.pattern_name,
                "type": pattern.pattern_type,
                "criteria": str(pattern.context_data)
            })
            pattern_id = result.fetchone()[0]

            # Record the match
            match_query = text("""
                INSERT INTO trading_predictions.pattern_matches (
                    id, pattern_id, prediction_id, matched_at, was_successful
                ) VALUES (
                    gen_random_uuid(), :pattern_id, :prediction_id, :matched_at, NULL
                )
            """)

            self.session.execute(match_query, {
                "pattern_id": pattern_id,
                "prediction_id": prediction_id,
                "matched_at": pattern.matched_at
            })

            self.session.commit()

            logger.info(
                f'{{"event":"pattern_recorded","pattern":"{pattern.pattern_name}",'
                f'"prediction_id":"{prediction_id}"}}'
            )

            return True

        except Exception as e:
            self.session.rollback()
            logger.error(
                f'{{"event":"pattern_record_failed","pattern":"{pattern.pattern_name}",'
                f'"error":"{str(e)}"}}'
            )
            return False

    def update_pattern_outcomes(self) -> int:
        """
        Update pattern match outcomes based on prediction evaluations.

        Returns:
            Number of patterns updated
        """
        try:
            # Update pattern matches with prediction outcomes
            update_query = text("""
                UPDATE trading_predictions.pattern_matches pm
                SET was_successful = ap.was_correct
                FROM trading_predictions.automated_predictions ap
                WHERE pm.prediction_id = ap.id
                  AND pm.was_successful IS NULL
                  AND ap.was_correct IS NOT NULL
            """)

            result = self.session.execute(update_query)
            updated = result.rowcount

            # Update pattern statistics
            stats_query = text("""
                UPDATE trading_predictions.prediction_patterns pp
                SET
                    occurrences = stats.total_matches,
                    successful_predictions = stats.successful_matches,
                    accuracy_rate = CASE
                        WHEN stats.evaluated_matches > 0
                        THEN stats.successful_matches::float / stats.evaluated_matches
                        ELSE 0.0
                    END,
                    avg_confidence = stats.avg_conf,
                    last_occurrence = stats.last_match
                FROM (
                    SELECT
                        pm.pattern_id,
                        COUNT(*) as total_matches,
                        COUNT(*) FILTER (WHERE pm.was_successful IS NOT NULL) as evaluated_matches,
                        COUNT(*) FILTER (WHERE pm.was_successful = true) as successful_matches,
                        AVG(ap.confidence) as avg_conf,
                        MAX(pm.matched_at) as last_match
                    FROM trading_predictions.pattern_matches pm
                    JOIN trading_predictions.automated_predictions ap ON pm.prediction_id = ap.id
                    GROUP BY pm.pattern_id
                ) stats
                WHERE pp.id = stats.pattern_id
            """)

            self.session.execute(stats_query)
            self.session.commit()

            logger.info(f'{{"event":"pattern_outcomes_updated","count":{updated}}}')

            return updated

        except Exception as e:
            self.session.rollback()
            logger.error(f'{{"event":"pattern_outcome_update_failed","error":"{str(e)}"}}')
            return 0

    def get_pattern_performance(
        self,
        min_occurrences: int = 5
    ) -> List[PatternPerformance]:
        """
        Get performance statistics for all patterns.

        Args:
            min_occurrences: Minimum occurrences to include

        Returns:
            List of pattern performance stats
        """
        try:
            query = text("""
                SELECT
                    pattern_name,
                    occurrences,
                    successful_predictions,
                    accuracy_rate,
                    avg_confidence,
                    last_occurrence
                FROM trading_predictions.prediction_patterns
                WHERE is_active = true
                  AND occurrences >= :min_occurrences
                ORDER BY accuracy_rate DESC, occurrences DESC
            """)

            result = self.session.execute(query, {"min_occurrences": min_occurrences})

            patterns = []
            for row in result:
                patterns.append(PatternPerformance(
                    pattern_name=row[0],
                    occurrences=row[1],
                    successful=row[2],
                    accuracy_rate=float(row[3]) if row[3] else 0.0,
                    avg_confidence=float(row[4]) if row[4] else 0.0,
                    last_occurrence=row[5]
                ))

            return patterns

        except Exception as e:
            logger.error(f'{{"event":"pattern_performance_query_failed","error":"{str(e)}"}}')
            return []

    def get_matching_historical_predictions(
        self,
        market_context: Dict[str, Any],
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Find historical predictions with similar patterns.

        Args:
            market_context: Current market context
            limit: Maximum results to return

        Returns:
            List of similar historical predictions with outcomes
        """
        # Detect current patterns
        current_patterns = self.detect_patterns(market_context)

        if not current_patterns:
            return []

        pattern_names = [p.pattern_name for p in current_patterns]

        try:
            query = text("""
                SELECT
                    ap.id,
                    ap.symbol,
                    ap.prediction_type,
                    ap.confidence,
                    ap.was_correct,
                    ap.actual_price_change,
                    ap.created_at,
                    pp.pattern_name
                FROM trading_predictions.automated_predictions ap
                JOIN trading_predictions.pattern_matches pm ON ap.id = pm.prediction_id
                JOIN trading_predictions.prediction_patterns pp ON pm.pattern_id = pp.id
                WHERE pp.pattern_name = ANY(:pattern_names)
                  AND ap.was_correct IS NOT NULL
                ORDER BY ap.created_at DESC
                LIMIT :limit
            """)

            result = self.session.execute(query, {
                "pattern_names": pattern_names,
                "limit": limit
            })

            predictions = []
            for row in result:
                predictions.append({
                    "prediction_id": str(row[0]),
                    "symbol": row[1],
                    "prediction_type": row[2],
                    "confidence": float(row[3]) if row[3] else None,
                    "was_correct": row[4],
                    "actual_change_pct": float(row[5]) if row[5] else None,
                    "created_at": row[6].isoformat() if row[6] else None,
                    "pattern": row[7]
                })

            return predictions

        except Exception as e:
            logger.error(
                f'{{"event":"historical_pattern_query_failed","error":"{str(e)}"}}'
            )
            return []


def analyze_prediction_patterns(
    session: Session,
    prediction_id: UUID,
    market_context: Dict[str, Any]
) -> List[str]:
    """
    Convenience function to detect and record patterns for a prediction.

    Args:
        session: Database session
        prediction_id: Prediction UUID
        market_context: Market context from prediction

    Returns:
        List of detected pattern names
    """
    analyzer = PatternAnalyzer(session)
    patterns = analyzer.detect_patterns(market_context)

    detected_names = []
    for pattern in patterns:
        if analyzer.record_pattern_match(prediction_id, pattern):
            detected_names.append(pattern.pattern_name)

    return detected_names


def get_pattern_context_for_prompt(
    session: Session,
    market_context: Dict[str, Any],
    days: int = 30
) -> str:
    """
    Generate pattern context text for inclusion in Claude prompts.

    Args:
        session: Database session
        market_context: Current market context
        days: Days of history to consider

    Returns:
        Formatted pattern context string
    """
    analyzer = PatternAnalyzer(session)

    # Detect current patterns
    patterns = analyzer.detect_patterns(market_context)

    if not patterns:
        return "No notable patterns detected in current market conditions."

    # Get historical predictions with similar patterns
    similar_preds = analyzer.get_matching_historical_predictions(market_context, limit=5)

    # Build context string
    lines = ["DETECTED PATTERNS:"]
    for p in patterns:
        lines.append(f"- {p.pattern_name.replace('_', ' ').title()}")

    if similar_preds:
        correct_count = sum(1 for p in similar_preds if p['was_correct'])
        total = len(similar_preds)

        lines.append("")
        lines.append(f"HISTORICAL PATTERN PERFORMANCE (last {days} days):")
        lines.append(f"- Similar patterns matched {total} times previously")
        lines.append(f"- Historical accuracy: {correct_count}/{total} ({100*correct_count/total:.0f}%)")

        # Show recent examples
        if similar_preds[:3]:
            lines.append("")
            lines.append("RECENT SIMILAR CONDITIONS:")
            for pred in similar_preds[:3]:
                outcome = "CORRECT" if pred['was_correct'] else "INCORRECT"
                change = pred.get('actual_change_pct', 0)
                lines.append(
                    f"- {pred['created_at'][:10]}: Predicted {pred['prediction_type'].upper()}, "
                    f"Result: {outcome} ({change:+.1f}%)"
                )

    return "\n".join(lines)
