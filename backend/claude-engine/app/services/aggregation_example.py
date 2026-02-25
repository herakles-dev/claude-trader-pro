"""
Example usage of the 4-Hour Aggregation Service

This script demonstrates how to use the aggregation service to combine
4 hourly predictions into a single 4-hour trading decision.

Author: Backend Architect
Date: 2025-11-12
"""

from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import (
    Base,
    Prediction,
    PredictionCycle,
    FourHourDecision,
    DatabaseConfig
)
from app.services.aggregation_service import (
    AggregationService,
    aggregate_cycle_predictions
)


def setup_database():
    """Create database connection and tables"""
    connection_string = DatabaseConfig.get_connection_string()
    engine = create_engine(connection_string, echo=True)
    
    # Create all tables
    Base.metadata.create_all(engine)
    
    # Create session
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    return session, engine


def create_sample_predictions(session, cycle_id, symbol="BTC/USDT"):
    """
    Create 4 sample hourly predictions for testing.
    
    This simulates a real scenario where we have predictions from 4 consecutive hours.
    """
    base_time = datetime.utcnow() - timedelta(hours=4)
    
    # Sample predictions with varying confidence and directions
    predictions_data = [
        {
            'hour': 1,
            'prediction_type': 'up',
            'confidence': Decimal('0.65'),
            'reasoning': 'Strong bullish momentum with RSI at 65'
        },
        {
            'hour': 2,
            'prediction_type': 'down',
            'confidence': Decimal('0.72'),
            'reasoning': 'Resistance at $45,000 with decreasing volume'
        },
        {
            'hour': 3,
            'prediction_type': 'up',
            'confidence': Decimal('0.78'),
            'reasoning': 'Breaking resistance, strong buy pressure'
        },
        {
            'hour': 4,
            'prediction_type': 'up',
            'confidence': Decimal('0.85'),
            'reasoning': 'Confirmed breakout with high volume'
        }
    ]
    
    predictions = []
    for pred_data in predictions_data:
        prediction = Prediction(
            cycle_id=cycle_id,
            symbol=symbol,
            timestamp=base_time + timedelta(hours=pred_data['hour']),
            prediction_type=pred_data['prediction_type'],
            confidence=pred_data['confidence'],
            reasoning=pred_data['reasoning'],
            market_context={'hour': pred_data['hour']},
            claude_model='claude-sonnet-4-20250514',
            prompt_version='v1.0'
        )
        session.add(prediction)
        predictions.append(prediction)
    
    session.commit()
    
    # Update cycle prediction count
    cycle = session.query(PredictionCycle).filter(
        PredictionCycle.id == cycle_id
    ).first()
    cycle.prediction_count = 4
    session.commit()
    
    return predictions


def example_basic_aggregation():
    """
    Example 1: Basic aggregation workflow
    
    This demonstrates the complete workflow:
    1. Create a prediction cycle
    2. Add 4 hourly predictions
    3. Run aggregation
    4. View the results
    """
    print("\n" + "="*70)
    print("EXAMPLE 1: Basic 4-Hour Aggregation")
    print("="*70)
    
    # Setup
    session, engine = setup_database()
    
    try:
        # Step 1: Create a new prediction cycle
        cycle = PredictionCycle(
            symbol="BTC/USDT",
            status='in_progress',
            started_at=datetime.utcnow() - timedelta(hours=4)
        )
        session.add(cycle)
        session.commit()
        session.refresh(cycle)
        
        print(f"\n✓ Created prediction cycle: {cycle.id}")
        
        # Step 2: Create 4 hourly predictions
        predictions = create_sample_predictions(session, cycle.id)
        print(f"✓ Created {len(predictions)} hourly predictions")
        
        for i, pred in enumerate(predictions, 1):
            print(f"  Hour {i}: {pred.prediction_type.upper()} "
                  f"(confidence: {float(pred.confidence):.2%})")
        
        # Step 3: Run aggregation
        print("\n→ Running aggregation algorithm...")
        service = AggregationService(session)
        decision_id = service.aggregate_cycle_predictions(cycle.id)
        
        print(f"✓ Aggregation complete! Decision ID: {decision_id}")
        
        # Step 4: View results
        decision = session.query(FourHourDecision).filter(
            FourHourDecision.id == decision_id
        ).first()
        
        print("\n" + "-"*70)
        print("AGGREGATED DECISION RESULTS")
        print("-"*70)
        print(f"Final Decision: {decision.final_decision.upper()}")
        print(f"Confidence: {float(decision.aggregated_confidence):.2%}")
        print(f"\nVote Breakdown:")
        print(f"  UP votes: {decision.vote_breakdown['up_count']}")
        print(f"  DOWN votes: {decision.vote_breakdown['down_count']}")
        print(f"  UP weighted score: {decision.vote_breakdown['up_weighted']:.4f}")
        print(f"  DOWN weighted score: {decision.vote_breakdown['down_weighted']:.4f}")
        
        print(f"\nConfidence Statistics:")
        print(f"  Min: {decision.confidence_stats['min']:.2%}")
        print(f"  Max: {decision.confidence_stats['max']:.2%}")
        print(f"  Average: {decision.confidence_stats['avg']:.2%}")
        print(f"  Std Dev: {decision.confidence_stats['std_dev']:.4f}")
        
        print(f"\nReasoning:\n{decision.decision_reasoning}")
        
        # Verify cycle status updated
        session.refresh(cycle)
        print(f"\n✓ Cycle status updated to: {cycle.status}")
        print("="*70)
        
    finally:
        session.close()
        engine.dispose()


