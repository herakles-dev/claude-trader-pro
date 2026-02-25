"""
Confidence Calibration Service

Analyzes historical prediction confidence vs actual outcomes to provide
calibrated confidence adjustments. This helps correct for systematic
over/under-confidence in the AI predictions.

Key Features:
1. Tracks confidence buckets (0-10, 10-20, ..., 90-100)
2. Calculates actual accuracy per bucket
3. Provides calibration curve for confidence adjustment
4. Supports symbol-specific calibration

Author: AI Integration Specialist
Date: 2026-01-16
"""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp":"%(asctime)s","service":"confidence_calibration","level":"%(levelname)s","message":"%(message)s"}'
)
logger = logging.getLogger(__name__)


@dataclass
class CalibrationBucket:
    """Statistics for a confidence bucket"""
    bucket_min: int
    bucket_max: int
    total_predictions: int
    correct_predictions: int
    actual_accuracy: float
    calibration_factor: float  # actual / expected (1.0 = perfect calibration)


@dataclass
class CalibrationReport:
    """Full calibration report"""
    symbol: str
    days_analyzed: int
    total_predictions: int
    overall_accuracy: float
    buckets: List[CalibrationBucket]
    is_overconfident: bool  # True if AI tends to be too confident
    recommended_adjustment: float  # Multiply confidence by this factor
    brier_score: float  # Lower is better (0 = perfect)
    calibration_error: float  # Average absolute error between confidence and accuracy


