"""
Gemini AI Client for ClaudeTrAIder Pro
Alternative AI provider using Google's Gemini API
"""

import os
import json
import time
from typing import Optional

import google.generativeai as genai

from .prompt_templates import get_system_prompt, format_market_context, PROMPT_VERSION
from app.core.logging import get_logger, log_ai_request, log_ai_response, log_ai_error

logger = get_logger(__name__)

# Gemini configuration
MODEL = "gemini-2.0-flash"  # Fast, cost-effective model
MAX_TOKENS = 500
TEMPERATURE = 0.3  # Lower temperature for consistent predictions

# Gemini pricing (per 1M tokens) - 2.0 Flash pricing
INPUT_PRICE_PER_1M = 0.10   # $0.10 per 1M input tokens
OUTPUT_PRICE_PER_1M = 0.40  # $0.40 per 1M output tokens


class GeminiClient:
    """
    Client for generating trading predictions using Google Gemini API.
    Implements the same interface as ClaudeClient for seamless switching.
    """

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            logger.warning("GEMINI_API_KEY not set - Gemini client will not function")
        else:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(
                MODEL,
                generation_config=genai.GenerationConfig(
                    max_output_tokens=MAX_TOKENS,
                    temperature=TEMPERATURE,
                )
            )
        self.provider = "gemini"

    def health_check(self) -> dict:
        """Check if Gemini API is available and responding."""
        if not self.api_key:
            return {
                "status": "error",
                "provider": self.provider,
                "model": MODEL,
                "error": "GEMINI_API_KEY not configured"
            }

        try:
            # Simple test generation
            response = self.model.generate_content("Say 'healthy'")
            return {
                "status": "healthy",
                "provider": self.provider,
                "model": MODEL,
                "response": response.text[:50] if response.text else "OK"
            }
        except Exception as e:
            logger.error(f"Gemini health check failed: {e}")
            return {
                "status": "error",
                "provider": self.provider,
                "model": MODEL,
                "error": str(e)
            }

    async def generate_prediction(
        self,
        market_snapshot: dict,
        strategy: str = "conservative"
    ) -> dict:
        """
        Generate a trading prediction using Gemini.

        Args:
            market_snapshot: Market data including price, indicators, sentiment
            strategy: Trading strategy ('conservative' or 'aggressive')

        Returns:
            dict with prediction, confidence, reasoning, and cost tracking
        """
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not configured")

        start_time = time.time()

        # Build the prompt using shared templates
        system_prompt = get_system_prompt(strategy)
        market_context = format_market_context(market_snapshot)

        # Combine system prompt and user message for Gemini
        full_prompt = f"""{system_prompt}

{market_context}

Respond with ONLY a JSON object in this exact format:
{{
    "trend_analysis": "Brief analysis of price trend",
    "indicator_alignment": "aligned|conflicting|mixed",
    "prediction": "up|down",
    "confidence": <number 0-100>,
    "reasoning": "Explanation of prediction"
}}"""

        # Log AI request
        estimated_input_tokens = self._estimate_tokens(full_prompt)
        log_ai_request(
            logger,
            provider="gemini",
            model=MODEL,
            input_tokens=estimated_input_tokens,
            symbol=market_snapshot.get('symbol', 'BTC/USDT'),
            request_type="prediction"
        )

        try:
            # Generate response
            response = self.model.generate_content(full_prompt)

            api_latency = (time.time() - start_time) * 1000  # ms

            # Parse the response
            response_text = response.text.strip()

            # Extract JSON from response (handle markdown code blocks)
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            prediction_data = json.loads(response_text)

            # Validate required fields
            self._validate_prediction(prediction_data)

            # Normalize values
            prediction_data["prediction"] = prediction_data["prediction"].lower()
            prediction_data["confidence"] = min(100, max(0, float(prediction_data["confidence"])))

            # Calculate cost using token counts from response metadata
            input_tokens = response.usage_metadata.prompt_token_count if hasattr(response, 'usage_metadata') and response.usage_metadata else self._estimate_tokens(full_prompt)
            output_tokens = response.usage_metadata.candidates_token_count if hasattr(response, 'usage_metadata') and response.usage_metadata else self._estimate_tokens(response_text)

            cost_tracking = self._calculate_cost(input_tokens, output_tokens, api_latency)

            # Log AI response
            log_ai_response(
                logger,
                provider="gemini",
                model=MODEL,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=api_latency,
                cost_usd=cost_tracking['total_cost_usd'],
                cached_tokens=0
            )

            # Return same structure as ClaudeClient for seamless switching
            return {
                'symbol': market_snapshot.get('symbol', 'BTC/USDT'),
                'timestamp': market_snapshot.get('timestamp'),
                'prediction_type': prediction_data["prediction"],
                'confidence': prediction_data["confidence"] / 100,  # Normalize to 0-1
                'reasoning': prediction_data.get("reasoning", ""),
                'market_context': market_snapshot,
                'claude_model': MODEL,  # Keep same key name for compatibility
                'prompt_version': PROMPT_VERSION,

                # Additional analysis
                'trend_analysis': prediction_data.get("trend_analysis", ""),
                'indicator_alignment': prediction_data.get("indicator_alignment", "unknown"),

                # Cost tracking (flattened to match ClaudeClient)
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'cached_tokens': 0,  # Gemini doesn't have caching
                'total_cost_usd': cost_tracking['total_cost_usd'],
                'api_latency_ms': int(api_latency),

                # Metadata
                'strategy': strategy,
                'created_at': market_snapshot.get('timestamp'),
                'ai_provider': self.provider
            }

        except json.JSONDecodeError as e:
            log_ai_error(
                logger,
                provider="gemini",
                model=MODEL,
                error_type="json_parse_error",
                error_message=str(e),
                symbol=market_snapshot.get('symbol')
            )
            raise ValueError(f"Invalid JSON response from Gemini: {e}")
        except Exception as e:
            log_ai_error(
                logger,
                provider="gemini",
                model=MODEL,
                error_type="unexpected_error",
                error_message=str(e),
                symbol=market_snapshot.get('symbol')
            )
            raise

    def _validate_prediction(self, prediction: dict) -> None:
        """Validate that the prediction has all required fields."""
        required_fields = ["prediction", "confidence", "reasoning"]
        for field in required_fields:
            if field not in prediction:
                raise ValueError(f"Missing required field: {field}")

        # Validate prediction direction
        if prediction["prediction"].lower() not in ["up", "down"]:
            raise ValueError(f"Invalid prediction direction: {prediction['prediction']}")

        # Validate confidence range
        try:
            conf = float(prediction["confidence"])
            if not 0 <= conf <= 100:
                raise ValueError(f"Confidence must be 0-100, got: {conf}")
        except (TypeError, ValueError) as e:
            raise ValueError(f"Invalid confidence value: {prediction['confidence']}")

    def _calculate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        api_latency_ms: float
    ) -> dict:
        """Calculate the cost of the API call."""
        input_cost = (input_tokens / 1_000_000) * INPUT_PRICE_PER_1M
        output_cost = (output_tokens / 1_000_000) * OUTPUT_PRICE_PER_1M
        total_cost = input_cost + output_cost

        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "input_cost_usd": round(input_cost, 6),
            "output_cost_usd": round(output_cost, 6),
            "total_cost_usd": round(total_cost, 6),
            "api_latency_ms": round(api_latency_ms, 2),
            "model": MODEL,
            "provider": self.provider
        }

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count when metadata is unavailable."""
        # Rough estimate: ~4 characters per token
        return len(text) // 4


# Singleton instance for app-wide use
_gemini_client: Optional[GeminiClient] = None


def get_gemini_client() -> GeminiClient:
    """Get or create the singleton Gemini client instance."""
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = GeminiClient()
    return _gemini_client
