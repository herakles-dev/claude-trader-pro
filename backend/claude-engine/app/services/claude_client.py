"""
Claude Client - Anthropic API Integration for Trading Predictions

Handles Claude API calls, token counting, cost tracking, and response parsing
for AI-powered trading predictions.

Model: Claude Sonnet 4.5 (balanced performance and capability)
Pricing: $3.00/1M input tokens, $15.00/1M output tokens

Author: AI Integration Specialist
Date: 2025-11-11
"""

import json
import os
import time
from typing import Dict, Any, Optional

import anthropic
from anthropic import Anthropic, APIError, APIConnectionError, RateLimitError

from app.services.prompt_templates import (
    get_system_prompt,
    format_market_context,
    PROMPT_VERSION
)
from app.core.logging import get_logger, log_ai_request, log_ai_response, log_ai_error

logger = get_logger(__name__)


class ClaudeClient:
    """
    Client for generating trading predictions using Claude AI
    """
    
    # Model configuration
    MODEL = "claude-sonnet-4-20250514"  # Balanced model for trading analysis
    MAX_TOKENS = 500  # Sufficient for prediction JSON response
    
    # Pricing (per million tokens)
    PRICE_INPUT = 3.00  # $3.00 per 1M input tokens
    PRICE_OUTPUT = 15.00  # $15.00 per 1M output tokens
    PRICE_CACHED_INPUT = 0.30  # $0.30 per 1M cached input tokens (10x cheaper)
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Claude client
        
        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
        """
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        
        if not self.api_key:
            logger.error("ANTHROPIC_API_KEY not found in environment")
            raise ValueError(
                "ANTHROPIC_API_KEY must be set in environment variables or secrets vault"
            )
        
        self.client = Anthropic(api_key=self.api_key)
        logger.info(f"ClaudeClient initialized with model: {self.MODEL}")
    
    async def generate_prediction(
        self,
        market_snapshot: Dict[str, Any],
        strategy: str = "conservative"
    ) -> Dict[str, Any]:
        """
        Generate trading prediction using Claude AI
        
        Args:
            market_snapshot: Market data from UnifiedDataClient
            strategy: "conservative" or "aggressive"
            
        Returns:
            Prediction result with metadata and cost tracking
            
        Raises:
            Exception if Claude API fails or returns invalid response
        """
        start_time = time.time()
        
        try:
            # Get prompts
            system_prompt = get_system_prompt(strategy)
            user_prompt = format_market_context(market_snapshot)

            # Estimate input tokens for logging
            estimated_input_tokens = self.estimate_tokens(system_prompt + user_prompt)

            # Log AI request
            log_ai_request(
                logger,
                provider="claude",
                model=self.MODEL,
                input_tokens=estimated_input_tokens,
                symbol=market_snapshot['symbol'],
                request_type="prediction"
            )

            # Call Claude API
            response = self.client.messages.create(
                model=self.MODEL,
                max_tokens=self.MAX_TOKENS,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ]
            )
            
            # Calculate latency
            latency_ms = int((time.time() - start_time) * 1000)
            
            # Extract response text
            response_text = response.content[0].text

            # Strip markdown code fences if present (```json ... ```)
            response_text = response_text.strip()
            if response_text.startswith('```json'):
                response_text = response_text[7:]  # Remove ```json
            if response_text.startswith('```'):
                response_text = response_text[3:]  # Remove ```
            if response_text.endswith('```'):
                response_text = response_text[:-3]  # Remove trailing ```
            response_text = response_text.strip()

            # Parse JSON response
            try:
                prediction_json = json.loads(response_text)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Claude response as JSON: {response_text[:500]}")
                raise Exception(f"Invalid Claude response format: {str(e)}")
            
            # Validate response structure
            self._validate_prediction(prediction_json)
            
            # Extract usage metrics
            usage = response.usage
            input_tokens = usage.input_tokens
            output_tokens = usage.output_tokens
            cached_tokens = getattr(usage, 'cache_read_input_tokens', 0)
            
            # Calculate cost
            cost = self._calculate_cost(input_tokens, output_tokens, cached_tokens)
            
            # Build result
            result = {
                'symbol': market_snapshot['symbol'],
                'timestamp': market_snapshot['timestamp'],
                'prediction_type': prediction_json['prediction'],
                'confidence': float(prediction_json['confidence']) / 100.0,  # Convert to 0-1 scale
                'reasoning': prediction_json['reasoning'],
                'market_context': market_snapshot,
                'claude_model': self.MODEL,
                'prompt_version': PROMPT_VERSION,
                
                # Additional analysis
                'trend_analysis': prediction_json.get('trend_analysis', ''),
                'indicator_alignment': prediction_json.get('indicator_alignment', 'unknown'),
                
                # Cost tracking
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'cached_tokens': cached_tokens,
                'total_cost_usd': cost,
                'api_latency_ms': latency_ms,
                
                # Metadata
                'strategy': strategy,
                'created_at': market_snapshot['timestamp']
            }
            
            # Log AI response
            log_ai_response(
                logger,
                provider="claude",
                model=self.MODEL,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
                cost_usd=cost,
                cached_tokens=cached_tokens
            )

            logger.info(
                f"Prediction generated: {result['prediction_type']} "
                f"(confidence: {result['confidence']:.2f})",
                extra={
                    "symbol": market_snapshot['symbol'],
                    "prediction_type": result['prediction_type'],
                    "confidence": result['confidence']
                }
            )

            return result

        except RateLimitError as e:
            log_ai_error(
                logger,
                provider="claude",
                model=self.MODEL,
                error_type="rate_limit",
                error_message=str(e),
                symbol=market_snapshot.get('symbol')
            )
            raise Exception(f"Rate limit exceeded. Please try again later.")

        except APIConnectionError as e:
            log_ai_error(
                logger,
                provider="claude",
                model=self.MODEL,
                error_type="connection_error",
                error_message=str(e),
                symbol=market_snapshot.get('symbol')
            )
            raise Exception(f"Failed to connect to Claude API: {str(e)}")

        except APIError as e:
            log_ai_error(
                logger,
                provider="claude",
                model=self.MODEL,
                error_type="api_error",
                error_message=str(e),
                symbol=market_snapshot.get('symbol')
            )
            raise Exception(f"Claude API error: {str(e)}")

        except Exception as e:
            log_ai_error(
                logger,
                provider="claude",
                model=self.MODEL,
                error_type="unexpected_error",
                error_message=str(e),
                symbol=market_snapshot.get('symbol')
            )
            raise
    
    def _validate_prediction(self, prediction: Dict[str, Any]):
        """
        Validate prediction response structure
        
        Raises:
            ValueError if prediction is invalid
        """
        required_fields = ['prediction', 'confidence', 'reasoning']
        
        for field in required_fields:
            if field not in prediction:
                raise ValueError(f"Missing required field: {field}")
        
        # Validate prediction type
        if prediction['prediction'] not in ['up', 'down']:
            raise ValueError(
                f"Invalid prediction type: {prediction['prediction']}. "
                "Must be 'up' or 'down'"
            )
        
        # Validate confidence
        confidence = prediction['confidence']
        if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 100:
            raise ValueError(
                f"Invalid confidence: {confidence}. "
                "Must be a number between 0 and 100"
            )
        
        # Validate reasoning
        if not isinstance(prediction['reasoning'], str) or len(prediction['reasoning']) < 10:
            raise ValueError("Reasoning must be a string with at least 10 characters")
    
    def _calculate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        cached_tokens: int = 0
    ) -> float:
        """
        Calculate API cost in USD
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            cached_tokens: Number of cached input tokens (10x cheaper)
            
        Returns:
            Total cost in USD
        """
        # Calculate cost for each token type
        uncached_input_tokens = max(0, input_tokens - cached_tokens)
        
        cost_input = (uncached_input_tokens / 1_000_000) * self.PRICE_INPUT
        cost_output = (output_tokens / 1_000_000) * self.PRICE_OUTPUT
        cost_cached = (cached_tokens / 1_000_000) * self.PRICE_CACHED_INPUT
        
        total_cost = cost_input + cost_output + cost_cached
        
        logger.debug(
            f"Cost breakdown: "
            f"input={uncached_input_tokens} (${cost_input:.6f}), "
            f"output={output_tokens} (${cost_output:.6f}), "
            f"cached={cached_tokens} (${cost_cached:.6f}), "
            f"total=${total_cost:.6f}"
        )
        
        return round(total_cost, 8)  # Round to 8 decimal places
    
    def health_check(self) -> dict:
        """
        Check if Claude API is accessible

        Returns:
            dict with status and provider info
        """
        try:
            # Send minimal test request
            response = self.client.messages.create(
                model=self.MODEL,
                max_tokens=10,
                messages=[
                    {
                        "role": "user",
                        "content": "Say 'healthy'"
                    }
                ]
            )

            return {
                "status": "healthy",
                "provider": "claude",
                "model": self.MODEL,
                "response": response.content[0].text[:50] if response.content else "OK"
            }

        except Exception as e:
            logger.error(f"Claude health check failed: {e}")
            return {
                "status": "error",
                "provider": "claude",
                "model": self.MODEL,
                "error": str(e)
            }
    
    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text
        
        Note: This is a rough estimate. Actual tokens may vary.
        Anthropic uses approximately 3.5 characters per token on average.
        
        Args:
            text: Text to estimate tokens for
            
        Returns:
            Estimated token count
        """
        # Rough estimation: ~3.5 characters per token
        return len(text) // 3 + 1
    
    def estimate_cost(self, input_text: str, output_tokens: int = None) -> float:
        """
        Estimate API cost for given input
        
        Args:
            input_text: Input text to estimate cost for
            output_tokens: Expected output tokens (defaults to MAX_TOKENS)
            
        Returns:
            Estimated cost in USD
        """
        input_tokens = self.estimate_tokens(input_text)
        output_tokens = output_tokens or self.MAX_TOKENS
        
        return self._calculate_cost(input_tokens, output_tokens)


