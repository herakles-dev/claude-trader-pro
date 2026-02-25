"""
Risk Management Service

Implements trading risk controls and position sizing rules to protect
capital and enforce responsible trading behavior.

Key Features:
1. Position sizing limits (max % of portfolio per trade)
2. Daily loss limits (stop trading if daily P&L exceeds threshold)
3. Maximum drawdown protection
4. Confidence-based signal filtering
5. Consecutive loss tracking
6. Market volatility adjustments

Author: Backend Architect
Date: 2026-01-16
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass, field
from enum import Enum

from sqlalchemy import text
from sqlalchemy.orm import Session

logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp":"%(asctime)s","service":"risk_management","level":"%(levelname)s","message":"%(message)s"}'
)
logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk level classification"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"


class TradeDecision(Enum):
    """Trade decision outcomes"""
    APPROVED = "approved"
    REJECTED = "rejected"
    REDUCED = "reduced"  # Approved but with reduced size


@dataclass
class RiskConfig:
    """Risk management configuration"""
    # Position sizing
    max_position_size_pct: float = 5.0  # Max 5% of portfolio per trade
    min_position_size_pct: float = 0.5  # Min position size

    # Daily limits
    max_daily_loss_pct: float = 3.0  # Stop trading if daily loss exceeds 3%
    max_daily_trades: int = 10  # Maximum trades per day

    # Drawdown protection
    max_drawdown_pct: float = 10.0  # Max drawdown from peak
    drawdown_reduce_size_pct: float = 5.0  # Reduce position size if drawdown > 5%

    # Confidence thresholds
    min_confidence_to_trade: float = 55.0  # Minimum AI confidence to execute
    high_confidence_threshold: float = 75.0  # High confidence for full position

    # Consecutive loss protection
    max_consecutive_losses: int = 5  # Pause after 5 consecutive losses
    consecutive_loss_cooldown_hours: int = 4  # Cooldown period

    # Volatility adjustments
    high_volatility_reduction: float = 0.5  # Reduce position by 50% in high volatility
    volatility_threshold_pct: float = 5.0  # 24h price change threshold

    # Portfolio settings
    initial_portfolio_value: float = 10000.0  # Starting portfolio value (paper trading)

    @classmethod
    def from_env(cls) -> 'RiskConfig':
        """Load risk config from environment variables"""
        return cls(
            max_position_size_pct=float(os.getenv('RISK_MAX_POSITION_PCT', '5.0')),
            min_position_size_pct=float(os.getenv('RISK_MIN_POSITION_PCT', '0.5')),
            max_daily_loss_pct=float(os.getenv('RISK_MAX_DAILY_LOSS_PCT', '3.0')),
            max_daily_trades=int(os.getenv('RISK_MAX_DAILY_TRADES', '10')),
            max_drawdown_pct=float(os.getenv('RISK_MAX_DRAWDOWN_PCT', '10.0')),
            drawdown_reduce_size_pct=float(os.getenv('RISK_DRAWDOWN_REDUCE_PCT', '5.0')),
            min_confidence_to_trade=float(os.getenv('RISK_MIN_CONFIDENCE', '55.0')),
            high_confidence_threshold=float(os.getenv('RISK_HIGH_CONFIDENCE', '75.0')),
            max_consecutive_losses=int(os.getenv('RISK_MAX_CONSEC_LOSSES', '5')),
            consecutive_loss_cooldown_hours=int(os.getenv('RISK_COOLDOWN_HOURS', '4')),
            high_volatility_reduction=float(os.getenv('RISK_VOLATILITY_REDUCTION', '0.5')),
            volatility_threshold_pct=float(os.getenv('RISK_VOLATILITY_THRESHOLD', '5.0')),
            initial_portfolio_value=float(os.getenv('RISK_INITIAL_PORTFOLIO', '10000.0')),
        )


@dataclass
class RiskAssessment:
    """Result of a risk assessment"""
    decision: TradeDecision
    approved: bool
    position_size_pct: float
    risk_level: RiskLevel
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    adjustments_applied: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision.value,
            "approved": self.approved,
            "position_size_pct": self.position_size_pct,
            "risk_level": self.risk_level.value,
            "reasons": self.reasons,
            "warnings": self.warnings,
            "adjustments_applied": self.adjustments_applied
        }


class RiskManagementService:
    """
    Service for assessing and managing trading risk.
    """

    def __init__(self, session: Session, config: Optional[RiskConfig] = None):
        """
        Initialize risk management service.

        Args:
            session: Database session
            config: Risk configuration (loads from env if not provided)
        """
        self.session = session
        self.config = config or RiskConfig.from_env()

        logger.info(
            f'{{"event":"risk_service_initialized",'
            f'"max_position_pct":{self.config.max_position_size_pct},'
            f'"max_daily_loss_pct":{self.config.max_daily_loss_pct},'
            f'"min_confidence":{self.config.min_confidence_to_trade}}}'
        )

    def get_daily_pnl(self, symbol: Optional[str] = None) -> Tuple[float, int]:
        """
        Get today's P&L and trade count.

        Args:
            symbol: Optional symbol filter

        Returns:
            Tuple of (daily_pnl, trade_count)
        """
        try:
            query = text("""
                SELECT
                    COALESCE(SUM(pnl), 0) as daily_pnl,
                    COUNT(*) as trade_count
                FROM trading_predictions.trade_outcomes
                WHERE DATE(closed_at) = CURRENT_DATE
                  AND status = 'closed'
                  AND (:symbol IS NULL OR symbol = :symbol)
            """)

            result = self.session.execute(query, {"symbol": symbol}).fetchone()

            daily_pnl = float(result[0]) if result[0] else 0.0
            trade_count = int(result[1]) if result[1] else 0

            return daily_pnl, trade_count

        except Exception as e:
            logger.error(f'{{"event":"daily_pnl_query_failed","error":"{str(e)}"}}')
            return 0.0, 0

    def get_consecutive_losses(self, symbol: Optional[str] = None) -> Tuple[int, Optional[datetime]]:
        """
        Get current consecutive loss streak and last loss time.

        Args:
            symbol: Optional symbol filter

        Returns:
            Tuple of (consecutive_losses, last_loss_time)
        """
        try:
            query = text("""
                WITH recent_trades AS (
                    SELECT
                        pnl,
                        closed_at,
                        ROW_NUMBER() OVER (ORDER BY closed_at DESC) as rn
                    FROM trading_predictions.trade_outcomes
                    WHERE status = 'closed'
                      AND (:symbol IS NULL OR symbol = :symbol)
                    ORDER BY closed_at DESC
                    LIMIT 20
                ),
                streak AS (
                    SELECT
                        COUNT(*) as consecutive_losses,
                        MAX(closed_at) as last_loss_time
                    FROM recent_trades
                    WHERE rn <= (
                        SELECT COALESCE(MIN(rn) - 1, 20)
                        FROM recent_trades
                        WHERE pnl >= 0
                    )
                    AND pnl < 0
                )
                SELECT consecutive_losses, last_loss_time FROM streak
            """)

            result = self.session.execute(query, {"symbol": symbol}).fetchone()

            consecutive = int(result[0]) if result and result[0] else 0
            last_loss_time = result[1] if result and result[1] else None

            return consecutive, last_loss_time

        except Exception as e:
            logger.error(f'{{"event":"consecutive_loss_query_failed","error":"{str(e)}"}}')
            return 0, None

    def get_drawdown_from_peak(self) -> Tuple[float, float]:
        """
        Calculate current drawdown from portfolio peak.

        Returns:
            Tuple of (current_value, drawdown_pct)
        """
        try:
            # Get total P&L to calculate current portfolio value
            query = text("""
                SELECT COALESCE(SUM(pnl), 0) as total_pnl
                FROM trading_predictions.trade_outcomes
                WHERE status = 'closed'
            """)

            result = self.session.execute(query).fetchone()
            total_pnl = float(result[0]) if result[0] else 0.0

            current_value = self.config.initial_portfolio_value + total_pnl

            # Get peak portfolio value (initial + max cumulative P&L)
            peak_query = text("""
                SELECT MAX(running_total) as peak_pnl
                FROM (
                    SELECT SUM(pnl) OVER (ORDER BY closed_at) as running_total
                    FROM trading_predictions.trade_outcomes
                    WHERE status = 'closed'
                ) running
            """)

            peak_result = self.session.execute(peak_query).fetchone()
            peak_pnl = float(peak_result[0]) if peak_result and peak_result[0] else 0.0
            peak_value = max(
                self.config.initial_portfolio_value + peak_pnl,
                self.config.initial_portfolio_value
            )

            # Calculate drawdown
            if peak_value > 0:
                drawdown_pct = ((peak_value - current_value) / peak_value) * 100
            else:
                drawdown_pct = 0.0

            return current_value, max(0.0, drawdown_pct)

        except Exception as e:
            logger.error(f'{{"event":"drawdown_query_failed","error":"{str(e)}"}}')
            return self.config.initial_portfolio_value, 0.0

    def check_cooldown_active(self, last_loss_time: Optional[datetime]) -> bool:
        """
        Check if cooldown period is active after consecutive losses.

        Args:
            last_loss_time: Time of last loss

        Returns:
            True if still in cooldown
        """
        if last_loss_time is None:
            return False

        cooldown_end = last_loss_time + timedelta(hours=self.config.consecutive_loss_cooldown_hours)
        return datetime.now(timezone.utc) < cooldown_end.replace(tzinfo=timezone.utc)

    def assess_trade(
        self,
        symbol: str,
        prediction_confidence: float,
        volatility_24h: Optional[float] = None,
        market_regime: Optional[str] = None
    ) -> RiskAssessment:
        """
        Assess whether a trade should be executed and at what size.

        Args:
            symbol: Trading symbol
            prediction_confidence: AI prediction confidence (0-100)
            volatility_24h: 24-hour price volatility (%)
            market_regime: Market regime (trending, ranging, volatile)

        Returns:
            RiskAssessment with decision and sizing
        """
        reasons = []
        warnings = []
        adjustments = []
        position_size_pct = self.config.max_position_size_pct
        risk_level = RiskLevel.LOW

        # Check 1: Minimum confidence threshold
        if prediction_confidence < self.config.min_confidence_to_trade:
            reasons.append(
                f"Confidence {prediction_confidence:.1f}% below minimum "
                f"{self.config.min_confidence_to_trade}%"
            )
            return RiskAssessment(
                decision=TradeDecision.REJECTED,
                approved=False,
                position_size_pct=0.0,
                risk_level=RiskLevel.HIGH,
                reasons=reasons
            )

        # Check 2: Daily loss limit
        daily_pnl, daily_trade_count = self.get_daily_pnl(symbol)
        daily_loss_pct = abs(daily_pnl) / self.config.initial_portfolio_value * 100

        if daily_pnl < 0 and daily_loss_pct >= self.config.max_daily_loss_pct:
            reasons.append(
                f"Daily loss limit reached: {daily_loss_pct:.2f}% "
                f"(max: {self.config.max_daily_loss_pct}%)"
            )
            return RiskAssessment(
                decision=TradeDecision.REJECTED,
                approved=False,
                position_size_pct=0.0,
                risk_level=RiskLevel.EXTREME,
                reasons=reasons
            )

        # Check 3: Daily trade count limit
        if daily_trade_count >= self.config.max_daily_trades:
            reasons.append(
                f"Daily trade limit reached: {daily_trade_count} "
                f"(max: {self.config.max_daily_trades})"
            )
            return RiskAssessment(
                decision=TradeDecision.REJECTED,
                approved=False,
                position_size_pct=0.0,
                risk_level=RiskLevel.HIGH,
                reasons=reasons
            )

        # Check 4: Consecutive losses
        consecutive_losses, last_loss_time = self.get_consecutive_losses(symbol)

        if consecutive_losses >= self.config.max_consecutive_losses:
            if self.check_cooldown_active(last_loss_time):
                reasons.append(
                    f"In cooldown after {consecutive_losses} consecutive losses. "
                    f"Resume after {self.config.consecutive_loss_cooldown_hours}h cooldown."
                )
                return RiskAssessment(
                    decision=TradeDecision.REJECTED,
                    approved=False,
                    position_size_pct=0.0,
                    risk_level=RiskLevel.EXTREME,
                    reasons=reasons
                )
            else:
                warnings.append(
                    f"Had {consecutive_losses} consecutive losses. Cooldown complete."
                )

        # Check 5: Drawdown protection
        current_value, drawdown_pct = self.get_drawdown_from_peak()

        if drawdown_pct >= self.config.max_drawdown_pct:
            reasons.append(
                f"Maximum drawdown reached: {drawdown_pct:.2f}% "
                f"(max: {self.config.max_drawdown_pct}%)"
            )
            return RiskAssessment(
                decision=TradeDecision.REJECTED,
                approved=False,
                position_size_pct=0.0,
                risk_level=RiskLevel.EXTREME,
                reasons=reasons
            )
        elif drawdown_pct >= self.config.drawdown_reduce_size_pct:
            # Reduce position size based on drawdown
            reduction = 1 - (drawdown_pct / self.config.max_drawdown_pct)
            position_size_pct *= reduction
            adjustments.append(
                f"Position reduced to {reduction*100:.0f}% due to "
                f"{drawdown_pct:.1f}% drawdown"
            )
            risk_level = RiskLevel.MEDIUM

        # Check 6: Volatility adjustment
        if volatility_24h is not None and volatility_24h > self.config.volatility_threshold_pct:
            position_size_pct *= self.config.high_volatility_reduction
            adjustments.append(
                f"Position reduced by {(1-self.config.high_volatility_reduction)*100:.0f}% "
                f"due to high volatility ({volatility_24h:.1f}%)"
            )
            risk_level = RiskLevel.MEDIUM if risk_level == RiskLevel.LOW else risk_level

        # Check 7: Confidence-based sizing
        if prediction_confidence < self.config.high_confidence_threshold:
            # Scale position size by confidence
            confidence_factor = prediction_confidence / self.config.high_confidence_threshold
            position_size_pct *= confidence_factor
            adjustments.append(
                f"Position scaled to {confidence_factor*100:.0f}% based on "
                f"confidence {prediction_confidence:.1f}%"
            )

        # Ensure minimum position size
        if position_size_pct < self.config.min_position_size_pct:
            position_size_pct = self.config.min_position_size_pct
            adjustments.append(f"Position increased to minimum {self.config.min_position_size_pct}%")

        # Determine final decision
        if len(adjustments) > 0:
            decision = TradeDecision.REDUCED
        else:
            decision = TradeDecision.APPROVED

        # Add warnings for elevated risk
        if daily_loss_pct > self.config.max_daily_loss_pct * 0.5:
            warnings.append(f"Daily loss at {daily_loss_pct:.2f}% (approaching limit)")
        if consecutive_losses >= 3:
            warnings.append(f"On {consecutive_losses} consecutive losses")

        logger.info(
            f'{{"event":"trade_assessed","symbol":"{symbol}",'
            f'"decision":"{decision.value}","position_pct":{position_size_pct:.2f},'
            f'"risk_level":"{risk_level.value}","confidence":{prediction_confidence:.1f}}}'
        )

        return RiskAssessment(
            decision=decision,
            approved=True,
            position_size_pct=round(position_size_pct, 2),
            risk_level=risk_level,
            reasons=reasons,
            warnings=warnings,
            adjustments_applied=adjustments
        )

    def get_risk_summary(self) -> Dict[str, Any]:
        """
        Get a summary of current risk metrics.

        Returns:
            Dictionary with risk summary
        """
        daily_pnl, daily_trades = self.get_daily_pnl()
        consecutive_losses, last_loss = self.get_consecutive_losses()
        current_value, drawdown = self.get_drawdown_from_peak()

        daily_loss_pct = abs(daily_pnl) / self.config.initial_portfolio_value * 100 if daily_pnl < 0 else 0

        return {
            "portfolio": {
                "initial_value": self.config.initial_portfolio_value,
                "current_value": current_value,
                "total_pnl": current_value - self.config.initial_portfolio_value,
                "drawdown_pct": drawdown
            },
            "daily": {
                "pnl": daily_pnl,
                "trades": daily_trades,
                "loss_pct": daily_loss_pct,
                "loss_limit_pct": self.config.max_daily_loss_pct,
                "trades_remaining": max(0, self.config.max_daily_trades - daily_trades)
            },
            "risk_status": {
                "consecutive_losses": consecutive_losses,
                "max_consecutive": self.config.max_consecutive_losses,
                "in_cooldown": self.check_cooldown_active(last_loss) if consecutive_losses >= self.config.max_consecutive_losses else False,
                "drawdown_warning": drawdown >= self.config.drawdown_reduce_size_pct,
                "daily_loss_warning": daily_loss_pct >= self.config.max_daily_loss_pct * 0.5
            },
            "limits": {
                "max_position_pct": self.config.max_position_size_pct,
                "min_confidence": self.config.min_confidence_to_trade,
                "max_drawdown_pct": self.config.max_drawdown_pct,
                "volatility_threshold": self.config.volatility_threshold_pct
            }
        }


    def calculate_risk_of_ruin(
        self,
        win_rate: float,
        risk_per_trade_pct: float,
        risk_reward_ratio: float,
        simulations: int = 1000,
        trades_per_sim: int = 100,
        ruin_threshold_pct: float = 50.0
    ) -> Dict[str, Any]:
        """
        Calculate probability of account ruin using Monte Carlo simulation.

        Args:
            win_rate: Win rate as decimal (0.60 = 60%)
            risk_per_trade_pct: Risk per trade as % of portfolio (e.g., 2.0)
            risk_reward_ratio: Average win / average loss
            simulations: Number of Monte Carlo simulations
            trades_per_sim: Number of trades per simulation
            ruin_threshold_pct: Account % loss that constitutes "ruin"

        Returns:
            Dictionary with risk of ruin analysis:
            - risk_of_ruin_pct: Probability of hitting ruin threshold
            - median_outcome_pct: Median portfolio change %
            - worst_outcome_pct: Worst case portfolio change %
            - best_outcome_pct: Best case portfolio change %
            - kelly_criterion: Optimal position size by Kelly formula
        """
        import random

        if win_rate <= 0 or win_rate >= 1:
            return {'error': 'Win rate must be between 0 and 1'}
        if risk_per_trade_pct <= 0:
            return {'error': 'Risk per trade must be positive'}
        if risk_reward_ratio <= 0:
            return {'error': 'Risk reward ratio must be positive'}

        # Calculate Kelly Criterion: f* = (bp - q) / b
        # where b = risk_reward_ratio, p = win_rate, q = 1 - win_rate
        b = risk_reward_ratio
        p = win_rate
        q = 1 - win_rate
        kelly_fraction = (b * p - q) / b if b > 0 else 0
        kelly_pct = max(0, kelly_fraction * 100)

        # Run Monte Carlo simulations
        final_balances = []
        ruin_count = 0

        for _ in range(simulations):
            balance = 100.0  # Start with 100 units

            for _ in range(trades_per_sim):
                if balance <= (100 - ruin_threshold_pct):
                    ruin_count += 1
                    break

                # Determine win or loss
                if random.random() < win_rate:
                    # Win: gain risk_per_trade * risk_reward_ratio
                    balance += (risk_per_trade_pct * risk_reward_ratio)
                else:
                    # Loss: lose risk_per_trade
                    balance -= risk_per_trade_pct

            final_balances.append(balance)

        # Calculate statistics
        final_balances.sort()
        risk_of_ruin = (ruin_count / simulations) * 100
        median_outcome = final_balances[len(final_balances) // 2] - 100
        worst_outcome = final_balances[0] - 100
        best_outcome = final_balances[-1] - 100
        percentile_5 = final_balances[int(simulations * 0.05)] - 100
        percentile_95 = final_balances[int(simulations * 0.95)] - 100

        logger.info(
            f'{{"event":"risk_of_ruin_calculated",'
            f'"win_rate":{win_rate},"risk_pct":{risk_per_trade_pct},'
            f'"rr_ratio":{risk_reward_ratio},"risk_of_ruin":{risk_of_ruin:.2f}}}'
        )

        return {
            'risk_of_ruin_pct': round(risk_of_ruin, 2),
            'median_outcome_pct': round(median_outcome, 2),
            'worst_outcome_pct': round(worst_outcome, 2),
            'best_outcome_pct': round(best_outcome, 2),
            'percentile_5_pct': round(percentile_5, 2),
            'percentile_95_pct': round(percentile_95, 2),
            'kelly_criterion_pct': round(kelly_pct, 2),
            'recommended_position_pct': round(kelly_pct * 0.5, 2),  # Half-Kelly is safer
            'simulations': simulations,
            'trades_per_sim': trades_per_sim,
            'ruin_threshold_pct': ruin_threshold_pct,
            'inputs': {
                'win_rate': win_rate,
                'risk_per_trade_pct': risk_per_trade_pct,
                'risk_reward_ratio': risk_reward_ratio
            }
        }

    def analyze_concentration_risk(self) -> Dict[str, Any]:
        """
        Analyze portfolio concentration risk by asset correlation groups.

        Returns:
            Dictionary with concentration analysis:
            - exposure_by_asset: Notional exposure per asset
            - exposure_by_group: Exposure by correlated groups (BTC-related, ETH-related, etc.)
            - concentration_warnings: Alerts if over-concentrated
            - largest_position_pct: Largest single position as % of total
        """
        try:
            # Get all open positions
            query = text("""
                SELECT
                    symbol,
                    action,
                    entry_price,
                    quantity,
                    (entry_price * quantity) as notional_value
                FROM trading_predictions.trade_outcomes
                WHERE status = 'open'
            """)

            result = self.session.execute(query).fetchall()

            if not result:
                return {
                    'total_open_positions': 0,
                    'total_notional': 0,
                    'exposure_by_asset': {},
                    'exposure_by_group': {},
                    'concentration_warnings': [],
                    'largest_position_pct': 0
                }

            # Define correlation groups
            # Assets in the same group tend to move together
            correlation_groups = {
                'BTC': ['BTC/USDT', 'BTC/USD', 'WBTC/USDT'],
                'ETH': ['ETH/USDT', 'ETH/USD', 'WETH/USDT', 'STETH/USDT'],
                'ALT_L1': ['SOL/USDT', 'ADA/USDT', 'AVAX/USDT', 'DOT/USDT', 'NEAR/USDT'],
                'DEFI': ['UNI/USDT', 'AAVE/USDT', 'LINK/USDT', 'MKR/USDT'],
                'MEME': ['DOGE/USDT', 'SHIB/USDT', 'PEPE/USDT', 'BONK/USDT'],
            }

            # Calculate exposures
            exposure_by_asset = {}
            exposure_by_group = {}
            total_notional = 0.0

            for row in result:
                symbol = row[0]
                action = row[1]
                notional = float(row[4]) if row[4] else 0.0

                # Direction-aware exposure (longs positive, shorts negative)
                direction = 1 if action == 'buy' else -1
                directed_notional = notional * direction

                exposure_by_asset[symbol] = exposure_by_asset.get(symbol, 0.0) + directed_notional
                total_notional += notional

                # Find group
                assigned_group = 'OTHER'
                for group, symbols in correlation_groups.items():
                    if symbol in symbols:
                        assigned_group = group
                        break

                exposure_by_group[assigned_group] = exposure_by_group.get(assigned_group, 0.0) + directed_notional

            # Calculate concentration warnings
            warnings = []

            # Check single asset concentration
            for asset, exposure in exposure_by_asset.items():
                pct = (abs(exposure) / total_notional * 100) if total_notional > 0 else 0
                if pct > 50:
                    warnings.append(f"HIGH: {asset} is {pct:.1f}% of portfolio (>50%)")
                elif pct > 30:
                    warnings.append(f"MEDIUM: {asset} is {pct:.1f}% of portfolio (>30%)")

            # Check group concentration
            for group, exposure in exposure_by_group.items():
                pct = (abs(exposure) / total_notional * 100) if total_notional > 0 else 0
                if pct > 70:
                    warnings.append(f"HIGH: {group} group is {pct:.1f}% of portfolio (>70%)")
                elif pct > 50:
                    warnings.append(f"MEDIUM: {group} group is {pct:.1f}% of portfolio (>50%)")

            # Find largest position
            largest_pct = 0
            if exposure_by_asset and total_notional > 0:
                largest_pct = max(abs(e) for e in exposure_by_asset.values()) / total_notional * 100

            logger.info(
                f'{{"event":"concentration_risk_analyzed",'
                f'"positions":{len(result)},"warnings":{len(warnings)},'
                f'"total_notional":{total_notional:.2f}}}'
            )

            return {
                'total_open_positions': len(result),
                'total_notional': round(total_notional, 2),
                'exposure_by_asset': {k: round(v, 2) for k, v in exposure_by_asset.items()},
                'exposure_by_group': {k: round(v, 2) for k, v in exposure_by_group.items()},
                'concentration_warnings': warnings,
                'largest_position_pct': round(largest_pct, 2)
            }

        except Exception as e:
            logger.error(f'{{"event":"concentration_analysis_failed","error":"{str(e)}"}}')
            return {
                'error': str(e),
                'total_open_positions': 0,
                'exposure_by_asset': {},
                'exposure_by_group': {},
                'concentration_warnings': [],
                'largest_position_pct': 0
            }


def assess_signal_risk(
    session: Session,
    symbol: str,
    confidence: float,
    volatility_24h: Optional[float] = None
) -> Dict[str, Any]:
    """
    Convenience function to assess risk for a trading signal.

    Args:
        session: Database session
        symbol: Trading symbol
        confidence: Prediction confidence
        volatility_24h: 24h volatility

    Returns:
        Risk assessment dictionary
    """
    service = RiskManagementService(session)
    assessment = service.assess_trade(symbol, confidence, volatility_24h)
    return assessment.to_dict()


def calculate_risk_of_ruin(
    session: Session,
    win_rate: float,
    risk_per_trade_pct: float,
    risk_reward_ratio: float,
    simulations: int = 1000
) -> Dict[str, Any]:
    """
    Convenience function to calculate risk of ruin.

    Args:
        session: Database session
        win_rate: Win rate as decimal
        risk_per_trade_pct: Risk per trade as % of portfolio
        risk_reward_ratio: Average win / average loss
        simulations: Number of Monte Carlo simulations

    Returns:
        Risk of ruin analysis dictionary
    """
    service = RiskManagementService(session)
    return service.calculate_risk_of_ruin(
        win_rate, risk_per_trade_pct, risk_reward_ratio, simulations
    )


def analyze_concentration(session: Session) -> Dict[str, Any]:
    """
    Convenience function to analyze concentration risk.

    Args:
        session: Database session

    Returns:
        Concentration risk analysis dictionary
    """
    service = RiskManagementService(session)
    return service.analyze_concentration_risk()