class ConfidenceCalibrationService:
    """
    Service for analyzing and calibrating prediction confidence.
    """

    BUCKET_SIZE = 10  # 10% buckets
    MIN_SAMPLES_PER_BUCKET = 5  # Minimum samples to consider bucket valid

    def __init__(self, session: Session):
        """Initialize with database session"""
        self.session = session
        self._cache: Dict[str, CalibrationReport] = {}
        self._cache_time: Dict[str, datetime] = {}
        self._cache_ttl = timedelta(hours=1)

    def _get_bucket_index(self, confidence: float) -> int:
        """Get bucket index for a confidence value (0-9)"""
        return min(int(confidence // self.BUCKET_SIZE), 9)

    def _get_bucket_range(self, bucket_index: int) -> Tuple[int, int]:
        """Get min/max range for a bucket index"""
        min_val = bucket_index * self.BUCKET_SIZE
        max_val = min_val + self.BUCKET_SIZE
        return min_val, max_val

    def _get_bucket_midpoint(self, bucket_index: int) -> float:
        """Get the midpoint of a bucket (expected accuracy)"""
        min_val, max_val = self._get_bucket_range(bucket_index)
        return (min_val + max_val) / 2.0

    def analyze_calibration(
        self,
        symbol: Optional[str] = None,
        days: int = 30
    ) -> CalibrationReport:
        """
        Analyze prediction calibration for a symbol or all symbols.

        Args:
            symbol: Trading pair to analyze (None for all)
            days: Number of days of history to analyze

        Returns:
            CalibrationReport with detailed statistics
        """
        cache_key = f"{symbol or 'ALL'}_{days}"

        # Check cache
        if cache_key in self._cache:
            cache_age = datetime.now(timezone.utc) - self._cache_time.get(cache_key, datetime.min.replace(tzinfo=timezone.utc))
            if cache_age < self._cache_ttl:
                return self._cache[cache_key]

        try:
            # Query historical predictions with outcomes
            query = text("""
                SELECT
                    confidence,
                    was_correct
                FROM trading_predictions.automated_predictions
                WHERE was_correct IS NOT NULL
                  AND confidence IS NOT NULL
                  AND created_at > NOW() - INTERVAL :days DAY
                  AND (:symbol IS NULL OR symbol = :symbol)
                ORDER BY created_at DESC
            """)

            result = self.session.execute(query, {
                "symbol": symbol,
                "days": f"{days} days"
            })

            # Initialize buckets
            buckets_data: List[Dict] = []
            for i in range(10):
                buckets_data.append({
                    "total": 0,
                    "correct": 0,
                    "confidence_sum": 0.0
                })

            total_predictions = 0
            total_correct = 0
            brier_sum = 0.0

            for row in result:
                raw_confidence = float(row[0])
                was_correct = row[1]

                # Convert decimal confidence (0-1) to percentage (0-100) if needed
                # DB stores as decimal (0.68 = 68%), but calibration expects percentage
                if raw_confidence <= 1.0:
                    confidence = raw_confidence * 100.0
                else:
                    confidence = raw_confidence

                bucket_idx = self._get_bucket_index(confidence)
                buckets_data[bucket_idx]["total"] += 1
                buckets_data[bucket_idx]["confidence_sum"] += confidence

                if was_correct:
                    buckets_data[bucket_idx]["correct"] += 1
                    total_correct += 1

                total_predictions += 1

                # Brier score component (uses decimal 0-1 for calculation)
                outcome = 1.0 if was_correct else 0.0
                confidence_decimal = confidence / 100.0
                brier_sum += (confidence_decimal - outcome) ** 2

            if total_predictions == 0:
                # Return empty report
                return CalibrationReport(
                    symbol=symbol or "ALL",
                    days_analyzed=days,
                    total_predictions=0,
                    overall_accuracy=0.0,
                    buckets=[],
                    is_overconfident=False,
                    recommended_adjustment=1.0,
                    brier_score=0.0,
                    calibration_error=0.0
                )

            # Calculate bucket statistics
            buckets: List[CalibrationBucket] = []
            calibration_errors = []
            weighted_adjustment_sum = 0.0
            weighted_total = 0

            for i in range(10):
                data = buckets_data[i]
                min_val, max_val = self._get_bucket_range(i)

                if data["total"] >= self.MIN_SAMPLES_PER_BUCKET:
                    actual_accuracy = data["correct"] / data["total"] * 100
                    expected_accuracy = self._get_bucket_midpoint(i)

                    # Calibration factor: how much to adjust
                    if expected_accuracy > 0:
                        calibration_factor = actual_accuracy / expected_accuracy
                    else:
                        calibration_factor = 1.0

                    calibration_errors.append(abs(actual_accuracy - expected_accuracy))

                    # Weight by sample size for overall adjustment
                    weighted_adjustment_sum += calibration_factor * data["total"]
                    weighted_total += data["total"]

                    buckets.append(CalibrationBucket(
                        bucket_min=min_val,
                        bucket_max=max_val,
                        total_predictions=data["total"],
                        correct_predictions=data["correct"],
                        actual_accuracy=actual_accuracy,
                        calibration_factor=calibration_factor
                    ))

            # Calculate overall metrics
            overall_accuracy = total_correct / total_predictions * 100
            brier_score = brier_sum / total_predictions
            calibration_error = sum(calibration_errors) / len(calibration_errors) if calibration_errors else 0.0

            # Recommended adjustment factor
            if weighted_total > 0:
                recommended_adjustment = weighted_adjustment_sum / weighted_total
            else:
                recommended_adjustment = 1.0

            # Is the system overconfident?
            # Check if high-confidence predictions (>70%) underperform
            high_conf_bucket = buckets_data[7:10]  # 70-100%
            high_conf_total = sum(b["total"] for b in high_conf_bucket)
            high_conf_correct = sum(b["correct"] for b in high_conf_bucket)

            if high_conf_total >= 10:
                high_conf_accuracy = high_conf_correct / high_conf_total * 100
                is_overconfident = high_conf_accuracy < 75  # If 70%+ confidence predictions are <75% accurate
            else:
                is_overconfident = False

            report = CalibrationReport(
                symbol=symbol or "ALL",
                days_analyzed=days,
                total_predictions=total_predictions,
                overall_accuracy=overall_accuracy,
                buckets=buckets,
                is_overconfident=is_overconfident,
                recommended_adjustment=recommended_adjustment,
                brier_score=brier_score,
                calibration_error=calibration_error
            )

            # Cache the result
            self._cache[cache_key] = report
            self._cache_time[cache_key] = datetime.now(timezone.utc)

            logger.info(
                f'{{"event":"calibration_analyzed","symbol":"{symbol or "ALL"}",'
                f'"predictions":{total_predictions},"accuracy":{overall_accuracy:.1f},'
                f'"brier":{brier_score:.4f},"adjustment":{recommended_adjustment:.3f}}}'
            )

            return report

        except Exception as e:
            logger.error(f'{{"event":"calibration_analysis_failed","error":"{str(e)}"}}')
            return CalibrationReport(
                symbol=symbol or "ALL",
                days_analyzed=days,
                total_predictions=0,
                overall_accuracy=0.0,
                buckets=[],
                is_overconfident=False,
                recommended_adjustment=1.0,
                brier_score=0.0,
                calibration_error=0.0
            )

    def get_calibrated_confidence(
        self,
        raw_confidence: float,
        symbol: Optional[str] = None
    ) -> float:
        """
        Apply calibration to a raw confidence value.

        Args:
            raw_confidence: Original confidence (0-100)
            symbol: Trading pair for symbol-specific calibration

        Returns:
            Calibrated confidence (0-100)
        """
        # Get calibration report
        report = self.analyze_calibration(symbol=symbol, days=30)

        if not report.buckets:
            return raw_confidence

        # Find the appropriate bucket
        bucket_idx = self._get_bucket_index(raw_confidence)

        # Find calibration factor for this bucket
        calibration_factor = 1.0
        for bucket in report.buckets:
            if bucket.bucket_min <= raw_confidence < bucket.bucket_max:
                calibration_factor = bucket.calibration_factor
                break

        # Apply calibration
        calibrated = raw_confidence * calibration_factor

        # Clamp to valid range
        calibrated = max(0, min(100, calibrated))

        logger.debug(
            f'{{"event":"confidence_calibrated","raw":{raw_confidence:.1f},'
            f'"calibrated":{calibrated:.1f},"factor":{calibration_factor:.3f}}}'
        )

        return calibrated

    def get_calibration_context_for_prompt(
        self,
        symbol: Optional[str] = None,
        days: int = 30
    ) -> str:
        """
        Generate calibration context for inclusion in AI prompts.

        This helps the AI understand how its historical confidence
        has correlated with actual outcomes.

        Args:
            symbol: Trading pair to analyze
            days: Days of history to consider

        Returns:
            Formatted context string for prompt
        """
        report = self.analyze_calibration(symbol=symbol, days=days)

        if report.total_predictions < 10:
            return "Insufficient historical data for confidence calibration."

        lines = ["CONFIDENCE CALIBRATION ANALYSIS:"]
        lines.append(f"Based on {report.total_predictions} predictions over {days} days:")
        lines.append(f"- Overall Accuracy: {report.overall_accuracy:.1f}%")
        lines.append(f"- Brier Score: {report.brier_score:.4f} (lower is better)")

        if report.is_overconfident:
            lines.append("")
            lines.append("IMPORTANT: Historical analysis shows OVERCONFIDENCE tendency.")
            lines.append("High-confidence predictions (>70%) have underperformed expectations.")
            lines.append(f"Consider reducing high confidence by ~{(1 - report.recommended_adjustment) * 100:.0f}%")

        # Show bucket performance
        if report.buckets:
            lines.append("")
            lines.append("CONFIDENCE BUCKET PERFORMANCE:")
            for bucket in report.buckets:
                expected = (bucket.bucket_min + bucket.bucket_max) / 2
                diff = bucket.actual_accuracy - expected
                diff_str = f"{diff:+.1f}%" if diff != 0 else "aligned"

                lines.append(
                    f"- {bucket.bucket_min}-{bucket.bucket_max}%: "
                    f"Actual {bucket.actual_accuracy:.1f}% ({bucket.total_predictions} samples) - {diff_str}"
                )

        # Provide guidance based on calibration
        lines.append("")
        lines.append("CALIBRATION GUIDANCE:")

        if report.calibration_error < 5:
            lines.append("- Confidence calibration is EXCELLENT. Trust your confidence levels.")
        elif report.calibration_error < 10:
            lines.append("- Confidence calibration is GOOD. Minor adjustments may help.")
        elif report.calibration_error < 15:
            lines.append("- Confidence calibration is MODERATE. Consider being more conservative.")
        else:
            lines.append("- Confidence calibration needs work. Significantly adjust confidence levels.")

        return "\n".join(lines)

    def store_calibration_snapshot(self) -> bool:
        """
        Store current calibration metrics for tracking over time.

        Returns:
            True if stored successfully
        """
        try:
            report = self.analyze_calibration(days=30)

            if report.total_predictions < 10:
                return False

            query = text("""
                INSERT INTO trading_predictions.calibration_snapshots (
                    id, captured_at, symbol, predictions_analyzed,
                    overall_accuracy, brier_score, calibration_error,
                    is_overconfident, recommended_adjustment, bucket_data
                ) VALUES (
                    gen_random_uuid(), NOW(), :symbol, :predictions,
                    :accuracy, :brier, :cal_error,
                    :overconf, :adjustment, :bucket_data
                )
            """)

            bucket_data = [
                {
                    "min": b.bucket_min,
                    "max": b.bucket_max,
                    "total": b.total_predictions,
                    "correct": b.correct_predictions,
                    "accuracy": b.actual_accuracy
                }
                for b in report.buckets
            ]

            self.session.execute(query, {
                "symbol": report.symbol,
                "predictions": report.total_predictions,
                "accuracy": report.overall_accuracy,
                "brier": report.brier_score,
                "cal_error": report.calibration_error,
                "overconf": report.is_overconfident,
                "adjustment": report.recommended_adjustment,
                "bucket_data": str(bucket_data)
            })

            self.session.commit()

            logger.info(f'{{"event":"calibration_snapshot_stored","predictions":{report.total_predictions}}}')
            return True

        except Exception as e:
            self.session.rollback()
            logger.error(f'{{"event":"calibration_snapshot_failed","error":"{str(e)}"}}')
            return False


def get_calibration_for_prediction(
    session: Session,
    symbol: str,
    raw_confidence: float
) -> Dict[str, Any]:
    """
    Convenience function to get calibration info for a prediction.

    Args:
        session: Database session
        symbol: Trading pair
        raw_confidence: Original confidence value

    Returns:
        Dictionary with calibrated confidence and metadata
    """
    service = ConfidenceCalibrationService(session)

    calibrated = service.get_calibrated_confidence(raw_confidence, symbol)
    report = service.analyze_calibration(symbol=symbol, days=30)

    return {
        "raw_confidence": raw_confidence,
        "calibrated_confidence": calibrated,
        "adjustment_applied": calibrated / raw_confidence if raw_confidence > 0 else 1.0,
        "is_overconfident_symbol": report.is_overconfident,
        "symbol_accuracy": report.overall_accuracy,
        "sample_size": report.total_predictions
    }
