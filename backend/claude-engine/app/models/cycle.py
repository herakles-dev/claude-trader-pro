"""
SQLAlchemy Models for Prediction Cycles and 4-Hour Decisions

This module defines the database models for managing prediction cycles and
their aggregated 4-hour trading decisions.

Author: Backend Architect
Date: 2025-11-12
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any
from uuid import uuid4

from sqlalchemy import (
    Column, Integer, String, TIMESTAMP, Numeric, Text, Boolean,
    CheckConstraint, Index, func, ForeignKey
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, validates

from app.models.prediction import Base


class PredictionCycle(Base):
    """
    Tracks 4-hour prediction cycles.
    
    Each cycle contains 4 hourly predictions that are aggregated into a single
    4-hour trading decision. The cycle tracks the overall status and timing.
    """
    __tablename__ = 'prediction_cycles'
    __table_args__ = (
        CheckConstraint(
            "status IN ('in_progress', 'completed', 'cancelled')",
            name='check_cycle_status'
        ),
        Index('idx_cycles_symbol_started', 'symbol', 'started_at'),
        Index('idx_cycles_status', 'status'),
        Index('idx_cycles_started_at', 'started_at'),
        {'schema': 'trading_predictions'}
    )
    
    # Primary Key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment='Unique cycle identifier'
    )
    
    # Cycle Information
    symbol = Column(
        String(20),
        nullable=False,
        comment='Trading pair (e.g., BTC/USDT)'
    )
    status = Column(
        String(20),
        nullable=False,
        default='in_progress',
        comment="Cycle status: 'in_progress', 'completed', 'cancelled'"
    )
    
    # Timing
    started_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=func.now(),
        comment='Cycle start timestamp'
    )
    completed_at = Column(
        TIMESTAMP(timezone=True),
        nullable=True,
        comment='Cycle completion timestamp'
    )
    
    # Metadata
    prediction_count = Column(
        Integer,
        default=0,
        comment='Number of predictions in cycle (should be 4 when complete)'
    )
    cycle_metadata = Column(
        JSONB,
        comment='Additional cycle metadata'
    )
    
    # Timestamps
    created_at = Column(
        TIMESTAMP,
        default=func.now(),
        comment='Record creation time'
    )
    updated_at = Column(
        TIMESTAMP,
        default=func.now(),
        onupdate=func.now(),
        comment='Record last update time'
    )
    
    # Relationships
    four_hour_decision = relationship(
        'FourHourDecision',
        back_populates='cycle',
        uselist=False,  # One-to-one relationship
        cascade='all, delete-orphan'
    )
    trade_outcomes = relationship(
        'TradeOutcome',
        back_populates='cycle',
        cascade='all, delete-orphan'
    )
    
    @validates('status')
    def validate_status(self, key: str, value: str) -> str:
        """Validate status is one of the allowed values"""
        allowed_statuses = ('in_progress', 'completed', 'cancelled')
        if value not in allowed_statuses:
            raise ValueError(
                f"status must be one of {allowed_statuses}, got '{value}'"
            )
        return value
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary"""
        return {
            'id': str(self.id),
            'symbol': self.symbol,
            'status': self.status,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'prediction_count': self.prediction_count,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self) -> str:
        return (
            f"<PredictionCycle(id={self.id}, symbol='{self.symbol}', "
            f"status='{self.status}', predictions={self.prediction_count})>"
        )


