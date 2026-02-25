"""
Backtesting Service - Historical Prediction Analysis

Runs backtests on historical predictions to evaluate trading strategy performance.

Features:
- Historical prediction analysis
- Win rate calculation
- P&L simulation
- Max drawdown tracking
- Sharpe ratio estimation

Author: AI Integration Specialist
Date: 2026-01-18
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional, List, Dict
import statistics

from sqlalchemy import and_, desc, text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Configuration
BACKTEST_DEFAULT_DAYS = int(os.getenv('BACKTEST_DEFAULT_DAYS', '30'))
BACKTEST_POSITION_SIZE_PCT = float(os.getenv('BACKTEST_POSITION_SIZE_PCT', '0.02'))
BACKTEST_STARTING_CAPITAL = float(os.getenv('BACKTEST_STARTING_CAPITAL', '10000'))
BACKTEST_CONFIDENCE_THRESHOLD = float(os.getenv('BACKTEST_CONFIDENCE_THRESHOLD', '0.70'))


@dataclass
class BacktestResult:
    """Result of a backtest run."""
    period_days: int
    start_date: datetime
    end_date: datetime
    symbols: List[str]
    starting_capital: float
    ending_capital: float
    total_predictions: int
    executed_predictions: int
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: Optional[float] = None
    total_pnl: float = 0.0
    total_pnl_percent: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_percent: float = 0.0
    sharpe_ratio: Optional[float] = None
    avg_win: Optional[float] = None
    avg_loss: Optional[float] = None
    profit_factor: Optional[float] = None
    expectancy: Optional[float] = None
    trades: List[Dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "period_days": self.period_days,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "symbols": self.symbols,
            "starting_capital": self.starting_capital,
            "ending_capital": round(self.ending_capital, 2),
            "total_predictions": self.total_predictions,
            "executed_predictions": self.executed_predictions,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": round(self.win_rate, 2) if self.win_rate else None,
            "total_pnl": round(self.total_pnl, 2),
            "total_pnl_percent": round(self.total_pnl_percent, 2),
            "max_drawdown": round(self.max_drawdown, 2),
            "max_drawdown_percent": round(self.max_drawdown_percent, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 2) if self.sharpe_ratio else None,
            "avg_win": round(self.avg_win, 2) if self.avg_win else None,
            "avg_loss": round(self.avg_loss, 2) if self.avg_loss else None,
            "profit_factor": round(self.profit_factor, 2) if self.profit_factor else None,
            "expectancy": round(self.expectancy, 2) if self.expectancy else None,
            "trades_count": len(self.trades)
        }


class BacktestingService:
    """
    Runs backtests on historical predictions.

    Usage:
        service = BacktestingService(db_session)
        result = service.run_backtest(days=30)
    """

    def __init__(
        self,
        db_session: Session,
        starting_capital: float = BACKTEST_STARTING_CAPITAL,
        position_size_pct: float = BACKTEST_POSITION_SIZE_PCT,
        confidence_threshold: float = BACKTEST_CONFIDENCE_THRESHOLD
    ):
        self.db = db_session
        self.starting_capital = starting_capital
        self.position_size_pct = position_size_pct
        self.confidence_threshold = confidence_threshold

    def run_backtest(
        self,
        days: int = BACKTEST_DEFAULT_DAYS,
        symbols: Optional[List[str]] = None
    ) -> BacktestResult:
        """
        Run backtest on historical predictions.

        Args:
            days: Number of days to analyze
            symbols: List of symbols to include (None = all)

        Returns:
            BacktestResult with performance metrics
        """
        from app.models import AutomatedPrediction

        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)

        if symbols is None:
            symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'XRP/USDT', 'BNB/USDT']

        logger.info(
            f'{{"event":"backtest_started",'
            f'"days":{days},'
            f'"symbols":"{symbols}",'
            f'"start_date":"{start_date.isoformat()}",'
            f'"end_date":"{end_date.isoformat()}"}}'
        )

        # Get historical predictions
        query = self.db.query(AutomatedPrediction).filter(
            and_(
                AutomatedPrediction.created_at >= start_date,
                AutomatedPrediction.created_at <= end_date,
                AutomatedPrediction.symbol.in_(symbols)
            )
        ).order_by(AutomatedPrediction.created_at)

        predictions = query.all()
        total_predictions = len(predictions)

        if total_predictions == 0:
            logger.warning(
                f'{{"event":"backtest_no_predictions",'
                f'"days":{days},'
                f'"symbols":"{symbols}"}}'
            )
            return BacktestResult(
                period_days=days,
                start_date=start_date,
                end_date=end_date,
                symbols=symbols,
                starting_capital=self.starting_capital,
                ending_capital=self.starting_capital,
                total_predictions=0,
                executed_predictions=0,
                total_trades=0,
                winning_trades=0,
                losing_trades=0
            )

        # Simulate trades
        capital = self.starting_capital
        peak_capital = capital
        max_drawdown = 0.0
        trades = []
        daily_returns = []
        executed_count = 0

        for pred in predictions:
            confidence = float(pred.confidence)

            # Skip if below threshold
            if confidence < self.confidence_threshold:
                continue

            executed_count += 1

            # Calculate position size
            position_size = capital * self.position_size_pct

            # Simulate trade outcome based on was_correct flag
            if pred.was_correct is not None:
                # Use actual outcome
                is_win = pred.was_correct
            else:
                # No outcome yet - skip for accurate backtest
                continue

            # Simulate P&L (simplified)
            if is_win:
                # Average win is ~2% for crypto
                pnl_pct = 0.02 * confidence  # Scale by confidence
                pnl = position_size * pnl_pct
            else:
                # Average loss is ~1.5% for crypto
                pnl_pct = -0.015 * (1 / confidence)  # Inverse scale
                pnl = position_size * pnl_pct

            capital += pnl
            daily_returns.append(pnl / (capital - pnl) * 100)

            # Track max drawdown
            if capital > peak_capital:
                peak_capital = capital
            drawdown = peak_capital - capital
            if drawdown > max_drawdown:
                max_drawdown = drawdown

            trades.append({
                "date": pred.created_at.isoformat(),
                "symbol": pred.symbol,
                "prediction": pred.prediction_type,
                "confidence": confidence,
                "position_size": round(position_size, 2),
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct * 100, 2),
                "capital": round(capital, 2),
                "is_win": is_win
            })

        # Calculate statistics
        winning_trades = [t for t in trades if t["is_win"]]
        losing_trades = [t for t in trades if not t["is_win"]]
        num_wins = len(winning_trades)
        num_losses = len(losing_trades)
        total_trades = num_wins + num_losses

        win_rate = (num_wins / total_trades * 100) if total_trades > 0 else None
        total_pnl = capital - self.starting_capital
        total_pnl_pct = (total_pnl / self.starting_capital) * 100

        # Average win/loss
        avg_win = statistics.mean([t["pnl"] for t in winning_trades]) if winning_trades else None
        avg_loss = statistics.mean([t["pnl"] for t in losing_trades]) if losing_trades else None

        # Profit factor
        gross_profit = sum([t["pnl"] for t in winning_trades]) if winning_trades else 0
        gross_loss = abs(sum([t["pnl"] for t in losing_trades])) if losing_trades else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else None

        # Expectancy
        if win_rate and avg_win and avg_loss:
            expectancy = (win_rate / 100 * avg_win) - ((100 - win_rate) / 100 * abs(avg_loss))
        else:
            expectancy = None

        # Sharpe ratio (simplified)
        sharpe = None
        if len(daily_returns) > 1:
            avg_return = statistics.mean(daily_returns)
            std_return = statistics.stdev(daily_returns)
            if std_return > 0:
                # Annualized (assuming daily data)
                sharpe = (avg_return / std_return) * (252 ** 0.5)

        max_dd_pct = (max_drawdown / peak_capital * 100) if peak_capital > 0 else 0

        logger.info(
            f'{{"event":"backtest_completed",'
            f'"total_predictions":{total_predictions},'
            f'"executed":{executed_count},'
            f'"trades":{total_trades},'
            f'"win_rate":{win_rate},'
            f'"total_pnl":{total_pnl:.2f},'
            f'"sharpe":{sharpe}}}'
        )

        return BacktestResult(
            period_days=days,
            start_date=start_date,
            end_date=end_date,
            symbols=symbols,
            starting_capital=self.starting_capital,
            ending_capital=capital,
            total_predictions=total_predictions,
            executed_predictions=executed_count,
            total_trades=total_trades,
            winning_trades=num_wins,
            losing_trades=num_losses,
            win_rate=win_rate,
            total_pnl=total_pnl,
            total_pnl_percent=total_pnl_pct,
            max_drawdown=max_drawdown,
            max_drawdown_percent=max_dd_pct,
            sharpe_ratio=sharpe,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            expectancy=expectancy,
            trades=trades[-100:]  # Last 100 trades for detail
        )

    def get_prediction_accuracy_by_symbol(
        self,
        days: int = 30
    ) -> Dict[str, Dict]:
        """
        Get prediction accuracy broken down by symbol.

        Returns:
            Dict with accuracy metrics per symbol
        """
        from app.models import AutomatedPrediction

        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)

        query = text("""
            SELECT
                symbol,
                COUNT(*) as total_predictions,
                SUM(CASE WHEN was_correct THEN 1 ELSE 0 END) as correct,
                SUM(CASE WHEN was_correct = false THEN 1 ELSE 0 END) as incorrect,
                AVG(CASE WHEN was_correct THEN confidence ELSE NULL END) as avg_confidence_correct,
                AVG(CASE WHEN was_correct = false THEN confidence ELSE NULL END) as avg_confidence_incorrect
            FROM trading_predictions.automated_predictions
            WHERE created_at >= :start_date
              AND created_at <= :end_date
              AND was_correct IS NOT NULL
            GROUP BY symbol
            ORDER BY symbol
        """)

        result = self.db.execute(query, {
            "start_date": start_date,
            "end_date": end_date
        })

        accuracy_by_symbol = {}
        for row in result:
            symbol = row[0]
            total = row[1]
            correct = row[2] or 0
            incorrect = row[3] or 0

            accuracy_by_symbol[symbol] = {
                "total_predictions": total,
                "correct": correct,
                "incorrect": incorrect,
                "accuracy_pct": round((correct / total * 100), 2) if total > 0 else 0,
                "avg_confidence_correct": round(float(row[4] or 0) * 100, 2),
                "avg_confidence_incorrect": round(float(row[5] or 0) * 100, 2)
            }

        return accuracy_by_symbol

    def get_confidence_calibration(
        self,
        days: int = 30
    ) -> List[Dict]:
        """
        Get confidence calibration data (predicted vs actual accuracy).

        Returns:
            List of calibration buckets
        """
        from app.models import AutomatedPrediction

        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)

        query = text("""
            SELECT
                FLOOR(confidence * 10) * 10 as confidence_bucket,
                COUNT(*) as total,
                SUM(CASE WHEN was_correct THEN 1 ELSE 0 END) as correct
            FROM trading_predictions.automated_predictions
            WHERE created_at >= :start_date
              AND created_at <= :end_date
              AND was_correct IS NOT NULL
            GROUP BY confidence_bucket
            ORDER BY confidence_bucket
        """)

        result = self.db.execute(query, {
            "start_date": start_date,
            "end_date": end_date
        })

        calibration = []
        for row in result:
            bucket = int(row[0])
            total = row[1]
            correct = row[2] or 0
            actual_accuracy = (correct / total * 100) if total > 0 else 0

            calibration.append({
                "confidence_range": f"{bucket}-{bucket + 10}%",
                "predicted_accuracy": bucket + 5,  # Midpoint
                "actual_accuracy": round(actual_accuracy, 2),
                "sample_size": total,
                "calibration_error": round(abs((bucket + 5) - actual_accuracy), 2)
            })

        return calibration
