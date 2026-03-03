#!/usr/bin/env python3
"""
Database CRUD Tests for Predictions

Tests database operations:
- Create predictions
- Read predictions
- Update predictions
- Delete predictions
- Cost tracking
- Accuracy metrics
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from decimal import Decimal

# Database configuration (from environment)
import os
DB_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': int(os.getenv('POSTGRES_PORT', '5432')),
    'database': os.getenv('POSTGRES_DB', 'trader_db'),
    'user': os.getenv('POSTGRES_USER', 'trader'),
    'password': os.getenv('POSTGRES_PASSWORD', 'changeme'),
    'schema': 'trading_predictions'
}

CONNECTION_STRING = os.getenv('DATABASE_URL', f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")


@pytest.fixture(scope="module")
def db_engine():
    """Create database engine"""
    engine = create_engine(CONNECTION_STRING)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    """Create database session for each test"""
    Session = sessionmaker(bind=db_engine)
    session = Session()
    
    yield session
    
    # Cleanup
    session.rollback()
    session.close()


def test_database_connection(db_session):
    """Test database connection"""
    result = db_session.execute(text("SELECT 1"))
    assert result.scalar() == 1


def test_schema_exists(db_session):
    """Test that trading_predictions schema exists"""
    result = db_session.execute(text(
        "SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'trading_predictions'"
    ))
    assert result.scalar() == 'trading_predictions'


def test_predictions_table_exists(db_session):
    """Test that predictions table exists"""
    result = db_session.execute(text(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'trading_predictions' AND table_name = 'predictions'"
    ))
    assert result.scalar() == 'predictions'


def test_create_prediction(db_session):
    """Test creating a new prediction"""
    result = db_session.execute(text(
        """
        INSERT INTO trading_predictions.predictions 
        (symbol, timestamp, prediction_type, confidence, reasoning, claude_model, prompt_version)
        VALUES 
        (:symbol, :timestamp, :prediction_type, :confidence, :reasoning, :claude_model, :prompt_version)
        RETURNING id, symbol, prediction_type, confidence
        """
    ), {
        'symbol': 'BTC/USDT',
        'timestamp': datetime.utcnow(),
        'prediction_type': 'up',
        'confidence': Decimal('0.75'),
        'reasoning': 'Test prediction for E2E testing',
        'claude_model': 'claude-sonnet-4-20250514',
        'prompt_version': '1.0'
    })
    
    prediction = result.fetchone()
    assert prediction is not None
    assert prediction.id is not None
    assert prediction.symbol == 'BTC/USDT'
    assert prediction.prediction_type == 'up'
    assert float(prediction.confidence) == 0.75
    
    # Cleanup
    db_session.execute(text(
        "DELETE FROM trading_predictions.predictions WHERE id = :id"
    ), {'id': prediction.id})
    db_session.commit()


def test_read_predictions(db_session):
    """Test reading predictions"""
    # Create test prediction
    result = db_session.execute(text(
        """
        INSERT INTO trading_predictions.predictions 
        (symbol, timestamp, prediction_type, confidence, reasoning)
        VALUES ('BTC/USDT', :timestamp, 'up', 0.75, 'Test prediction')
        RETURNING id
        """
    ), {'timestamp': datetime.utcnow()})
    
    prediction_id = result.scalar()
    db_session.commit()
    
    # Read it back
    result = db_session.execute(text(
        "SELECT * FROM trading_predictions.predictions WHERE id = :id"
    ), {'id': prediction_id})
    
    prediction = result.fetchone()
    assert prediction is not None
    assert prediction.symbol == 'BTC/USDT'
    assert prediction.prediction_type == 'up'
    
    # Cleanup
    db_session.execute(text(
        "DELETE FROM trading_predictions.predictions WHERE id = :id"
    ), {'id': prediction_id})
    db_session.commit()


def test_prediction_constraints(db_session):
    """Test prediction type and confidence constraints"""
    # Test invalid prediction type
    with pytest.raises(Exception):
        db_session.execute(text(
            """
            INSERT INTO trading_predictions.predictions 
            (symbol, timestamp, prediction_type, confidence, reasoning)
            VALUES ('BTC/USDT', :timestamp, 'invalid', 0.75, 'Test')
            """
        ), {'timestamp': datetime.utcnow()})
        db_session.commit()
    
    db_session.rollback()
    
    # Test invalid confidence (> 1.0)
    with pytest.raises(Exception):
        db_session.execute(text(
            """
            INSERT INTO trading_predictions.predictions 
            (symbol, timestamp, prediction_type, confidence, reasoning)
            VALUES ('BTC/USDT', :timestamp, 'up', 1.5, 'Test')
            """
        ), {'timestamp': datetime.utcnow()})
        db_session.commit()
    
    db_session.rollback()
    
    # Test invalid confidence (< 0.0)
    with pytest.raises(Exception):
        db_session.execute(text(
            """
            INSERT INTO trading_predictions.predictions 
            (symbol, timestamp, prediction_type, confidence, reasoning)
            VALUES ('BTC/USDT', :timestamp, 'up', -0.5, 'Test')
            """
        ), {'timestamp': datetime.utcnow()})
        db_session.commit()
    
    db_session.rollback()


def test_cost_tracking(db_session):
    """Test cost tracking functionality"""
    # Create prediction
    result = db_session.execute(text(
        """
        INSERT INTO trading_predictions.predictions 
        (symbol, timestamp, prediction_type, confidence, reasoning)
        VALUES ('BTC/USDT', :timestamp, 'up', 0.75, 'Test prediction')
        RETURNING id
        """
    ), {'timestamp': datetime.utcnow()})
    
    prediction_id = result.scalar()
    db_session.commit()
    
    # Create cost record
    db_session.execute(text(
        """
        INSERT INTO trading_predictions.cost_tracking 
        (prediction_id, input_tokens, output_tokens, cached_tokens, total_cost_usd, api_latency_ms)
        VALUES (:prediction_id, :input_tokens, :output_tokens, :cached_tokens, :total_cost_usd, :api_latency_ms)
        """
    ), {
        'prediction_id': prediction_id,
        'input_tokens': 1250,
        'output_tokens': 150,
        'cached_tokens': 0,
        'total_cost_usd': Decimal('0.0005'),
        'api_latency_ms': 850
    })
    db_session.commit()
    
    # Verify cost record
    result = db_session.execute(text(
        "SELECT * FROM trading_predictions.cost_tracking WHERE prediction_id = :id"
    ), {'id': prediction_id})
    
    cost = result.fetchone()
    assert cost is not None
    assert cost.input_tokens == 1250
    assert cost.output_tokens == 150
    assert float(cost.total_cost_usd) == 0.0005
    
    # Cleanup
    db_session.execute(text(
        "DELETE FROM trading_predictions.cost_tracking WHERE prediction_id = :id"
    ), {'id': prediction_id})
    db_session.execute(text(
        "DELETE FROM trading_predictions.predictions WHERE id = :id"
    ), {'id': prediction_id})
    db_session.commit()


def test_accuracy_metrics(db_session):
    """Test accuracy metrics functionality"""
    # Create prediction
    result = db_session.execute(text(
        """
        INSERT INTO trading_predictions.predictions 
        (symbol, timestamp, prediction_type, confidence, reasoning)
        VALUES ('BTC/USDT', :timestamp, 'up', 0.75, 'Test prediction')
        RETURNING id
        """
    ), {'timestamp': datetime.utcnow()})
    
    prediction_id = result.scalar()
    db_session.commit()
    
    # Create accuracy metric
    db_session.execute(text(
        """
        INSERT INTO trading_predictions.accuracy_metrics 
        (prediction_id, actual_movement, actual_change_pct, time_horizon_hours, was_correct, evaluated_at)
        VALUES (:prediction_id, :actual_movement, :actual_change_pct, :time_horizon_hours, :was_correct, :evaluated_at)
        """
    ), {
        'prediction_id': prediction_id,
        'actual_movement': 'up',
        'actual_change_pct': Decimal('1.5'),
        'time_horizon_hours': 1,
        'was_correct': True,
        'evaluated_at': datetime.utcnow()
    })
    db_session.commit()
    
    # Verify accuracy record
    result = db_session.execute(text(
        "SELECT * FROM trading_predictions.accuracy_metrics WHERE prediction_id = :id"
    ), {'id': prediction_id})
    
    metric = result.fetchone()
    assert metric is not None
    assert metric.actual_movement == 'up'
    assert metric.was_correct is True
    assert metric.time_horizon_hours == 1
    
    # Cleanup
    db_session.execute(text(
        "DELETE FROM trading_predictions.accuracy_metrics WHERE prediction_id = :id"
    ), {'id': prediction_id})
    db_session.execute(text(
        "DELETE FROM trading_predictions.predictions WHERE id = :id"
    ), {'id': prediction_id})
    db_session.commit()


def test_query_predictions_by_symbol(db_session):
    """Test querying predictions by symbol"""
    # Create test predictions
    symbols = ['BTC/USDT', 'ETH/USDT', 'BTC/USDT']
    prediction_ids = []
    
    for symbol in symbols:
        result = db_session.execute(text(
            """
            INSERT INTO trading_predictions.predictions 
            (symbol, timestamp, prediction_type, confidence, reasoning)
            VALUES (:symbol, :timestamp, 'up', 0.75, 'Test')
            RETURNING id
            """
        ), {'symbol': symbol, 'timestamp': datetime.utcnow()})
        prediction_ids.append(result.scalar())
    
    db_session.commit()
    
    # Query BTC/USDT predictions
    result = db_session.execute(text(
        "SELECT COUNT(*) FROM trading_predictions.predictions WHERE symbol = 'BTC/USDT'"
    ))
    
    count = result.scalar()
    assert count >= 2  # At least our 2 test predictions
    
    # Cleanup
    for pid in prediction_ids:
        db_session.execute(text(
            "DELETE FROM trading_predictions.predictions WHERE id = :id"
        ), {'id': pid})
    db_session.commit()


def test_query_predictions_by_date_range(db_session):
    """Test querying predictions by date range"""
    now = datetime.utcnow()
    
    # Create prediction
    result = db_session.execute(text(
        """
        INSERT INTO trading_predictions.predictions 
        (symbol, timestamp, prediction_type, confidence, reasoning)
        VALUES ('BTC/USDT', :timestamp, 'up', 0.75, 'Test')
        RETURNING id
        """
    ), {'timestamp': now})
    
    prediction_id = result.scalar()
    db_session.commit()
    
    # Query with date range
    start_date = now - timedelta(hours=1)
    end_date = now + timedelta(hours=1)
    
    result = db_session.execute(text(
        """
        SELECT COUNT(*) FROM trading_predictions.predictions 
        WHERE timestamp BETWEEN :start_date AND :end_date
        """
    ), {'start_date': start_date, 'end_date': end_date})
    
    count = result.scalar()
    assert count >= 1
    
    # Cleanup
    db_session.execute(text(
        "DELETE FROM trading_predictions.predictions WHERE id = :id"
    ), {'id': prediction_id})
    db_session.commit()


def test_jsonb_market_context(db_session):
    """Test storing and querying JSONB market context"""
    market_context = {
        "price": 43250.50,
        "volume": 28500000000,
        "sentiment": {"score": 65},
        "technical": {"rsi_14": 58.5}
    }
    
    # Create prediction with JSONB context
    result = db_session.execute(text(
        """
        INSERT INTO trading_predictions.predictions 
        (symbol, timestamp, prediction_type, confidence, reasoning, market_context)
        VALUES ('BTC/USDT', :timestamp, 'up', 0.75, 'Test', :market_context::jsonb)
        RETURNING id
        """
    ), {
        'timestamp': datetime.utcnow(),
        'market_context': str(market_context).replace("'", '"')
    })
    
    prediction_id = result.scalar()
    db_session.commit()
    
    # Query and verify JSONB
    result = db_session.execute(text(
        "SELECT market_context FROM trading_predictions.predictions WHERE id = :id"
    ), {'id': prediction_id})
    
    context = result.scalar()
    assert context is not None
    assert 'price' in context
    
    # Cleanup
    db_session.execute(text(
        "DELETE FROM trading_predictions.predictions WHERE id = :id"
    ), {'id': prediction_id})
    db_session.commit()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