class FourHourDecision(Base):
    """
    Stores aggregated 4-hour trading decisions.
    
    Each decision is the result of aggregating 4 hourly predictions using a
    time-weighted voting algorithm. Stores the final decision, confidence,
    vote breakdown, and detailed reasoning.
    """
    __tablename__ = 'four_hour_decisions'
    __table_args__ = (
        CheckConstraint(
            "final_decision IN ('up', 'down')",
            name='check_final_decision'
        ),
        CheckConstraint(
            "aggregated_confidence >= 0.0 AND aggregated_confidence <= 1.0",
            name='check_aggregated_confidence_range'
        ),
        Index('idx_decisions_cycle_id', 'cycle_id'),
        Index('idx_decisions_symbol_decided', 'symbol', 'decided_at'),
        Index('idx_decisions_decided_at', 'decided_at'),
        {'schema': 'trading_predictions'}
    )
    
    # Primary Key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment='Unique decision identifier'
    )
    
    # Foreign Key
    cycle_id = Column(
        UUID(as_uuid=True),
        ForeignKey('trading_predictions.prediction_cycles.id', ondelete='CASCADE'),
        nullable=False,
        unique=True,  # One decision per cycle
        comment='Reference to prediction cycle'
    )
    
    # Decision Information
    symbol = Column(
        String(20),
        nullable=False,
        comment='Trading pair (e.g., BTC/USDT)'
    )
    final_decision = Column(
        String(10),
        nullable=False,
        comment="Aggregated decision: 'up' or 'down'"
    )
    aggregated_confidence = Column(
        Numeric(5, 4),
        nullable=False,
        comment='Time-weighted confidence score (0.0 to 1.0)'
    )
    
    # Vote Analysis
    vote_breakdown = Column(
        JSONB,
        nullable=False,
        comment='Vote statistics: {up_count, down_count, up_weighted, down_weighted}'
    )
    confidence_stats = Column(
        JSONB,
        nullable=False,
        comment='Confidence statistics: {min, max, avg, std_dev}'
    )
    
    # Reasoning
    decision_reasoning = Column(
        Text,
        nullable=False,
        comment='Human-readable explanation of the decision'
    )
    
    # Timing
    decided_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=func.now(),
        comment='Decision timestamp'
    )
    
    # Timestamps
    created_at = Column(
        TIMESTAMP,
        default=func.now(),
        comment='Record creation time'
    )
    
    # Relationships
    cycle = relationship(
        'PredictionCycle',
        back_populates='four_hour_decision'
    )
    
    @validates('final_decision')
    def validate_final_decision(self, key: str, value: str) -> str:
        """Validate final_decision is 'up' or 'down'"""
        if value not in ('up', 'down'):
            raise ValueError(
                f"final_decision must be 'up' or 'down', got '{value}'"
            )
        return value
    
    @validates('aggregated_confidence')
    def validate_aggregated_confidence(self, key: str, value: Decimal) -> Decimal:
        """Validate aggregated_confidence is between 0.0 and 1.0"""
        if not (0.0 <= float(value) <= 1.0):
            raise ValueError(
                f"aggregated_confidence must be between 0.0 and 1.0, got {value}"
            )
        return value
    
    @validates('vote_breakdown')
    def validate_vote_breakdown(self, key: str, value: Dict) -> Dict:
        """Validate vote_breakdown has required keys"""
        required_keys = {'up_count', 'down_count', 'up_weighted', 'down_weighted'}
        if not all(k in value for k in required_keys):
            raise ValueError(
                f"vote_breakdown must contain keys: {required_keys}"
            )
        return value
    
    @validates('confidence_stats')
    def validate_confidence_stats(self, key: str, value: Dict) -> Dict:
        """Validate confidence_stats has required keys"""
        required_keys = {'min', 'max', 'avg', 'std_dev'}
        if not all(k in value for k in required_keys):
            raise ValueError(
                f"confidence_stats must contain keys: {required_keys}"
            )
        return value
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary"""
        return {
            'id': str(self.id),
            'cycle_id': str(self.cycle_id),
            'symbol': self.symbol,
            'final_decision': self.final_decision,
            'aggregated_confidence': float(self.aggregated_confidence),
            'vote_breakdown': self.vote_breakdown,
            'confidence_stats': self.confidence_stats,
            'decision_reasoning': self.decision_reasoning,
            'decided_at': self.decided_at.isoformat() if self.decided_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self) -> str:
        return (
            f"<FourHourDecision(id={self.id}, cycle_id={self.cycle_id}, "
            f"decision='{self.final_decision}', "
            f"confidence={self.aggregated_confidence})>"
        )


# Helper functions
def create_prediction_cycle(
    db_session,
    symbol: str,
    metadata: Optional[Dict] = None
) -> PredictionCycle:
    """
    Create a new prediction cycle.
    
    Args:
        db_session: SQLAlchemy database session
        symbol: Trading pair (e.g., BTC/USDT)
        metadata: Optional metadata dictionary
        
    Returns:
        Created PredictionCycle instance
    """
    cycle = PredictionCycle(
        symbol=symbol,
        status='in_progress',
        metadata=metadata or {}
    )
    db_session.add(cycle)
    db_session.commit()
    db_session.refresh(cycle)
    return cycle


def get_active_cycle(db_session, symbol: str) -> Optional[PredictionCycle]:
    """
    Get the active (in_progress) cycle for a symbol.
    
    Args:
        db_session: SQLAlchemy database session
        symbol: Trading pair
        
    Returns:
        Active PredictionCycle or None
    """
    return db_session.query(PredictionCycle).filter(
        PredictionCycle.symbol == symbol,
        PredictionCycle.status == 'in_progress'
    ).order_by(PredictionCycle.started_at.desc()).first()


def get_completed_cycles(
    db_session,
    symbol: Optional[str] = None,
    limit: int = 100
) -> list:
    """
    Get completed prediction cycles.
    
    Args:
        db_session: SQLAlchemy database session
        symbol: Optional symbol filter
        limit: Maximum number of cycles to return
        
    Returns:
        List of completed PredictionCycle instances
    """
    query = db_session.query(PredictionCycle).filter(
        PredictionCycle.status == 'completed'
    )
    
    if symbol:
        query = query.filter(PredictionCycle.symbol == symbol)
    
    return query.order_by(
        PredictionCycle.completed_at.desc()
    ).limit(limit).all()
