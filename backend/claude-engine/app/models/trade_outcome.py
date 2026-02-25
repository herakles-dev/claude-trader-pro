"""
Trade Outcome Model - Records trade executions from OctoBot

Used for:
- Tracking actual trade results from signals
- Calculating real-world prediction accuracy
- Analyzing signal-to-execution performance

Author: Database Engineer
Date: 2026-01-14
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any
from uuid import uuid4

from sqlalchemy import (
    Column, String, Float, TIMESTAMP, ForeignKey, Boolean,
    CheckConstraint, Index, Numeric, func
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, validates

from app.models.prediction import Base


class TradeOutcome(Base):
    """
    Records trade outcomes from OctoBot executions.

    Each trade outcome represents a signal that was executed by OctoBot,
    tracking entry/exit prices, profit/loss, and execution status.
    """
    __tablename__ = 'trade_outcomes'
    __table_args__ = (
        CheckConstraint(
            "action IN ('buy', 'sell')",
            name='trade_outcomes_action_check'
        ),
        CheckConstraint(
            "status IN ('open', 'closed', 'cancelled')",
            name='trade_outcomes_status_check'
        ),
        Index('idx_trade_outcomes_symbol', 'symbol'),
        Index('idx_trade_outcomes_signal_id', 'signal_id'),
        Index('idx_trade_outcomes_status', 'status'),
        Index('idx_trade_outcomes_executed_at', 'executed_at'),
        Index('idx_trade_outcomes_cycle_id', 'cycle_id'),
        {'schema': 'trading_predictions'}
    )

    # Primary Key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment='Unique trade outcome identifier'
    )

    # Signal Reference
    signal_id = Column(
        String(100),
        nullable=False,
        unique=True,
        comment='Signal ID from OctoBot (cycle_id from signal)'
    )
    cycle_id = Column(
        UUID(as_uuid=True),
        ForeignKey('trading_predictions.prediction_cycles.id', ondelete='SET NULL'),
        nullable=True,
        comment='Reference to prediction cycle'
    )

    # Trade Details
    symbol = Column(
        String(20),
        nullable=False,
        comment='Trading pair (e.g., BTC/USDT)'
    )
    action = Column(
        String(10),
        nullable=False,
        comment="Trade action: 'buy' or 'sell'"
    )
    entry_price = Column(
        Numeric(20, 8),
        nullable=False,
        comment='Entry price at execution'
    )
    exit_price = Column(
        Numeric(20, 8),
        nullable=True,
        comment='Exit price when closed'
    )
    quantity = Column(
        Numeric(20, 8),
        nullable=False,
        comment='Trade quantity'
    )
    pnl = Column(
        Numeric(20, 8),
        nullable=True,
        comment='Profit/Loss in quote currency'
    )
    pnl_percent = Column(
        Float,
        nullable=True,
        comment='Percentage profit/loss'
    )

    # Status Tracking
    status = Column(
        String(20),
        nullable=False,
        default='open',
        comment="Trade status: 'open', 'closed', 'cancelled'"
    )
    executed_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        comment='Trade execution timestamp'
    )
    closed_at = Column(
        TIMESTAMP(timezone=True),
        nullable=True,
        comment='Trade close timestamp'
    )

    # OctoBot Metadata
    octobot_order_id = Column(
        String(100),
        nullable=True,
        comment='OctoBot order identifier'
    )
    exchange = Column(
        String(50),
        nullable=True,
        comment='Exchange where trade was executed'
    )

    # OctoBot Sync Tracking
    was_auto_executed = Column(
        Boolean,
        nullable=True,
        comment='True if executed by scheduler, False if manual trigger'
    )
    execution_confidence = Column(
        Float,
        nullable=True,
        comment='AI prediction confidence at time of execution (0.0-1.0)'
    )
    octobot_synced_at = Column(
        TIMESTAMP(timezone=True),
        nullable=True,
        comment='Timestamp of last sync from OctoBot'
    )
    octobot_raw_data = Column(
        JSONB,
        nullable=True,
        comment='Raw order data from OctoBot for debugging'
    )

    # Fee Tracking - Entry
    entry_fee_cost = Column(
        Numeric(20, 8),
        nullable=True,
        comment='Fee paid on entry trade in quote currency'
    )
    entry_fee_rate = Column(
        Numeric(10, 8),
        nullable=True,
        comment='Fee rate on entry (e.g., 0.001 for 0.1%)'
    )
    entry_fee_type = Column(
        String(10),
        nullable=True,
        comment='Fee type: maker or taker'
    )

    # Fee Tracking - Exit
    exit_fee_cost = Column(
        Numeric(20, 8),
        nullable=True,
        comment='Fee paid on exit trade in quote currency'
    )
    exit_fee_rate = Column(
        Numeric(10, 8),
        nullable=True,
        comment='Fee rate on exit (e.g., 0.001 for 0.1%)'
    )
    exit_fee_type = Column(
        String(10),
        nullable=True,
        comment='Fee type: maker or taker'
    )

    # Fee Aggregates
    total_fees = Column(
        Numeric(20, 8),
        nullable=True,
        comment='Sum of entry and exit fees'
    )
    net_pnl = Column(
        Numeric(20, 8),
        nullable=True,
        comment='Gross P&L minus total fees'
    )
    net_pnl_percent = Column(
        Float,
        nullable=True,
        comment='Net P&L as percentage of entry value'
    )

    # Risk Management Fields
    stop_loss_price = Column(
        Numeric(20, 8),
        nullable=True,
        comment='Price at which to exit for loss protection'
    )
    take_profit_price = Column(
        Numeric(20, 8),
        nullable=True,
        comment='Target price for taking profits'
    )
    risk_amount = Column(
        Numeric(20, 8),
        nullable=True,
        comment='Dollar amount at risk: (entry_price - stop_loss) × quantity'
    )

    # Audit Fields
    created_at = Column(
        TIMESTAMP(timezone=True),
        default=func.now(),
        comment='Record creation time'
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        default=func.now(),
        onupdate=func.now(),
        comment='Record last update time'
    )

    # Relationships
    cycle = relationship(
        'PredictionCycle',
        back_populates='trade_outcomes'
    )

    @validates('action')
    def validate_action(self, key: str, value: str) -> str:
        """Validate action is 'buy' or 'sell'"""
        if value not in ('buy', 'sell'):
            raise ValueError(f"action must be 'buy' or 'sell', got '{value}'")
        return value

    @validates('status')
    def validate_status(self, key: str, value: str) -> str:
        """Validate status is one of the allowed values"""
        allowed_statuses = ('open', 'closed', 'cancelled')
        if value not in allowed_statuses:
            raise ValueError(
                f"status must be one of {allowed_statuses}, got '{value}'"
            )
        return value

    @validates('entry_price', 'quantity')
    def validate_positive_decimal(self, key: str, value: Decimal) -> Decimal:
        """Validate entry_price and quantity are positive"""
        if value is not None and float(value) <= 0:
            raise ValueError(f"{key} must be positive, got {value}")
        return value

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary for JSON serialization"""
        return {
            'id': str(self.id),
            'signal_id': self.signal_id,
            'cycle_id': str(self.cycle_id) if self.cycle_id else None,
            'symbol': self.symbol,
            'action': self.action,
            'entry_price': float(self.entry_price) if self.entry_price else None,
            'exit_price': float(self.exit_price) if self.exit_price else None,
            'quantity': float(self.quantity) if self.quantity else None,
            'pnl': float(self.pnl) if self.pnl else None,
            'pnl_percent': self.pnl_percent,
            # Fee tracking fields
            'entry_fee_cost': float(self.entry_fee_cost) if self.entry_fee_cost else None,
            'entry_fee_rate': float(self.entry_fee_rate) if self.entry_fee_rate else None,
            'entry_fee_type': self.entry_fee_type,
            'exit_fee_cost': float(self.exit_fee_cost) if self.exit_fee_cost else None,
            'exit_fee_rate': float(self.exit_fee_rate) if self.exit_fee_rate else None,
            'exit_fee_type': self.exit_fee_type,
            'total_fees': float(self.total_fees) if self.total_fees else None,
            'net_pnl': float(self.net_pnl) if self.net_pnl else None,
            'net_pnl_percent': self.net_pnl_percent,
            # Risk management fields
            'stop_loss_price': float(self.stop_loss_price) if self.stop_loss_price else None,
            'take_profit_price': float(self.take_profit_price) if self.take_profit_price else None,
            'risk_amount': float(self.risk_amount) if self.risk_amount else None,
            # Status and timestamps
            'status': self.status,
            'executed_at': self.executed_at.isoformat() if self.executed_at else None,
            'closed_at': self.closed_at.isoformat() if self.closed_at else None,
            'octobot_order_id': self.octobot_order_id,
            'exchange': self.exchange,
            # OctoBot sync tracking
            'was_auto_executed': self.was_auto_executed,
            'execution_confidence': self.execution_confidence,
            'octobot_synced_at': self.octobot_synced_at.isoformat() if self.octobot_synced_at else None,
            # Timestamps
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def __repr__(self) -> str:
        return (
            f"<TradeOutcome(id={self.id}, signal={self.signal_id}, "
            f"action='{self.action}', pnl={self.pnl})>"
        )


# Helper functions
def get_trade_outcomes_by_cycle(
    db_session,
    cycle_id: str,
) -> list:
    """
    Get all trade outcomes for a specific cycle.

    Args:
        db_session: SQLAlchemy database session
        cycle_id: Prediction cycle UUID

    Returns:
        List of TradeOutcome instances
    """
    return db_session.query(TradeOutcome).filter(
        TradeOutcome.cycle_id == cycle_id
    ).order_by(TradeOutcome.executed_at.desc()).all()


def get_open_trades(
    db_session,
    symbol: Optional[str] = None
) -> list:
    """
    Get all open trades.

    Args:
        db_session: SQLAlchemy database session
        symbol: Optional symbol filter

    Returns:
        List of open TradeOutcome instances
    """
    query = db_session.query(TradeOutcome).filter(
        TradeOutcome.status == 'open'
    )

    if symbol:
        query = query.filter(TradeOutcome.symbol == symbol)

    return query.order_by(TradeOutcome.executed_at.desc()).all()


def get_trade_statistics(
    db_session,
    symbol: Optional[str] = None,
    days: int = 30
) -> Dict[str, Any]:
    """
    Calculate trade statistics including fee data and professional risk metrics.

    Args:
        db_session: SQLAlchemy database session
        symbol: Optional symbol filter
        days: Number of days to analyze

    Returns:
        Dictionary with trade statistics including:
        - Gross/Net P&L and fees
        - Profit Factor (gross_profit / gross_loss)
        - Average Win/Loss size
        - Risk/Reward Ratio
        - Expectancy
        - Fee Efficiency
    """
    from datetime import timedelta
    from sqlalchemy import func as sql_func, case

    cutoff_date = datetime.utcnow() - timedelta(days=days)

    # Main query with win/loss aggregations
    query = db_session.query(
        sql_func.count(TradeOutcome.id).label('total_trades'),
        sql_func.sum(TradeOutcome.pnl).label('total_pnl'),
        sql_func.sum(TradeOutcome.net_pnl).label('total_net_pnl'),
        sql_func.sum(TradeOutcome.total_fees).label('total_fees_paid'),
        sql_func.avg(TradeOutcome.pnl_percent).label('avg_pnl_percent'),
        sql_func.avg(TradeOutcome.net_pnl_percent).label('avg_net_pnl_percent'),
        sql_func.avg(TradeOutcome.total_fees).label('avg_fee_per_trade'),
        sql_func.count(
            sql_func.nullif(TradeOutcome.pnl > 0, False)
        ).label('winning_trades'),
        sql_func.count(
            sql_func.nullif(TradeOutcome.pnl < 0, False)
        ).label('losing_trades'),
        sql_func.count(
            sql_func.nullif(TradeOutcome.net_pnl > 0, False)
        ).label('net_winning_trades'),
        sql_func.count(
            sql_func.nullif(TradeOutcome.net_pnl < 0, False)
        ).label('net_losing_trades'),
        # Professional metrics: Gross Profit/Loss sums
        sql_func.sum(
            case((TradeOutcome.pnl > 0, TradeOutcome.pnl), else_=0)
        ).label('gross_profit'),
        sql_func.sum(
            case((TradeOutcome.pnl < 0, sql_func.abs(TradeOutcome.pnl)), else_=0)
        ).label('gross_loss'),
        # Average Win/Loss sizes
        sql_func.avg(
            case((TradeOutcome.pnl > 0, TradeOutcome.pnl), else_=None)
        ).label('avg_win'),
        sql_func.avg(
            case((TradeOutcome.pnl < 0, sql_func.abs(TradeOutcome.pnl)), else_=None)
        ).label('avg_loss'),
        # Average Win/Loss percentages
        sql_func.avg(
            case((TradeOutcome.pnl > 0, TradeOutcome.pnl_percent), else_=None)
        ).label('avg_win_pct'),
        sql_func.avg(
            case((TradeOutcome.pnl < 0, sql_func.abs(TradeOutcome.pnl_percent)), else_=None)
        ).label('avg_loss_pct'),
    ).filter(
        TradeOutcome.status == 'closed',
        TradeOutcome.executed_at >= cutoff_date
    )

    if symbol:
        query = query.filter(TradeOutcome.symbol == symbol)

    result = query.first()

    total = result.total_trades or 0
    winning = result.winning_trades or 0
    losing = result.losing_trades or 0
    net_winning = result.net_winning_trades or 0

    # Extract professional metrics
    gross_profit = float(result.gross_profit) if result.gross_profit else 0.0
    gross_loss = float(result.gross_loss) if result.gross_loss else 0.0
    avg_win = float(result.avg_win) if result.avg_win else 0.0
    avg_loss = float(result.avg_loss) if result.avg_loss else 0.0
    avg_win_pct = float(result.avg_win_pct) if result.avg_win_pct else 0.0
    avg_loss_pct = float(result.avg_loss_pct) if result.avg_loss_pct else 0.0
    total_fees = float(result.total_fees_paid) if result.total_fees_paid else 0.0

    # Calculate derived metrics
    win_rate = (winning / total * 100) if total > 0 else 0
    loss_rate = (losing / total * 100) if total > 0 else 0
    win_rate_decimal = winning / total if total > 0 else 0
    loss_rate_decimal = losing / total if total > 0 else 0

    # Profit Factor: gross_profit / gross_loss (healthy: 1.75 - 4.0)
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else None

    # Risk/Reward Ratio: avg_win / avg_loss
    risk_reward_ratio = avg_win / avg_loss if avg_loss > 0 else None

    # Expectancy: (WinRate × AvgWin) - (LossRate × AvgLoss)
    # Tells you expected $ per trade
    expectancy = (win_rate_decimal * avg_win) - (loss_rate_decimal * avg_loss) if total > 0 else 0.0

    # Expectancy %: Same formula but using percentages
    expectancy_pct = (win_rate_decimal * avg_win_pct) - (loss_rate_decimal * avg_loss_pct) if total > 0 else 0.0

    # Fee Efficiency: Total Fees / Gross Profit × 100 (target: < 10%)
    fee_efficiency_pct = (total_fees / gross_profit * 100) if gross_profit > 0 else 100.0

    return {
        'total_trades': total,
        'winning_trades': winning,
        'losing_trades': losing,
        'win_rate': win_rate,
        # Gross P&L (before fees)
        'total_pnl': float(result.total_pnl) if result.total_pnl else 0,
        'avg_pnl_percent': float(result.avg_pnl_percent) if result.avg_pnl_percent else 0,
        # Net P&L (after fees)
        'total_net_pnl': float(result.total_net_pnl) if result.total_net_pnl else 0,
        'avg_net_pnl_percent': float(result.avg_net_pnl_percent) if result.avg_net_pnl_percent else 0,
        'net_winning_trades': net_winning,
        'net_losing_trades': result.net_losing_trades or 0,
        'net_win_rate': (net_winning / total * 100) if total > 0 else 0,
        # Fee statistics
        'total_fees_paid': total_fees,
        'avg_fee_per_trade': float(result.avg_fee_per_trade) if result.avg_fee_per_trade else 0,
        'period_days': days,
        # === Professional Risk Metrics ===
        # Profit Factor: Healthy range 1.75 - 4.0
        'gross_profit': gross_profit,
        'gross_loss': gross_loss,
        'profit_factor': round(profit_factor, 3) if profit_factor is not None else None,
        # Win/Loss Sizes
        'avg_win': round(avg_win, 2),
        'avg_loss': round(avg_loss, 2),
        'avg_win_pct': round(avg_win_pct, 2),
        'avg_loss_pct': round(avg_loss_pct, 2),
        # Risk/Reward Ratio
        'risk_reward_ratio': round(risk_reward_ratio, 3) if risk_reward_ratio is not None else None,
        # Expectancy: Expected $ (or %) per trade
        'expectancy': round(expectancy, 2),
        'expectancy_pct': round(expectancy_pct, 2),
        # Fee Efficiency: Target < 10%
        'fee_efficiency_pct': round(fee_efficiency_pct, 2),
    }
