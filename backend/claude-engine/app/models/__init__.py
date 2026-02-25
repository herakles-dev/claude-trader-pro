"""
Database Models Package for ClaudeTrader Pro

This package provides SQLAlchemy models and database utilities for the
ClaudeTrader Pro prediction tracking system.

Usage:
    from app.models import Prediction, AccuracyMetric, CostTracking
    from app.models import get_db_session, init_database
    
    # Initialize database
    engine = init_database()
    
    # Create session
    session = get_db_session(engine)
    
    # Query predictions
    predictions = session.query(Prediction).all()
"""

from .prediction import (
    Base,
    Prediction,
    AccuracyMetric,
    CostTracking,
    DatabaseConfig,
    create_all_tables,
    drop_all_tables
)

from .cycle import (
    PredictionCycle,
    FourHourDecision,
    create_prediction_cycle,
    get_active_cycle,
    get_completed_cycles
)

from .automated_prediction import AutomatedPrediction

from .trade_outcome import (
    TradeOutcome,
    get_trade_outcomes_by_cycle,
    get_open_trades,
    get_trade_statistics
)

__all__ = [
    'Base',
    'Prediction',
    'AccuracyMetric',
    'CostTracking',
    'DatabaseConfig',
    'create_all_tables',
    'drop_all_tables',
    'get_db_session',
    'init_database',
    # Cycle models
    'PredictionCycle',
    'FourHourDecision',
    'create_prediction_cycle',
    'get_active_cycle',
    'get_completed_cycles',
    # Automated prediction model
    'AutomatedPrediction',
    # Trade outcome model
    'TradeOutcome',
    'get_trade_outcomes_by_cycle',
    'get_open_trades',
    'get_trade_statistics',
]


# Database session management
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Optional
import os


def init_database(
    connection_string: Optional[str] = None,
    echo: bool = False
):
    """
    Initialize database connection and return engine.
    
    Args:
        connection_string: PostgreSQL connection string
                          If not provided, uses DatabaseConfig defaults
        echo: If True, log all SQL statements (useful for debugging)
        
    Returns:
        SQLAlchemy Engine instance
        
    Example:
        engine = init_database()
        engine = init_database(echo=True)  # Debug mode
        engine = init_database('postgresql://user:pass@host:5432/db')
    """
    if connection_string is None:
        # Try to get from environment variable first
        connection_string = os.getenv(
            'DATABASE_URL',
            DatabaseConfig.get_connection_string()
        )
    
    engine = create_engine(
        connection_string,
        echo=echo,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,  # Verify connections before using
        pool_recycle=3600    # Recycle connections after 1 hour
    )
    
    return engine


def get_db_session(engine) -> Session:
    """
    Create and return a new database session.
    
    Args:
        engine: SQLAlchemy Engine instance
        
    Returns:
        SQLAlchemy Session instance
        
    Example:
        engine = init_database()
        session = get_db_session(engine)
        
        try:
            predictions = session.query(Prediction).all()
            session.commit()
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
    """
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine
    )
    return SessionLocal()


def get_session_factory(engine):
    """
    Create and return a session factory.
    
    Args:
        engine: SQLAlchemy Engine instance
        
    Returns:
        Session factory (callable)
        
    Example:
        engine = init_database()
        SessionFactory = get_session_factory(engine)
        
        session = SessionFactory()
        try:
            # Use session
            pass
        finally:
            session.close()
    """
    return sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine
    )
