"""
AI Provider Factory for ClaudeTrAIder Pro
Manages multiple AI providers (Claude, Gemini) and provides unified access.
"""

import os
import logging
from typing import Optional, Literal
from enum import Enum

logger = logging.getLogger(__name__)


class AIProvider(str, Enum):
    """Available AI providers."""
    CLAUDE = "claude"
    GEMINI = "gemini"


# Default provider - can be overridden by environment variable
DEFAULT_PROVIDER = os.getenv("AI_PROVIDER", AIProvider.GEMINI.value)


class AIProviderFactory:
    """
    Factory for creating and managing AI provider clients.
    Supports runtime switching between providers.
    """

    def __init__(self):
        self._claude_client = None
        self._gemini_client = None
        self._current_provider = DEFAULT_PROVIDER

    @property
    def current_provider(self) -> str:
        return self._current_provider

    def set_provider(self, provider: str) -> None:
        """Set the current AI provider."""
        provider = provider.lower()
        if provider not in [p.value for p in AIProvider]:
            raise ValueError(f"Invalid provider: {provider}. Must be one of {[p.value for p in AIProvider]}")
        self._current_provider = provider
        logger.info(f"AI provider set to: {provider}")

    def get_client(self, provider: Optional[str] = None):
        """
        Get an AI client instance.

        Args:
            provider: Specific provider to use, or None for current default

        Returns:
            AI client instance (ClaudeClient or GeminiClient)
        """
        provider = (provider or self._current_provider).lower()

        if provider == AIProvider.CLAUDE.value:
            return self._get_claude_client()
        elif provider == AIProvider.GEMINI.value:
            return self._get_gemini_client()
        else:
            raise ValueError(f"Unknown provider: {provider}")

    def _get_claude_client(self):
        """Get or create Claude client instance."""
        if self._claude_client is None:
            from .claude_client import ClaudeClient
            self._claude_client = ClaudeClient()
        return self._claude_client

    def _get_gemini_client(self):
        """Get or create Gemini client instance."""
        if self._gemini_client is None:
            from .gemini_client import GeminiClient
            self._gemini_client = GeminiClient()
        return self._gemini_client

    def health_check(self, provider: Optional[str] = None) -> dict:
        """
        Check health of specified or all providers.

        Args:
            provider: Specific provider to check, or None for all

        Returns:
            Health status dict
        """
        if provider:
            client = self.get_client(provider)
            return client.health_check()

        # Check all providers
        results = {
            "current_provider": self._current_provider,
            "providers": {}
        }

        for p in AIProvider:
            try:
                client = self.get_client(p.value)
                results["providers"][p.value] = client.health_check()
            except Exception as e:
                results["providers"][p.value] = {
                    "status": "error",
                    "error": str(e)
                }

        return results

    def generate_prediction(
        self,
        market_snapshot: dict,
        strategy: str = "conservative",
        provider: Optional[str] = None
    ) -> dict:
        """
        Generate a trading prediction using specified or current provider.

        Args:
            market_snapshot: Market data including price, indicators, sentiment
            strategy: Trading strategy ('conservative' or 'aggressive')
            provider: Specific provider to use, or None for current default

        Returns:
            Prediction dict with direction, confidence, reasoning, and cost tracking
        """
        client = self.get_client(provider)
        return client.generate_prediction(market_snapshot, strategy)

    async def generate_prediction_with_fallback(
        self,
        market_snapshot: dict,
        strategy: str = "conservative",
        primary_provider: Optional[str] = None,
        fallback_provider: str = "claude"
    ) -> dict:
        """
        Generate a trading prediction with automatic fallback on failure.

        Tries the primary provider first (default: Gemini), falls back to
        the fallback provider (default: Claude) on any error including
        rate limits, API errors, or invalid responses.

        Args:
            market_snapshot: Market data including price, indicators, sentiment
            strategy: Trading strategy ('conservative' or 'aggressive')
            primary_provider: Primary provider to try first (default: current provider)
            fallback_provider: Fallback provider if primary fails (default: 'claude')

        Returns:
            Prediction dict with direction, confidence, reasoning, cost tracking,
            and 'ai_provider' field indicating which provider was used
        """
        primary = (primary_provider or self._current_provider).lower()
        fallback = fallback_provider.lower()

        # Ensure fallback is different from primary
        if fallback == primary:
            fallback = "claude" if primary == "gemini" else "gemini"

        # Try primary provider first
        try:
            logger.info(f"Attempting prediction with primary provider: {primary}")
            client = self.get_client(primary)
            result = await client.generate_prediction(market_snapshot, strategy)
            result['ai_provider'] = primary
            result['fallback_used'] = False
            logger.info(f"Primary provider ({primary}) succeeded")
            return result

        except Exception as primary_error:
            logger.warning(
                f"Primary provider ({primary}) failed: {primary_error}. "
                f"Falling back to {fallback}"
            )

            # Try fallback provider
            try:
                logger.info(f"Attempting prediction with fallback provider: {fallback}")
                fallback_client = self.get_client(fallback)
                result = await fallback_client.generate_prediction(market_snapshot, strategy)
                result['ai_provider'] = fallback
                result['fallback_used'] = True
                result['primary_error'] = str(primary_error)
                logger.info(f"Fallback provider ({fallback}) succeeded")
                return result

            except Exception as fallback_error:
                logger.error(
                    f"Both providers failed. Primary ({primary}): {primary_error}, "
                    f"Fallback ({fallback}): {fallback_error}"
                )
                # Re-raise with combined error info
                raise RuntimeError(
                    f"All AI providers failed. "
                    f"Primary ({primary}): {primary_error}. "
                    f"Fallback ({fallback}): {fallback_error}"
                ) from fallback_error

    def get_available_providers(self) -> list:
        """Get list of available providers with their status."""
        providers = []
        for p in AIProvider:
            try:
                client = self.get_client(p.value)
                health = client.health_check()
                providers.append({
                    "id": p.value,
                    "name": p.value.capitalize(),
                    "available": health.get("status") == "healthy",
                    "model": health.get("model", "unknown"),
                    "is_default": p.value == self._current_provider
                })
            except Exception as e:
                providers.append({
                    "id": p.value,
                    "name": p.value.capitalize(),
                    "available": False,
                    "error": str(e),
                    "is_default": p.value == self._current_provider
                })
        return providers


# Singleton instance
_factory: Optional[AIProviderFactory] = None


def get_ai_provider_factory() -> AIProviderFactory:
    """Get or create the singleton AI provider factory instance."""
    global _factory
    if _factory is None:
        _factory = AIProviderFactory()
    return _factory


def get_ai_client(provider: Optional[str] = None):
    """Convenience function to get an AI client."""
    return get_ai_provider_factory().get_client(provider)


def generate_prediction(
    market_snapshot: dict,
    strategy: str = "conservative",
    provider: Optional[str] = None
) -> dict:
    """Convenience function to generate a prediction."""
    return get_ai_provider_factory().generate_prediction(market_snapshot, strategy, provider)


async def generate_prediction_with_fallback(
    market_snapshot: dict,
    strategy: str = "conservative",
    primary_provider: Optional[str] = None,
    fallback_provider: str = "claude"
) -> dict:
    """Convenience function to generate a prediction with automatic fallback."""
    return await get_ai_provider_factory().generate_prediction_with_fallback(
        market_snapshot, strategy, primary_provider, fallback_provider
    )