def example_weighted_voting_explanation():
    """
    Example 2: Detailed explanation of the time-weighted voting algorithm
    
    This shows step-by-step how the algorithm calculates the final decision.
    """
    print("\n" + "="*70)
    print("EXAMPLE 2: Time-Weighted Voting Algorithm Explanation")
    print("="*70)
    
    # Sample data
    predictions = [
        {'hour': 1, 'type': 'up', 'confidence': 0.65, 'weight': 0.15},
        {'hour': 2, 'type': 'down', 'confidence': 0.72, 'weight': 0.20},
        {'hour': 3, 'type': 'up', 'confidence': 0.78, 'weight': 0.25},
        {'hour': 4, 'type': 'up', 'confidence': 0.85, 'weight': 0.40},
    ]
    
    print("\nInput: 4 Hourly Predictions")
    print("-" * 70)
    for pred in predictions:
        print(f"Hour {pred['hour']} (weight {pred['weight']:.2f}): "
              f"{pred['type'].upper()} - confidence {pred['confidence']:.2%}")
    
    print("\nCalculation: Weighted Scores")
    print("-" * 70)
    
    up_score = 0.0
    down_score = 0.0
    
    for pred in predictions:
        weighted_value = pred['confidence'] * pred['weight']
        if pred['type'] == 'up':
            up_score += weighted_value
            print(f"Hour {pred['hour']}: {pred['confidence']:.2%} × {pred['weight']:.2f} "
                  f"= {weighted_value:.4f} → UP")
        else:
            down_score += weighted_value
            print(f"Hour {pred['hour']}: {pred['confidence']:.2%} × {pred['weight']:.2f} "
                  f"= {weighted_value:.4f} → DOWN")
    
    print("\nFinal Weighted Scores:")
    print("-" * 70)
    print(f"UP total:   {up_score:.4f}")
    print(f"DOWN total: {down_score:.4f}")
    
    final_decision = 'UP' if up_score > down_score else 'DOWN'
    winning_score = max(up_score, down_score)
    
    print(f"\n→ Final Decision: {final_decision} (confidence: {winning_score:.2%})")
    print("\nWhy time-weighted?")
    print("-" * 70)
    print("• Hour 1 (oldest) gets 15% weight - market may have changed")
    print("• Hour 2 gets 20% weight - still relevant but less recent")
    print("• Hour 3 gets 25% weight - recent and relevant")
    print("• Hour 4 (newest) gets 40% weight - most current market conditions")
    print("\nThis ensures more recent predictions have stronger influence!")
    print("="*70)


def example_edge_cases():
    """
    Example 3: Testing edge cases and error handling
    """
    print("\n" + "="*70)
    print("EXAMPLE 3: Edge Cases and Error Handling")
    print("="*70)
    
    session, engine = setup_database()
    
    try:
        # Edge Case 1: Trying to aggregate non-existent cycle
        print("\n1. Testing non-existent cycle...")
        service = AggregationService(session)
        try:
            fake_id = uuid4()
            service.aggregate_cycle_predictions(fake_id)
            print("  ✗ Should have raised error!")
        except Exception as e:
            print(f"  ✓ Correctly raised error: {type(e).__name__}")
        
        # Edge Case 2: Cycle with insufficient predictions
        print("\n2. Testing cycle with < 4 predictions...")
        cycle = PredictionCycle(symbol="BTC/USDT", status='in_progress')
        session.add(cycle)
        session.commit()
        session.refresh(cycle)
        
        # Add only 2 predictions
        for i in range(2):
            pred = Prediction(
                cycle_id=cycle.id,
                symbol="BTC/USDT",
                timestamp=datetime.utcnow(),
                prediction_type='up',
                confidence=Decimal('0.75'),
                reasoning='Test'
            )
            session.add(pred)
        session.commit()
        
        try:
            service.aggregate_cycle_predictions(cycle.id)
            print("  ✗ Should have raised error!")
        except Exception as e:
            print(f"  ✓ Correctly raised error: {type(e).__name__}")
            print(f"     Message: {str(e)}")
        
        # Edge Case 3: Already completed cycle
        print("\n3. Testing already completed cycle...")
        cycle.status = 'completed'
        session.commit()
        
        try:
            service.aggregate_cycle_predictions(cycle.id)
            print("  ✗ Should have raised error!")
        except Exception as e:
            print(f"  ✓ Correctly raised error: {type(e).__name__}")
        
        print("\n✓ All edge cases handled correctly!")
        print("="*70)
        
    finally:
        session.close()
        engine.dispose()


def example_convenience_function():
    """
    Example 4: Using the convenience function
    """
    print("\n" + "="*70)
    print("EXAMPLE 4: Using Convenience Function")
    print("="*70)
    
    session, engine = setup_database()
    
    try:
        # Create cycle and predictions
        cycle = PredictionCycle(symbol="BTC/USDT", status='in_progress')
        session.add(cycle)
        session.commit()
        session.refresh(cycle)
        
        create_sample_predictions(session, cycle.id)
        
        # Use convenience function (simpler API)
        print("\nUsing: aggregate_cycle_predictions(db_session, cycle_id)")
        decision_id = aggregate_cycle_predictions(session, cycle.id)
        
        print(f"✓ Decision created: {decision_id}")
        print("\nThis is the recommended way for simple use cases!")
        print("="*70)
        
    finally:
        session.close()
        engine.dispose()


if __name__ == '__main__':
    """
    Run all examples
    """
    print("\n" + "#"*70)
    print("# 4-HOUR PREDICTION AGGREGATION SERVICE - EXAMPLES")
    print("#"*70)
    
    # Run examples
    example_weighted_voting_explanation()
    example_basic_aggregation()
    example_edge_cases()
    example_convenience_function()
    
    print("\n" + "#"*70)
    print("# ALL EXAMPLES COMPLETED")
    print("#"*70)
