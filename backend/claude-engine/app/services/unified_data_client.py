"""
Unified Data Client - Wrapper for Unified Crypto Data API

Provides simplified access to market data, sentiment, technical indicators,
and derivatives data with caching and error handling.

Author: AI Integration Specialist
Date: 2025-11-11
"""

import asyncio
import sys
import os
import time
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

# Add external_data_sources to Python path (Docker volume mount)
sys.path.insert(0, '/app/external_data_sources')

from unified_data_api import UnifiedCryptoDataAPI
from data_schemas import MarketSnapshot
from taapi_pro_client import TaapiProClient
from multi_timeframe_analysis import MultiTimeframeAnalysis

from app.core.logging import get_logger, log_external_api_call

logger = get_logger(__name__)


class UnifiedDataClient:
    """
    Wrapper client for Unified Crypto Data API with caching and error handling
    """
    
    def __init__(self, taapi_api_key: Optional[str] = None):
        """Initialize Unified API client with optional TAAPI Pro integration"""
        self.api = UnifiedCryptoDataAPI()
        self._cache = {}
        self._cache_ttl = 300  # 5 minutes - consistent with TAAPI cache

        # Separate MTF cache with longer TTL (30 min) - reduces TAAPI rate limit issues
        # Since 4H data doesn't change rapidly, we can safely cache for 30 minutes
        self._mtf_cache = {}
        self._mtf_cache_ttl = 1800  # 30 minutes

        # MTF circuit breaker tracking
        self._mtf_consecutive_failures = 0
        self._mtf_backoff_until: Optional[datetime] = None
        
        # Initialize TAAPI Pro client if API key available
        self.taapi_api_key = taapi_api_key or os.getenv('TAAPI_API_KEY')
        print(f"[DEBUG] TAAPI_API_KEY present: {bool(self.taapi_api_key)}", flush=True)
        if self.taapi_api_key:
            try:
                print(f"[DEBUG] Attempting to initialize TaapiProClient...", flush=True)
                self.taapi_client = TaapiProClient(api_key=self.taapi_api_key)
                print(f"[DEBUG] TaapiProClient created, initializing MultiTimeframeAnalysis...", flush=True)
                self.mtf_analyzer = MultiTimeframeAnalysis(self.taapi_client)
                print(f"[INFO] ✓ TAAPI Pro integration enabled - Multi-timeframe analysis available", flush=True)
                logger.info("✓ TAAPI Pro integration enabled - Multi-timeframe analysis available")
            except Exception as e:
                print(f"[ERROR] TAAPI Pro initialization failed: {e}", flush=True)
                logger.warning(f"TAAPI Pro initialization failed: {e}, using fallback", exc_info=True)
                self.taapi_client = None
                self.mtf_analyzer = None
        else:
            self.taapi_client = None
            self.mtf_analyzer = None
            print(f"[WARN] TAAPI Pro not configured - using Binance fallback only", flush=True)
            logger.warning("TAAPI Pro not configured - using Binance fallback only")
        
        logger.info("UnifiedDataClient initialized")
    
    async def get_market_snapshot(self, symbol: str) -> Dict[str, Any]:
        """
        Get complete market snapshot for a trading pair

        Returns:
            Market snapshot with price, sentiment, technical indicators, derivatives

        Raises:
            Exception if API fails or returns invalid data
        """
        cache_key = f"snapshot_{symbol}"

        # Check cache
        cached = self._get_from_cache(cache_key)
        if cached:
            log_external_api_call(
                logger,
                source="unified_data_api",
                endpoint="get_market_snapshot",
                latency_ms=0,
                status_code=200,
                cache_hit=True
            )
            return cached

        try:
            logger.info(f"Fetching market snapshot for {symbol}")
            start_time = time.time()

            # OPTIMIZATION: Do MTF analysis FIRST if available
            # MTF already includes 4H RSI, MACD, EMA - no need for separate TAAPI call
            # This eliminates double API calls and rate limit issues
            mtf_result = None
            mtf_cache_hit = False
            if self.mtf_analyzer:
                # Check MTF cache first (30 min TTL to avoid rate limits)
                mtf_cache_key = f"mtf_{symbol}"
                cached_mtf = self._get_mtf_from_cache(mtf_cache_key)
                if cached_mtf:
                    mtf_result = cached_mtf
                    mtf_cache_hit = True
                    log_external_api_call(
                        logger,
                        source="taapi_pro",
                        endpoint="multi_timeframe_analysis",
                        latency_ms=0,
                        status_code=200,
                        cache_hit=True
                    )
                    logger.info(f"MTF cache hit for {symbol}")
                # Check circuit breaker - skip MTF if in backoff period
                elif self._mtf_backoff_until and datetime.utcnow() < self._mtf_backoff_until:
                    remaining = (self._mtf_backoff_until - datetime.utcnow()).total_seconds()
                    logger.info(f"Skipping MTF analysis - circuit breaker active, {remaining:.0f}s remaining")
                else:
                    # Fetch fresh MTF data
                    mtf_start = time.time()
                    try:
                        mtf_result = await self.mtf_analyzer.analyze(symbol)
                        mtf_latency = (time.time() - mtf_start) * 1000
                        log_external_api_call(
                            logger,
                            source="taapi_pro",
                            endpoint="multi_timeframe_analysis",
                            latency_ms=mtf_latency,
                            status_code=200,
                            cache_hit=False
                        )
                        logger.info(f"Multi-timeframe analysis succeeded for {symbol} ({mtf_latency:.0f}ms)")
                        # Cache the successful result for 30 minutes
                        self._set_mtf_cache(mtf_cache_key, mtf_result)
                        # Reset circuit breaker on success
                        self._mtf_consecutive_failures = 0
                        self._mtf_backoff_until = None
                    except Exception as mtf_error:
                        # MTF failure is non-fatal - will use basic snapshot
                        mtf_latency = (time.time() - mtf_start) * 1000
                        log_external_api_call(
                            logger,
                            source="taapi_pro",
                            endpoint="multi_timeframe_analysis",
                            latency_ms=mtf_latency,
                            status_code=500,
                            cache_hit=False,
                            error=str(mtf_error)
                        )
                        mtf_result = None
                        # Increment circuit breaker counter
                        self._mtf_consecutive_failures += 1
                        if self._mtf_consecutive_failures >= 3:
                            # Back off for 5 minutes after 3 consecutive failures
                            self._mtf_backoff_until = datetime.utcnow() + timedelta(minutes=5)
                            logger.warning(f"MTF circuit breaker triggered: {self._mtf_consecutive_failures} failures, backing off until {self._mtf_backoff_until.isoformat()}")

            # Fetch basic snapshot (market data, sentiment, derivatives, etc.)
            # When MTF succeeds, pass skip_taapi=True to avoid duplicate TAAPI call
            skip_taapi = mtf_result is not None
            if skip_taapi:
                logger.info("MTF data available - skipping redundant TAAPI call in basic snapshot")
            snapshot = await self.api.get_market_snapshot(symbol, skip_taapi=skip_taapi)

            # Log the unified API call
            snapshot_latency = (time.time() - start_time) * 1000
            log_external_api_call(
                logger,
                source="unified_data_api",
                endpoint="get_market_snapshot",
                latency_ms=snapshot_latency,
                status_code=200,
                cache_hit=False
            )
            
            # Check if basic snapshot failed
            if isinstance(snapshot, Exception):
                logger.error(f"Basic snapshot failed: {snapshot}")
                raise snapshot
            
            # Build enhanced snapshot if MTF available, otherwise basic snapshot
            if mtf_result:
                snapshot_dict = self._build_snapshot_with_mtf(snapshot, mtf_result)
            else:
                snapshot_dict = self._build_basic_snapshot(snapshot)
            
            # Cache the result
            self._set_cache(cache_key, snapshot_dict)
            
            # Log market data only if available
            if snapshot.market:
                logger.info(
                    f"Market snapshot retrieved for {symbol}: "
                    f"price=${snapshot.market.price:.2f}, "
                    f"confidence={snapshot.overall_confidence:.2f}"
                )
            else:
                logger.warning(f"Market snapshot for {symbol} has no market data")
                raise Exception(f"Market data unavailable for {symbol}: No price data returned")

            return snapshot_dict
            
        except Exception as e:
            log_external_api_call(
                logger,
                source="unified_data_api",
                endpoint="get_market_snapshot",
                latency_ms=(time.time() - start_time) * 1000 if 'start_time' in locals() else 0,
                status_code=500,
                cache_hit=False,
                error=str(e)
            )
            raise Exception(f"Market data unavailable for {symbol}: {str(e)}")
    
    def _build_basic_snapshot(self, snapshot: MarketSnapshot) -> Dict[str, Any]:
        """Build basic snapshot (fallback when TAAPI unavailable)"""
        if not snapshot.market:
            raise ValueError(f"Cannot build snapshot: market data is None for {snapshot.symbol}")

        return {
                'symbol': snapshot.symbol,
                'timestamp': snapshot.timestamp.isoformat(),
                
                # Market data
                'market': {
                    'price': snapshot.market.price,
                    'volume_24h': snapshot.market.volume_24h,
                    'market_cap': snapshot.market.market_cap,
                    'price_change_24h': snapshot.market.price_change_24h,
                    'high_24h': snapshot.market.high_24h,
                    'low_24h': snapshot.market.low_24h,
                    'confidence': snapshot.market.confidence,
                    'sources': [s.value for s in snapshot.market.sources]
                },
                
                # Sentiment data
                'sentiment': {
                    'score': snapshot.sentiment.score,
                    'fear_greed_index': snapshot.sentiment.fear_greed_index,
                    'fear_greed_label': snapshot.sentiment.fear_greed_label,
                    'reddit_score': snapshot.sentiment.reddit_score,
                    'reddit_posts_24h': snapshot.sentiment.reddit_posts_24h,
                    'confidence': snapshot.sentiment.confidence
                } if snapshot.sentiment else None,
                
                # Technical indicators
                'technical': {
                    'rsi_14': snapshot.technical.rsi,
                    'rsi_signal': 'neutral' if not snapshot.technical.rsi else (
                        'overbought' if snapshot.technical.rsi > 70 else 
                        'oversold' if snapshot.technical.rsi < 30 else 
                        'neutral'
                    ),
                    'macd_line': snapshot.technical.macd,
                    'macd_signal': snapshot.technical.macd_signal,
                    'macd_histogram': (snapshot.technical.macd - snapshot.technical.macd_signal) 
                        if snapshot.technical.macd and snapshot.technical.macd_signal else None,
                    'macd_trend': snapshot.technical.trend,
                    'ema_20': None,  # Not available in schema
                    'ema_50': snapshot.technical.ema_50,
                    'ema_200': snapshot.technical.ema_200,
                    'confidence': snapshot.technical.confidence
                } if snapshot.technical else None,
                
                # Derivatives data
                'derivatives': {
                    'avg_funding_rate': snapshot.derivatives.avg_funding_rate,
                    'funding_by_exchange': snapshot.derivatives.funding_by_exchange,
                    'total_open_interest': snapshot.derivatives.total_open_interest,
                    'oi_change_24h': snapshot.derivatives.oi_change_24h,
                    'liquidations_24h_usd': snapshot.derivatives.liquidations_24h,  # Schema has liquidations_24h not liquidations_24h_usd
                    'confidence': snapshot.derivatives.confidence
                } if snapshot.derivatives else None,
                
                # On-chain data (when available)
                'onchain': {
                    'gas_price_gwei': snapshot.onchain.gas_price_gwei,
                    'gas_price_usd': snapshot.onchain.gas_price_usd,
                    'tvl': snapshot.onchain.tvl,
                    'tvl_change_24h': snapshot.onchain.tvl_change_24h,
                    'active_addresses_24h': snapshot.onchain.active_addresses_24h,
                    'transaction_count_24h': snapshot.onchain.transaction_count_24h,
                    'whale_transactions_24h': snapshot.onchain.whale_transactions_24h,
                    'confidence': snapshot.onchain.confidence,
                    'sources': [s.value for s in snapshot.onchain.sources]
                } if snapshot.onchain else None,

                # News data (when available)
                'news': {
                    'headlines': snapshot.news.headlines,
                    'overall_sentiment': snapshot.news.sentiment_label,
                    'sentiment_score': snapshot.news.sentiment_score,
                    'breaking_news_count': snapshot.news.breaking_news_1h,
                    'news_velocity': snapshot.news.news_velocity,
                    'confidence': snapshot.news.confidence,
                    'sources': [s.value for s in snapshot.news.sources]
                } if snapshot.news else None,

                # Order book data (when available)
                'orderbook': {
                    'imbalance_ratio': snapshot.orderbook.imbalance_ratio,
                    'imbalance_label': snapshot.orderbook.imbalance_label,
                    'spread_pct': snapshot.orderbook.spread_pct,
                    'bid_volume_usd': snapshot.orderbook.bid_volume_usd,
                    'ask_volume_usd': snapshot.orderbook.ask_volume_usd,
                    'nearest_support_price': snapshot.orderbook.nearest_support_price,
                    'nearest_resistance_price': snapshot.orderbook.nearest_resistance_price,
                    'confidence': snapshot.orderbook.confidence
                } if snapshot.orderbook else None,

                # Ultra intelligence: TVL data (DeFiLlama)
                'tvl_data': snapshot.tvl_data if snapshot.tvl_data else None,

                # Ultra intelligence: Liquidation data (Coinglass)
                'liquidation_data': snapshot.liquidation_data if snapshot.liquidation_data else None,

                # Ultra intelligence: Social sentiment (LunarCrush)
                'social_data': snapshot.social_data if snapshot.social_data else None,

                # Ultra intelligence: Comprehensive Coinglass derivatives (OI, funding, taker flow)
                'coinglass_derivatives': snapshot.coinglass_derivatives_data if snapshot.coinglass_derivatives_data else None,

                # Ultra intelligence: FRED Macro Economic Indicators (DXY, S&P500, Treasury, VIX)
                'macro_data': snapshot.macro_data if snapshot.macro_data else None,

                # Metadata
                'overall_confidence': snapshot.overall_confidence,
                'timestamp': snapshot.timestamp.isoformat(),
                'fetch_duration_ms': snapshot.fetch_duration_ms,
                'data_source': 'binance_fallback',
                'uses_multi_timeframe': False
            }
    
    def _build_snapshot_with_mtf(self, snapshot: MarketSnapshot, mtf_result: Any) -> Dict[str, Any]:
        """Build enhanced snapshot with multi-timeframe analysis"""
        basic_dict = self._build_basic_snapshot(snapshot)
        
        # Override technical section with multi-timeframe data
        mtf_dict = mtf_result.to_dict()
        
        basic_dict['technical'] = {
            'data_source': 'taapi_pro',
            'timeframes': mtf_dict['timeframes'],
            'overall_trend': mtf_dict['overall_trend'],
            'alignment_status': mtf_dict['alignment_status'],
            'alignment_confidence': mtf_dict['alignment_confidence'],
            'signals': mtf_dict['signals'],
            'volume_confirmed': mtf_dict['volume_confirmed'],
            'market_regime': mtf_dict['market_regime'],
            'recommendation': mtf_dict['recommendation'],
            'confidence': mtf_dict['confidence_score'],
            
            # Keep backward compatibility with old fields (use 4H data)
            'rsi_14': mtf_result.four_hour.rsi if mtf_result.four_hour else None,
            'rsi_signal': 'neutral',
            'macd_histogram': mtf_result.four_hour.macd_histogram if mtf_result.four_hour else None,
            'ema_50': mtf_result.four_hour.ema_50 if mtf_result.four_hour else None,
            'ema_200': mtf_result.four_hour.ema_200 if mtf_result.four_hour else None
        }
        
        # Update overall confidence with MTF alignment
        basic_dict['overall_confidence'] = mtf_dict['confidence_score']
        basic_dict['data_source'] = 'taapi_pro'
        basic_dict['uses_multi_timeframe'] = True
        
        return basic_dict
    
    async def get_sentiment_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get sentiment data for an asset

        Returns:
            Sentiment data or None if unavailable
        """
        start_time = time.time()
        try:
            # Extract base symbol (BTC from BTC/USDT)
            base_symbol = symbol.split('/')[0] if '/' in symbol else symbol

            sentiment = await self.api.get_sentiment(base_symbol)

            latency_ms = (time.time() - start_time) * 1000
            log_external_api_call(
                logger,
                source="sentiment_api",
                endpoint="get_sentiment",
                latency_ms=latency_ms,
                status_code=200 if sentiment else 404,
                cache_hit=False
            )

            if not sentiment:
                return None

            return {
                'symbol': sentiment.symbol,
                'score': sentiment.score,
                'fear_greed_index': sentiment.fear_greed_index,
                'fear_greed_label': sentiment.fear_greed_label,
                'reddit_score': sentiment.reddit_score,
                'reddit_posts_24h': sentiment.reddit_posts_24h,
                'reddit_comments_24h': sentiment.reddit_comments_24h,
                'confidence': sentiment.confidence
            }

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            log_external_api_call(
                logger,
                source="sentiment_api",
                endpoint="get_sentiment",
                latency_ms=latency_ms,
                status_code=500,
                cache_hit=False,
                error=str(e)
            )
            return None
    
    async def get_technical_indicators(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get technical indicators for a trading pair

        Returns:
            Technical indicators or None if unavailable
        """
        start_time = time.time()
        try:
            technical = await self.api.get_technical_indicators(symbol)

            latency_ms = (time.time() - start_time) * 1000
            log_external_api_call(
                logger,
                source="technical_api",
                endpoint="get_technical_indicators",
                latency_ms=latency_ms,
                status_code=200 if technical else 404,
                cache_hit=False
            )

            if not technical:
                return None

            return {
                'symbol': technical.symbol,
                'rsi_14': technical.rsi,
                'rsi_signal': 'neutral' if not technical.rsi else (
                    'overbought' if technical.rsi > 70 else
                    'oversold' if technical.rsi < 30 else
                    'neutral'
                ),
                'macd_line': technical.macd,
                'macd_signal': technical.macd_signal,
                'macd_histogram': (technical.macd - technical.macd_signal)
                    if technical.macd and technical.macd_signal else None,
                'macd_trend': technical.trend,
                'ema_20': None,  # Not available in schema
                'ema_50': technical.ema_50,
                'confidence': 0.5  # Default confidence
            }

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            log_external_api_call(
                logger,
                source="technical_api",
                endpoint="get_technical_indicators",
                latency_ms=latency_ms,
                status_code=500,
                cache_hit=False,
                error=str(e)
            )
            return None
    
    async def health_check(self) -> bool:
        """
        Check if Unified API is healthy
        
        Returns:
            True if API is responsive, False otherwise
        """
        try:
            # Try to get system health (synchronous method)
            health = self.api.get_system_health()
            
            if not health:
                return False
            
            # Check if any data source is operational
            operational_sources = [
                api_health for api_health in health.api_health
                if api_health.is_healthy
            ]
            
            return len(operational_sources) > 0
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    def _get_from_cache(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get value from cache if not expired
        """
        if key in self._cache:
            cached_value, cached_time = self._cache[key]
            
            if datetime.utcnow() - cached_time < timedelta(seconds=self._cache_ttl):
                return cached_value
            else:
                # Expired, remove from cache
                del self._cache[key]
        
        return None
    
    def _set_cache(self, key: str, value: Dict[str, Any]):
        """
        Store value in cache with timestamp
        """
        self._cache[key] = (value, datetime.utcnow())
        
        # Simple cache size management (keep last 100 entries)
        if len(self._cache) > 100:
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][1])
            del self._cache[oldest_key]
    
    def clear_cache(self):
        """
        Clear all cached data
        """
        self._cache.clear()
        self._mtf_cache.clear()
        logger.info("Cache cleared")

    def _get_mtf_from_cache(self, key: str) -> Optional[Any]:
        """
        Get MTF result from cache if not expired (30 min TTL)
        """
        if key in self._mtf_cache:
            cached_value, cached_time = self._mtf_cache[key]

            if datetime.utcnow() - cached_time < timedelta(seconds=self._mtf_cache_ttl):
                return cached_value
            else:
                # Expired, remove from cache
                del self._mtf_cache[key]

        return None

    def _set_mtf_cache(self, key: str, value: Any):
        """
        Store MTF result in cache with timestamp (30 min TTL)
        """
        self._mtf_cache[key] = (value, datetime.utcnow())

        # Simple cache size management (keep last 20 MTF entries)
        if len(self._mtf_cache) > 20:
            oldest_key = min(self._mtf_cache.keys(), key=lambda k: self._mtf_cache[k][1])
            del self._mtf_cache[oldest_key]

    async def close(self):
        """Cleanup resources - call on application shutdown"""
        if self.taapi_client:
            try:
                if hasattr(self.taapi_client, 'close'):
                    await self.taapi_client.close()
                logger.info("TAAPI client closed")
            except Exception as e:
                logger.warning(f"Error closing TAAPI client: {e}")

        if hasattr(self.api, 'close'):
            try:
                await self.api.close()
                logger.info("Unified API client closed")
            except Exception as e:
                logger.warning(f"Error closing unified API: {e}")