# Example usage for testing
if __name__ == "__main__":
    import asyncio
    
    async def test_claude_client():
        """Test Claude client with mock data"""
        
        # Mock market snapshot
        mock_snapshot = {
            'symbol': 'BTC/USDT',
            'timestamp': '2025-11-11T12:00:00Z',
            'overall_confidence': 0.85,
            'market': {
                'price': 43250.50,
                'volume_24h': 28500000000,
                'price_change_24h': 2.5,
                'high_24h': 43500,
                'low_24h': 42000,
                'confidence': 0.90,
                'sources': ['binance', 'bybit']
            },
            'sentiment': {
                'score': 65,
                'fear_greed_index': 68,
                'fear_greed_label': 'Greed',
                'reddit_score': 72,
                'reddit_posts_24h': 456,
                'confidence': 0.75
            },
            'technical': {
                'rsi_14': 58.5,
                'rsi_signal': 'neutral',
                'macd_histogram': 150.25,
                'macd_trend': 'bullish',
                'ema_20': 42900,
                'ema_50': 42500,
                'confidence': 0.88
            },
            'derivatives': {
                'avg_funding_rate': 0.0125,
                'total_open_interest': 15000000000,
                'oi_change_24h': 3.2,
                'confidence': 0.82
            }
        }
        
        try:
            client = ClaudeClient()
            
            # Test health check
            print("Testing health check...")
            health = client.health_check()
            print(f"Claude API health: {health}")

            if health.get('status') == 'healthy':
                # Generate prediction
                print("\nGenerating prediction...")
                result = await client.generate_prediction(mock_snapshot)
                
                print(f"\nPrediction: {result['prediction_type']}")
                print(f"Confidence: {result['confidence']:.2%}")
                print(f"Reasoning: {result['reasoning']}")
                print(f"Cost: ${result['total_cost_usd']:.6f}")
                print(f"Latency: {result['api_latency_ms']}ms")
                print(f"Tokens: {result['input_tokens']} input, {result['output_tokens']} output")
        
        except Exception as e:
            print(f"Error: {e}")
    
    # Run test
    asyncio.run(test_claude_client())
