"""
SQLAlchemy Models for ClaudeTrader Pro Prediction Tracking

This module defines the database models for storing and tracking AI-generated
trading predictions, accuracy metrics, and API cost analytics.

Author: Database Engineer
Date: 2025-11-11
"""

import os
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any

from sqlalchemy import (
    Column, Integer, String, TIMESTAMP, Numeric, Text, Boolean,
    ForeignKey, CheckConstraint, Index, func
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, validates

Base = declarative_base()


class Prediction(Base):
    """
    Stores AI-generated trading predictions with market context.
    
    Each prediction represents a single call to Claude API with market data,
    resulting in a directional forecast (up/down) with confidence score.
    """
    __tablename__ = 'predictions'
    __table_args__ = (
        CheckConstraint("prediction_type IN ('up', 'down')", name='check_prediction_type'),
        CheckConstraint("confidence >= 0.0 AND confidence <= 1.0", name='check_confidence_range'),
        Index('idx_predictions_symbol_timestamp', 'symbol', 'timestamp'),
        Index('idx_predictions_created_at', 'created_at'),
        Index('idx_predictions_symbol', 'symbol'),
        {'schema': 'trading_predictions'}
    )

    # Primary Key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Prediction Core Fields
    symbol = Column(String(20), nullable=False, comment='Trading pair (e.g., BTC/USDT)')
    timestamp = Column(TIMESTAMP(timezone=True), nullable=False, comment='Prediction timestamp')
    prediction_type = Column(String(10), nullable=False, comment="Direction: 'up' or 'down'")
    confidence = Column(
        Numeric(5, 4), 
        nullable=False, 
        comment='Confidence score (0.0 to 1.0)'
    )
    
    # Context and Metadata
    reasoning = Column(Text, comment='Claude reasoning for prediction')
    market_context = Column(JSONB, comment='Market snapshot from Unified API')
    claude_model = Column(String(50), comment='Claude model version used')
    prompt_version = Column(String(20), comment='Prompt template version')
    
    # Timestamps
    created_at = Column(TIMESTAMP, default=func.now(), comment='Record creation time')
    
    # Relationships
    accuracy_metrics = relationship(
        'AccuracyMetric',
        back_populates='prediction',
        cascade='all, delete-orphan'
    )
    cost_tracking = relationship(
        'CostTracking',
        back_populates='prediction',
        cascade='all, delete-orphan'
    )

    @validates('prediction_type')
    def validate_prediction_type(self, key: str, value: str) -> str:
        """Validate prediction_type is 'up' or 'down'"""
        if value not in ('up', 'down'):
            raise ValueError(f"prediction_type must be 'up' or 'down', got '{value}'")
        return value

    @validates('confidence')
    def validate_confidence(self, key: str, value: Decimal) -> Decimal:
        """Validate confidence is between 0.0 and 1.0"""
        if not (0.0 <= float(value) <= 1.0):
            raise ValueError(f"confidence must be between 0.0 and 1.0, got {value}")
        return value

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary"""
        return {
            'id': self.id,
            'symbol': self.symbol,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'prediction_type': self.prediction_type,
            'confidence': float(self.confidence) if self.confidence else None,
            'reasoning': self.reasoning,
            'market_context': self.market_context,
            'claude_model': self.claude_model,
            'prompt_version': self.prompt_version,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self) -> str:
        return (
            f"<Prediction(id={self.id}, symbol='{self.symbol}', "
            f"type='{self.prediction_type}', confidence={self.confidence})>"
        )


class AccuracyMetric(Base):
    """
    Tracks prediction accuracy over different time horizons.
    
    Evaluates whether predictions were correct by comparing predicted
    direction with actual market movement after specified time periods.
    """
    __tablename__ = 'accuracy_metrics'
    __table_args__ = (
        CheckConstraint("actual_movement IN ('up', 'down')", name='check_actual_movement'),
        Index('idx_accuracy_prediction_id', 'prediction_id'),
        Index('idx_accuracy_correct_evaluated', 'was_correct', 'evaluated_at'),
        Index('idx_accuracy_time_horizon', 'time_horizon_hours'),
        {'schema': 'trading_predictions'}
    )

    # Primary Key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign Key
    prediction_id = Column(
        Integer,
        ForeignKey('trading_predictions.predictions.id', ondelete='CASCADE'),
        nullable=False,
        comment='Reference to prediction'
    )
    
    # Accuracy Metrics
    actual_movement = Column(
        String(10),
        nullable=False,
        comment="Actual market direction: 'up' or 'down'"
    )
    actual_change_pct = Column(
        Numeric(10, 6),
        nullable=False,
        comment='Actual percentage change'
    )
    time_horizon_hours = Column(
        Integer,
        nullable=False,
        comment='Time period evaluated (e.g., 1, 4, 24 hours)'
    )
    was_correct = Column(
        Boolean,
        nullable=False,
        comment='Whether prediction matched actual movement'
    )
    evaluated_at = Column(TIMESTAMP, nullable=False, comment='Evaluation timestamp')
    
    # Relationships
    prediction = relationship('Prediction', back_populates='accuracy_metrics')

    @validates('actual_movement')
    def validate_actual_movement(self, key: str, value: str) -> str:
        """Validate actual_movement is 'up' or 'down'"""
        if value not in ('up', 'down'):
            raise ValueError(f"actual_movement must be 'up' or 'down', got '{value}'")
        return value

    @validates('time_horizon_hours')
    def validate_time_horizon(self, key: str, value: int) -> int:
        """Validate time_horizon_hours is positive"""
        if value <= 0:
            raise ValueError(f"time_horizon_hours must be positive, got {value}")
        return value

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary"""
        return {
            'id': self.id,
            'prediction_id': self.prediction_id,
            'actual_movement': self.actual_movement,
            'actual_change_pct': float(self.actual_change_pct) if self.actual_change_pct else None,
            'time_horizon_hours': self.time_horizon_hours,
            'was_correct': self.was_correct,
            'evaluated_at': self.evaluated_at.isoformat() if self.evaluated_at else None
        }

    def __repr__(self) -> str:
        return (
            f"<AccuracyMetric(id={self.id}, prediction_id={self.prediction_id}, "
            f"correct={self.was_correct}, horizon={self.time_horizon_hours}h)>"
        )


class CostTracking(Base):
    """
    Monitors API usage costs and performance metrics.
    
    Tracks token usage, costs, and latency for each prediction to enable
    cost optimization and performance monitoring.
    """
    __tablename__ = 'cost_tracking'
    __table_args__ = (
        Index('idx_cost_created_at', 'created_at'),
        Index('idx_cost_prediction_id', 'prediction_id'),
        {'schema': 'trading_predictions'}
    )

    # Primary Key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign Key
    prediction_id = Column(
        Integer,
        ForeignKey('trading_predictions.predictions.id', ondelete='CASCADE'),
        nullable=False,
        comment='Reference to prediction'
    )
    
    # Token Usage
    input_tokens = Column(Integer, nullable=False, comment='Input tokens consumed')
    output_tokens = Column(Integer, nullable=False, comment='Output tokens generated')
    cached_tokens = Column(
        Integer,
        default=0,
        comment='Tokens served from cache (cost savings)'
    )
    
    # Cost and Performance
    total_cost_usd = Column(
        Numeric(10, 8),
        nullable=False,
        comment='Total cost in USD'
    )
    api_latency_ms = Column(Integer, comment='API response time in milliseconds')
    
    # Timestamps
    created_at = Column(TIMESTAMP, default=func.now(), comment='Record creation time')
    
    # Relationships
    prediction = relationship('Prediction', back_populates='cost_tracking')

    @validates('input_tokens', 'output_tokens', 'cached_tokens')
    def validate_tokens(self, key: str, value: int) -> int:
        """Validate token counts are non-negative"""
        if value < 0:
            raise ValueError(f"{key} must be non-negative, got {value}")
        return value

    @validates('total_cost_usd')
    def validate_cost(self, key: str, value: Decimal) -> Decimal:
        """Validate cost is non-negative"""
        if float(value) < 0:
            raise ValueError(f"total_cost_usd must be non-negative, got {value}")
        return value

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary"""
        return {
            'id': self.id,
            'prediction_id': self.prediction_id,
            'input_tokens': self.input_tokens,
            'output_tokens': self.output_tokens,
            'cached_tokens': self.cached_tokens,
            'total_cost_usd': float(self.total_cost_usd) if self.total_cost_usd else None,
            'api_latency_ms': self.api_latency_ms,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self) -> str:
        return (
            f"<CostTracking(id={self.id}, prediction_id={self.prediction_id}, "
            f"cost=${self.total_cost_usd}, latency={self.api_latency_ms}ms)>"
        )


# Database connection configuration
class DatabaseConfig:
    """
    Database connection configuration for ClaudeTrader Pro.
    
    Connection string format:
    postgresql://username:password@host:port/database
    """
    
    # Default connection parameters
    DEFAULT_HOST = os.getenv('POSTGRES_HOST', 'postgres')
    DEFAULT_PORT = int(os.getenv('POSTGRES_PORT', '5432'))
    DEFAULT_USER = os.getenv('POSTGRES_USER', 'hercules')
    DEFAULT_DATABASE = os.getenv('POSTGRES_DB', 'hercules_db')
    # NO DEFAULT PASSWORD - must be set via environment variable

    @classmethod
    def get_connection_string(
        cls,
        host: Optional[str] = None,
        port: Optional[int] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None
    ) -> str:
        """
        Generate PostgreSQL connection string.

        Args:
            host: Database host (default: postgres)
            port: Database port (default: 5432)
            user: Database user (default: hercules)
            password: Database password (REQUIRED from env)
            database: Database name (default: hercules_db)

        Returns:
            PostgreSQL connection string

        Raises:
            ValueError: If POSTGRES_PASSWORD environment variable is not set
        """
        host = host or cls.DEFAULT_HOST
        port = port or cls.DEFAULT_PORT
        user = user or cls.DEFAULT_USER
        database = database or cls.DEFAULT_DATABASE

        # Password MUST be provided or from environment - no default allowed
        password = password or os.getenv('POSTGRES_PASSWORD')
        if not password:
            raise ValueError("POSTGRES_PASSWORD environment variable is required")

        return f"postgresql://{user}:{password}@{host}:{port}/{database}"
    
    @classmethod
    def get_async_connection_string(cls, **kwargs) -> str:
        """
        Generate async PostgreSQL connection string (for asyncpg).
        
        Returns:
            PostgreSQL+asyncpg connection string
        """
        base_url = cls.get_connection_string(**kwargs)
        return base_url.replace('postgresql://', 'postgresql+asyncpg://')


# Example usage and helper functions
def create_all_tables(engine):
    """
    Create all tables in the database.
    
    Args:
        engine: SQLAlchemy engine instance
    """
    Base.metadata.create_all(engine)


def drop_all_tables(engine):
    """
    Drop all tables from the database.
    
    WARNING: This will delete all data!
    
    Args:
        engine: SQLAlchemy engine instance
    """
    Base.metadata.drop_all(engine)
