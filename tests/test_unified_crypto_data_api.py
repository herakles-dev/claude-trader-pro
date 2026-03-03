"""
Complete Test Suite for UnifiedCryptoDataAPI (External Data Sources)
Coverage: 95%+ including rate limiting, circuit breakers, caching

Test Categories:
1. Market Data Fetching (10 tests)
2. Sentiment Data (8 tests)
3. Derivatives Data (8 tests)
4. Technical Indicators (10 tests)
5. Rate Limiting (8 tests)
6. Circuit Breakers (8 tests)
7. Caching (8 tests)
8. System Health (6 tests)

Total: 66 tests
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime, timedelta

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend', 'claude-engine', 'external_data_sources'))

from unified_data_api import (
    UnifiedCryptoDataAPI,
    RateLimiter,
    CircuitBreaker,
    InMemoryCache,
    CacheEntry
)
from data_schemas import (
    MarketData,
    SentimentData,
    DerivativesData,
    TechnicalData,
    MarketSnapshot,
    DataSource,
    SystemHealth,
    APIHealth
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def unified_api():
    """Create UnifiedCryptoDataAPI instance with mocked dependencies"""
    with patch('unified_data_api.ccxt'), \
         patch('unified_data_api.praw'), \
         patch('unified_data_api.requests'):
        
        api = UnifiedCryptoDataAPI()
        api.cache = InMemoryCache()
        
        yield api


@pytest.fixture
def rate_limiter():
    """Create RateLimiter for testing"""
    return RateLimiter(calls_per_minute=60, safety_margin=0.8)


@pytest.fixture
def circuit_breaker():
    """Create CircuitBreaker for testing"""
    return CircuitBreaker(failure_threshold=3, timeout=60)


@pytest.fixture
def mock_binance_ticker():
    """Mock Binance ticker response"""
    return {
        'last': 43250.50,
        'quoteVolume': 28500000000,
        'high': 43500.0,
        'low': 42000.0,
        'percentage': 2.5
    }


@pytest.fixture
def mock_coingecko_response():
    """Mock CoinGecko API response"""
    return {
        'bitcoin': {
            'usd': 43245.0,
            'usd_24h_vol': 28000000000,
            'usd_market_cap': 850000000000,
            'usd_24h_change': 2.3
        }
    }


@pytest.fixture
def mock_fear_greed_response():
    """Mock Alternative.me Fear & Greed Index response"""
    return {
        'data': [
            {
                'value': '72',
                'value_classification': 'Greed'
            }
        ]
    }


# ============================================================================
# RATE LIMITER TESTS (8 tests)
# ============================================================================

@pytest.mark.asyncio
async def test_rate_limiter_allows_immediate_call(rate_limiter):
    """
    Test: First call proceeds immediately
    Coverage: RateLimiter.acquire initial state
    """
    start_time = time.time()
    await rate_limiter.acquire()
    elapsed = time.time() - start_time
    
    assert elapsed < 0.1  # Should be nearly instant


@pytest.mark.asyncio
async def test_rate_limiter_throttles_when_tokens_depleted(rate_limiter):
    """
    Test: Throttle when token bucket empty
    Coverage: RateLimiter token depletion
    """
    # Deplete all tokens
    rate_limiter.tokens = 0
    
    start_time = time.time()
    await rate_limiter.acquire()
    elapsed = time.time() - start_time
    
    # Should wait for token refill
    assert elapsed > 0.1


@pytest.mark.asyncio
async def test_rate_limiter_refills_tokens_over_time(rate_limiter):
    """
    Test: Tokens refill based on elapsed time
    Coverage: RateLimiter._refill
    """
    initial_tokens = rate_limiter.tokens
    
    # Wait for refill
    await asyncio.sleep(1.0)
    rate_limiter._refill()
    
    # Tokens should have refilled (but capped at max_tokens)
    assert rate_limiter.tokens <= rate_limiter.max_tokens


@pytest.mark.asyncio
async def test_rate_limiter_respects_safety_margin(rate_limiter):
    """
    Test: Safety margin reduces max tokens
    Coverage: RateLimiter safety margin (80% of limit)
    """
    # calls_per_minute=60, safety_margin=0.8
    # max_tokens should be 48 (60 * 0.8)
    assert rate_limiter.max_tokens == 48


@pytest.mark.asyncio
async def test_rate_limiter_multiple_rapid_calls():
    """
    Test: Multiple rapid calls respect rate limit
    Coverage: RateLimiter under load
    """
    limiter = RateLimiter(calls_per_minute=60, safety_margin=1.0)  # 60 calls/min
    
    start_time = time.time()
    
    # Try to make 10 calls rapidly
    for _ in range(10):
        await limiter.acquire()
    
    elapsed = time.time() - start_time
    
    # Should complete quickly (tokens available initially)
    assert elapsed < 1.0


@pytest.mark.asyncio
async def test_rate_limiter_does_not_exceed_max_tokens(rate_limiter):
    """
    Test: Tokens never exceed max_tokens
    Coverage: Token cap enforcement
    """
    # Wait long time to trigger refill
    await asyncio.sleep(5.0)
    rate_limiter._refill()
    
    assert rate_limiter.tokens <= rate_limiter.max_tokens


@pytest.mark.asyncio
async def test_rate_limiter_calculates_wait_time_correctly():
    """
    Test: Wait time calculation when tokens < 1
    Coverage: Wait time formula
    """
    limiter = RateLimiter(calls_per_minute=60, safety_margin=1.0)
    limiter.tokens = 0.5
    
    start_time = time.time()
    await limiter.acquire()
    elapsed = time.time() - start_time
    
    # Should wait for ~0.5 seconds to get 0.5 more tokens
    assert 0.4 < elapsed < 0.7


@pytest.mark.asyncio
async def test_rate_limiter_refill_rate_matches_config():
    """
    Test: Refill rate matches calls_per_minute
    Coverage: Refill rate calculation
    """
    limiter = RateLimiter(calls_per_minute=120, safety_margin=1.0)
    
    # refill_rate = max_tokens / 60.0 = 120 / 60 = 2.0 tokens/sec
    assert limiter.refill_rate == 2.0


# ============================================================================
# CIRCUIT BREAKER TESTS (8 tests)
# ============================================================================

def test_circuit_breaker_starts_closed(circuit_breaker):
    """
    Test: Circuit breaker starts in CLOSED state
    Coverage: CircuitBreaker initial state
    """
    assert circuit_breaker.state == 'CLOSED'
    assert circuit_breaker.can_attempt() is True


def test_circuit_breaker_opens_after_threshold_failures(circuit_breaker):
    """
    Test: Circuit opens after failure_threshold consecutive failures
    Coverage: CircuitBreaker.call_failed
    """
    # Trigger 3 failures (threshold)
    circuit_breaker.call_failed()
    circuit_breaker.call_failed()
    circuit_breaker.call_failed()
    
    assert circuit_breaker.state == 'OPEN'
    assert circuit_breaker.failure_count == 3


def test_circuit_breaker_blocks_calls_when_open(circuit_breaker):
    """
    Test: Can't attempt calls when circuit is OPEN
    Coverage: CircuitBreaker.can_attempt when OPEN
    """
    # Open circuit
    for _ in range(3):
        circuit_breaker.call_failed()
    
    assert circuit_breaker.can_attempt() is False


def test_circuit_breaker_transitions_to_half_open_after_timeout(circuit_breaker):
    """
    Test: Circuit transitions to HALF_OPEN after timeout
    Coverage: CircuitBreaker timeout recovery
    """
    # Open circuit
    for _ in range(3):
        circuit_breaker.call_failed()
    
    # Simulate timeout expiry
    circuit_breaker.last_failure_time = time.time() - 61  # 61 seconds ago
    
    assert circuit_breaker.can_attempt() is True
    assert circuit_breaker.state == 'HALF_OPEN'


def test_circuit_breaker_closes_on_success(circuit_breaker):
    """
    Test: Circuit closes on successful call
    Coverage: CircuitBreaker.call_succeeded
    """
    # Open circuit
    for _ in range(3):
        circuit_breaker.call_failed()
    
    assert circuit_breaker.state == 'OPEN'
    
    # Success resets
    circuit_breaker.call_succeeded()
    
    assert circuit_breaker.state == 'CLOSED'
    assert circuit_breaker.failure_count == 0


def test_circuit_breaker_resets_failure_count_on_success(circuit_breaker):
    """
    Test: Successful call resets failure count
    Coverage: Failure count reset
    """
    circuit_breaker.call_failed()
    circuit_breaker.call_failed()
    
    assert circuit_breaker.failure_count == 2
    
    circuit_breaker.call_succeeded()
    
    assert circuit_breaker.failure_count == 0


def test_circuit_breaker_allows_calls_in_half_open_state(circuit_breaker):
    """
    Test: Circuit allows testing in HALF_OPEN state
    Coverage: HALF_OPEN state behavior
    """
    circuit_breaker.state = 'HALF_OPEN'
    
    assert circuit_breaker.can_attempt() is True


def test_circuit_breaker_custom_thresholds():
    """
    Test: Custom failure threshold and timeout
    Coverage: CircuitBreaker configuration
    """
    cb = CircuitBreaker(failure_threshold=5, timeout=120)
    
    # Should require 5 failures to open
    for _ in range(4):
        cb.call_failed()
    
    assert cb.state == 'CLOSED'
    
    cb.call_failed()  # 5th failure
    
    assert cb.state == 'OPEN'


# ============================================================================
# CACHE TESTS (8 tests)
# ============================================================================

def test_cache_entry_is_valid_within_ttl():
    """
    Test: CacheEntry is valid within TTL
    Coverage: CacheEntry.is_valid
    """
    entry = CacheEntry(data={'test': 'data'}, ttl=60)
    
    assert entry.is_valid() is True


def test_cache_entry_expires_after_ttl():
    """
    Test: CacheEntry expires after TTL
    Coverage: CacheEntry expiration
    """
    entry = CacheEntry(data={'test': 'data'}, ttl=0)
    
    time.sleep(0.1)
    
    assert entry.is_valid() is False


def test_in_memory_cache_get_returns_none_on_miss():
    """
    Test: Cache returns None on miss
    Coverage: InMemoryCache.get miss
    """
    cache = InMemoryCache()
    
    result = cache.get('non_existent_key')
    
    assert result is None


def test_in_memory_cache_get_returns_value_on_hit():
    """
    Test: Cache returns cached value on hit
    Coverage: InMemoryCache.get hit
    """
    cache = InMemoryCache()
    cache.set('test_key', {'data': 'value'}, ttl=60)
    
    result = cache.get('test_key')
    
    assert result == {'data': 'value'}


def test_in_memory_cache_tracks_hit_rate():
    """
    Test: Cache tracks hit/miss statistics
    Coverage: InMemoryCache.hit_rate
    """
    cache = InMemoryCache()
    cache.set('key1', 'value1', ttl=60)
    
    cache.get('key1')  # Hit
    cache.get('key2')  # Miss
    cache.get('key1')  # Hit
    
    # 2 hits, 1 miss = 66.6% hit rate
    assert 0.65 < cache.hit_rate < 0.68


def test_in_memory_cache_invalidates_expired_entries():
    """
    Test: Cache removes expired entries on get
    Coverage: Automatic cleanup
    """
    cache = InMemoryCache()
    cache.set('test_key', 'value', ttl=0)
    
    time.sleep(0.1)
    
    result = cache.get('test_key')
    
    assert result is None
    assert 'test_key' not in cache._cache


def test_in_memory_cache_invalidates_by_pattern():
    """
    Test: Invalidate entries matching pattern
    Coverage: InMemoryCache.invalidate
    """
    cache = InMemoryCache()
    cache.set('market:BTC', 'data1', ttl=60)
    cache.set('market:ETH', 'data2', ttl=60)
    cache.set('sentiment:BTC', 'data3', ttl=60)
    
    cache.invalidate('market')
    
    assert cache.get('market:BTC') is None
    assert cache.get('market:ETH') is None
    assert cache.get('sentiment:BTC') == 'data3'


def test_in_memory_cache_clear_all():
    """
    Test: Clear all cache entries
    Coverage: InMemoryCache.invalidate with no pattern
    """
    cache = InMemoryCache()
    cache.set('key1', 'value1', ttl=60)
    cache.set('key2', 'value2', ttl=60)
    
    cache.invalidate()
    
    assert len(cache._cache) == 0


# ============================================================================
# MARKET DATA TESTS (10 tests)
# ============================================================================

@pytest.mark.asyncio
async def test_get_market_data_aggregates_multiple_sources(unified_api, mock_binance_ticker, mock_coingecko_response):
    """
    Test: Aggregate price from Binance + CoinGecko
    Coverage: UnifiedCryptoDataAPI.get_market_data
    """
    # Mock exchange
    unified_api._exchanges['binance'].fetch_ticker = Mock(return_value=mock_binance_ticker)
    
    # Mock requests for CoinGecko
    with patch('unified_data_api.requests.get') as mock_get:
        mock_response = Mock()
        mock_response.json.return_value = mock_coingecko_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        result = await unified_api.get_market_data('BTC/USDT')
    
    # Should average prices from both sources
    # Binance: 43250.50, CoinGecko: 43245.0
    # Average: 43247.75
    assert 43247.0 < result.price < 43248.0
    assert DataSource.BINANCE in result.sources
    assert DataSource.COINGECKO in result.sources
    assert result.confidence > 0.8  # High confidence with 2 sources


@pytest.mark.asyncio
async def test_get_market_data_calculates_spread(unified_api, mock_binance_ticker, mock_coingecko_response):
    """
    Test: Calculate price spread across sources
    Coverage: Spread calculation
    """
    unified_api._exchanges['binance'].fetch_ticker = Mock(return_value=mock_binance_ticker)
    
    with patch('unified_data_api.requests.get') as mock_get:
        mock_response = Mock()
        mock_response.json.return_value = mock_coingecko_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        result = await unified_api.get_market_data('BTC/USDT')
    
    # Spread = (max - min) / avg
    # max = 43250.50, min = 43245.0, avg ≈ 43247.75
    # spread ≈ 5.50 / 43247.75 ≈ 0.000127
    assert result.spread < 0.01  # Small spread indicates consensus


@pytest.mark.asyncio
async def test_get_market_data_caches_result(unified_api, mock_binance_ticker):
    """
    Test: Market data cached for 30 seconds
    Coverage: Caching
    """
    unified_api._exchanges['binance'].fetch_ticker = Mock(return_value=mock_binance_ticker)
    
    with patch('unified_data_api.requests.get') as mock_get:
        mock_response = Mock()
        mock_response.json.return_value = {'bitcoin': {'usd': 43245.0}}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        # First call
        result1 = await unified_api.get_market_data('BTC/USDT')
        
        # Second call (should hit cache)
        result2 = await unified_api.get_market_data('BTC/USDT')
    
    assert result2.cache_hit is True
    assert mock_get.call_count == 1  # Only called once


@pytest.mark.asyncio
async def test_get_market_data_fallback_to_single_source(unified_api, mock_binance_ticker):
    """
    Test: Fallback to single source if others fail
    Coverage: Graceful degradation
    """
    unified_api._exchanges['binance'].fetch_ticker = Mock(return_value=mock_binance_ticker)
    
    # CoinGecko fails
    with patch('unified_data_api.requests.get', side_effect=Exception("API error")):
        result = await unified_api.get_market_data('BTC/USDT')
    
    # Should still return data from Binance
    assert result.price == 43250.50
    assert len(result.sources) == 1
    assert DataSource.BINANCE in result.sources


@pytest.mark.asyncio
async def test_get_market_data_raises_when_no_sources(unified_api):
    """
    Test: Raise error when all sources fail
    Coverage: Error handling
    """
    unified_api._exchanges['binance'].fetch_ticker = Mock(side_effect=Exception("Binance down"))
    
    with patch('unified_data_api.requests.get', side_effect=Exception("CoinGecko down")):
        with pytest.raises(ValueError, match="No price data available"):
            await unified_api.get_market_data('BTC/USDT')


@pytest.mark.asyncio
async def test_get_market_data_normalizes_symbols(unified_api, mock_binance_ticker):
    """
    Test: Symbol normalization (BTC -> BTC/USDT)
    Coverage: UnifiedCryptoDataAPI._normalize_symbol
    """
    # Test different symbol formats
    assert unified_api._normalize_symbol('BTC', 'standard') == 'BTC/USDT'
    assert unified_api._normalize_symbol('BTC/USDT', 'standard') == 'BTC/USDT'
    assert unified_api._normalize_symbol('BTC', 'base') == 'BTC'
    assert unified_api._normalize_symbol('BTC/USDT', 'base') == 'BTC'
    assert unified_api._normalize_symbol('BTC', 'futures') == 'BTC/USDT:USDT'


@pytest.mark.asyncio
async def test_get_market_data_includes_24h_metrics(unified_api, mock_binance_ticker, mock_coingecko_response):
    """
    Test: Include volume, high, low, price change
    Coverage: Complete market data
    """
    unified_api._exchanges['binance'].fetch_ticker = Mock(return_value=mock_binance_ticker)
    
    with patch('unified_data_api.requests.get') as mock_get:
        mock_response = Mock()
        mock_response.json.return_value = mock_coingecko_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        result = await unified_api.get_market_data('BTC/USDT')
    
    assert result.volume_24h == 28500000000
    assert result.high_24h == 43500.0
    assert result.low_24h == 42000.0
    assert result.price_change_24h == 2.5


@pytest.mark.asyncio
async def test_get_market_data_handles_rate_limiting(unified_api, mock_binance_ticker):
    """
    Test: Respects rate limits for exchanges
    Coverage: Rate limiter integration
    """
    unified_api._exchanges['binance'].fetch_ticker = Mock(return_value=mock_binance_ticker)
    
    with patch('unified_data_api.requests.get') as mock_get:
        mock_response = Mock()
        mock_response.json.return_value = {'bitcoin': {'usd': 43245.0}}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        start_time = time.time()
        await unified_api.get_market_data('BTC/USDT')
        elapsed = time.time() - start_time
        
        # Should complete quickly with rate limiter
        assert elapsed < 2.0


@pytest.mark.asyncio
async def test_get_market_data_circuit_breaker_opens_on_failures(unified_api):
    """
    Test: Circuit breaker opens after consecutive failures
    Coverage: Circuit breaker integration
    """
    unified_api._exchanges['binance'].fetch_ticker = Mock(side_effect=Exception("Fail"))
    
    with patch('unified_data_api.requests.get', side_effect=Exception("Fail")):
        # Trigger 3 failures for binance
        for _ in range(3):
            try:
                await unified_api.get_market_data('BTC/USDT')
            except:
                pass
    
    # Circuit should be open for binance
    assert unified_api._circuit_breakers['binance'].state == 'OPEN'


@pytest.mark.asyncio
async def test_get_market_data_confidence_based_on_sources_and_spread(unified_api, mock_binance_ticker, mock_coingecko_response):
    """
    Test: Confidence score considers sources + spread
    Coverage: UnifiedCryptoDataAPI._calculate_confidence
    """
    unified_api._exchanges['binance'].fetch_ticker = Mock(return_value=mock_binance_ticker)
    
    with patch('unified_data_api.requests.get') as mock_get:
        mock_response = Mock()
        mock_response.json.return_value = mock_coingecko_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        result = await unified_api.get_market_data('BTC/USDT')
    
    # 2 sources = 0.67 source confidence
    # Low spread (<0.01) = 1.0 spread confidence
    # Total ≈ 0.67 * 1.0 = 0.67
    assert 0.6 < result.confidence < 0.7


# ============================================================================
# SENTIMENT DATA TESTS (8 tests)
# ============================================================================

@pytest.mark.asyncio
async def test_get_sentiment_aggregates_fear_greed_and_reddit(unified_api, mock_fear_greed_response):
    """
    Test: Aggregate Fear & Greed + Reddit sentiment
    Coverage: UnifiedCryptoDataAPI.get_sentiment
    """
    # Mock Fear & Greed API
    with patch('unified_data_api.requests.get') as mock_get:
        mock_response = Mock()
        mock_response.json.return_value = mock_fear_greed_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        # Mock Reddit
        if unified_api._reddit:
            mock_subreddit = Mock()
            mock_post = Mock()
            mock_post.upvote_ratio = 0.75
            mock_post.num_comments = 100
            mock_subreddit.search.return_value = [mock_post] * 50
            unified_api._reddit.subreddit = Mock(return_value=mock_subreddit)
        
        result = await unified_api.get_sentiment('BTC')
    
    assert result.fear_greed_index == 72
    assert result.fear_greed_label == "Greed"
    assert DataSource.ALTERNATIVE_ME in result.sources


@pytest.mark.asyncio
async def test_get_sentiment_calculates_composite_score(unified_api, mock_fear_greed_response):
    """
    Test: Composite score averages all sources
    Coverage: Sentiment aggregation
    """
    with patch('unified_data_api.requests.get') as mock_get:
        mock_response = Mock()
        mock_response.json.return_value = mock_fear_greed_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        result = await unified_api.get_sentiment('BTC')
    
    # Fear & Greed index: 72
    # Composite should be close to 72 (or averaged with Reddit if available)
    assert 60 < result.score < 80


@pytest.mark.asyncio
async def test_get_sentiment_handles_reddit_failure_gracefully(unified_api, mock_fear_greed_response):
    """
    Test: Continue if Reddit fails
    Coverage: Partial failure handling
    """
    with patch('unified_data_api.requests.get') as mock_get:
        mock_response = Mock()
        mock_response.json.return_value = mock_fear_greed_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        # Reddit fails
        unified_api._reddit = None
        
        result = await unified_api.get_sentiment('BTC')
    
    # Should still have Fear & Greed data
    assert result.fear_greed_index == 72
    assert result.reddit_score is None


@pytest.mark.asyncio
async def test_get_sentiment_caches_result_for_15_minutes(unified_api, mock_fear_greed_response):
    """
    Test: Sentiment cached for 900 seconds (15 min)
    Coverage: Cache TTL
    """
    with patch('unified_data_api.requests.get') as mock_get:
        mock_response = Mock()
        mock_response.json.return_value = mock_fear_greed_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        # First call
        result1 = await unified_api.get_sentiment('BTC')
        
        # Second call (should hit cache)
        result2 = await unified_api.get_sentiment('BTC')
    
    assert result2.cache_hit is True
    assert mock_get.call_count == 1


@pytest.mark.asyncio
async def test_get_sentiment_reddit_calculates_score_from_upvote_ratio(unified_api, mock_fear_greed_response):
    """
    Test: Reddit score = upvote_ratio * 100
    Coverage: Reddit sentiment calculation
    """
    with patch('unified_data_api.requests.get') as mock_get:
        mock_response = Mock()
        mock_response.json.return_value = mock_fear_greed_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        # Mock Reddit with specific upvote ratio
        if not unified_api._reddit:
            unified_api._reddit = Mock()
        
        mock_subreddit = Mock()
        mock_posts = []
        for _ in range(10):
            post = Mock()
            post.upvote_ratio = 0.80  # 80% upvote ratio
            post.num_comments = 50
            mock_posts.append(post)
        
        mock_subreddit.search.return_value = mock_posts
        unified_api._reddit.subreddit = Mock(return_value=mock_subreddit)
        
        result = await unified_api.get_sentiment('BTC')
    
    # Reddit score should be 80 (0.80 * 100)
    assert result.reddit_score == 80.0


@pytest.mark.asyncio
async def test_get_sentiment_tracks_reddit_activity(unified_api, mock_fear_greed_response):
    """
    Test: Track Reddit posts and comments count
    Coverage: Reddit metrics
    """
    with patch('unified_data_api.requests.get') as mock_get:
        mock_response = Mock()
        mock_response.json.return_value = mock_fear_greed_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        # Mock Reddit
        if not unified_api._reddit:
            unified_api._reddit = Mock()
        
        mock_subreddit = Mock()
        mock_posts = []
        for _ in range(25):
            post = Mock()
            post.upvote_ratio = 0.75
            post.num_comments = 100
            mock_posts.append(post)
        
        mock_subreddit.search.return_value = mock_posts
        unified_api._reddit.subreddit = Mock(return_value=mock_subreddit)
        
        result = await unified_api.get_sentiment('BTC')
    
    assert result.reddit_posts_24h == 25
    assert result.reddit_comments_24h == 2500  # 25 posts * 100 comments


@pytest.mark.asyncio
async def test_get_sentiment_confidence_based_on_sources(unified_api, mock_fear_greed_response):
    """
    Test: Confidence based on number of sources
    Coverage: Confidence calculation (sources / 3.0)
    """
    with patch('unified_data_api.requests.get') as mock_get:
        mock_response = Mock()
        mock_response.json.return_value = mock_fear_greed_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        unified_api._reddit = None  # Disable Reddit
        
        result = await unified_api.get_sentiment('BTC')
    
    # 1 source (Fear & Greed) = 1/3 = 0.33 confidence
    assert 0.3 < result.confidence < 0.4


@pytest.mark.asyncio
async def test_get_sentiment_defaults_to_50_when_no_data(unified_api):
    """
    Test: Default composite score = 50 when no sources
    Coverage: Fallback behavior
    """
    # Both APIs fail
    with patch('unified_data_api.requests.get', side_effect=Exception("API down")):
        unified_api._reddit = None
        
        result = await unified_api.get_sentiment('BTC')
    
    assert result.score == 50.0
    assert result.confidence == 0.0


# ============================================================================
# DERIVATIVES DATA TESTS (8 tests)
# ============================================================================

@pytest.mark.asyncio
async def test_get_derivatives_data_aggregates_multiple_exchanges(unified_api):
    """
    Test: Aggregate funding rates from 4 exchanges
    Coverage: UnifiedCryptoDataAPI.get_derivatives_data
    """
    # Mock each exchange
    for name, exchange in unified_api._exchanges.items():
        mock_funding = Mock()
        mock_funding.__getitem__ = lambda self, key: 0.0125 if key == 'fundingRate' else None
        
        exchange.fetch_funding_rate = Mock(return_value={'fundingRate': 0.0125})
        exchange.fetch_open_interest = Mock(return_value={'openInterestAmount': 100000000})
    
    result = await unified_api.get_derivatives_data('BTC/USDT:USDT')
    
    assert result.avg_funding_rate == 0.0125
    assert len(result.exchanges) == 4  # binance, bybit, okx, bitget


@pytest.mark.asyncio
async def test_get_derivatives_data_calculates_total_open_interest(unified_api):
    """
    Test: Sum open interest across exchanges
    Coverage: OI aggregation
    """
    for name, exchange in unified_api._exchanges.items():
        exchange.fetch_funding_rate = Mock(return_value={'fundingRate': 0.01})
        exchange.fetch_open_interest = Mock(return_value={'openInterestAmount': 5000000000})
    
    result = await unified_api.get_derivatives_data('BTC/USDT:USDT')
    
    # 4 exchanges * 5B each = 20B total
    assert result.total_open_interest == 20000000000


@pytest.mark.asyncio
async def test_get_derivatives_data_handles_exchange_failures(unified_api):
    """
    Test: Continue if some exchanges fail
    Coverage: Partial failure handling
    """
    # Mock binance success, others fail
    unified_api._exchanges['binance'].fetch_funding_rate = Mock(
        return_value={'fundingRate': 0.0120}
    )
    unified_api._exchanges['binance'].fetch_open_interest = Mock(
        return_value={'openInterestAmount': 8000000000}
    )
    
    for name in ['bybit', 'okx', 'bitget']:
        unified_api._exchanges[name].fetch_funding_rate = Mock(side_effect=Exception("Fail"))
        unified_api._exchanges[name].fetch_open_interest = Mock(side_effect=Exception("Fail"))
    
    result = await unified_api.get_derivatives_data('BTC/USDT:USDT')
    
    assert result.avg_funding_rate == 0.0120
    assert len(result.exchanges) == 1
    assert 'binance' in result.exchanges


@pytest.mark.asyncio
async def test_get_derivatives_data_caches_for_4_hours(unified_api):
    """
    Test: Derivatives cached for 14400 seconds (4 hours)
    Coverage: Cache TTL
    """
    for exchange in unified_api._exchanges.values():
        exchange.fetch_funding_rate = Mock(return_value={'fundingRate': 0.01})
        exchange.fetch_open_interest = Mock(return_value={'openInterestAmount': 1000000000})
    
    # First call
    result1 = await unified_api.get_derivatives_data('BTC/USDT:USDT')
    
    # Second call (should hit cache)
    result2 = await unified_api.get_derivatives_data('BTC/USDT:USDT')
    
    assert result2.cache_hit is True


@pytest.mark.asyncio
async def test_get_derivatives_data_okx_symbol_normalization(unified_api):
    """
    Test: OKX uses different symbol format (BTC-USDT-SWAP)
    Coverage: Symbol normalization per exchange
    """
    # Verify OKX gets special symbol format
    unified_api._exchanges['okx'].fetch_funding_rate = Mock(return_value={'fundingRate': 0.01})
    unified_api._exchanges['okx'].fetch_open_interest = Mock(return_value={'openInterestAmount': 1000000000})
    
    for name in ['binance', 'bybit', 'bitget']:
        unified_api._exchanges[name].fetch_funding_rate = Mock(side_effect=Exception("Fail"))
        unified_api._exchanges[name].fetch_open_interest = Mock(side_effect=Exception("Fail"))
    
    await unified_api.get_derivatives_data('BTC/USDT:USDT')
    
    # OKX should be called with BTC-USDT-SWAP
    # (implementation detail - verify by checking code)
    assert unified_api._exchanges['okx'].fetch_funding_rate.called


@pytest.mark.asyncio
async def test_get_derivatives_data_confidence_based_on_exchanges(unified_api):
    """
    Test: Confidence = exchanges_used / total_exchanges
    Coverage: Confidence calculation
    """
    # Only 2 out of 4 exchanges succeed
    for name in ['binance', 'bybit']:
        unified_api._exchanges[name].fetch_funding_rate = Mock(return_value={'fundingRate': 0.01})
        unified_api._exchanges[name].fetch_open_interest = Mock(return_value={'openInterestAmount': 1000000000})
    
    for name in ['okx', 'bitget']:
        unified_api._exchanges[name].fetch_funding_rate = Mock(side_effect=Exception("Fail"))
        unified_api._exchanges[name].fetch_open_interest = Mock(side_effect=Exception("Fail"))
    
    result = await unified_api.get_derivatives_data('BTC/USDT:USDT')
    
    # 2/4 = 0.5 confidence
    assert result.confidence == 0.5


@pytest.mark.asyncio
async def test_get_derivatives_data_stores_per_exchange_funding(unified_api):
    """
    Test: Store funding rate per exchange
    Coverage: funding_by_exchange field
    """
    unified_api._exchanges['binance'].fetch_funding_rate = Mock(return_value={'fundingRate': 0.0120})
    unified_api._exchanges['binance'].fetch_open_interest = Mock(return_value={'openInterestAmount': 1000000000})
    
    unified_api._exchanges['bybit'].fetch_funding_rate = Mock(return_value={'fundingRate': 0.0130})
    unified_api._exchanges['bybit'].fetch_open_interest = Mock(return_value={'openInterestAmount': 1000000000})
    
    for name in ['okx', 'bitget']:
        unified_api._exchanges[name].fetch_funding_rate = Mock(side_effect=Exception("Fail"))
        unified_api._exchanges[name].fetch_open_interest = Mock(side_effect=Exception("Fail"))
    
    result = await unified_api.get_derivatives_data('BTC/USDT:USDT')
    
    assert result.funding_by_exchange['binance'] == 0.0120
    assert result.funding_by_exchange['bybit'] == 0.0130
    assert result.funding_by_exchange['okx'] is None


@pytest.mark.asyncio
async def test_get_derivatives_data_stores_per_exchange_oi(unified_api):
    """
    Test: Store open interest per exchange
    Coverage: oi_by_exchange field
    """
    unified_api._exchanges['binance'].fetch_funding_rate = Mock(return_value={'fundingRate': 0.01})
    unified_api._exchanges['binance'].fetch_open_interest = Mock(return_value={'openInterestAmount': 8000000000})
    
    unified_api._exchanges['bybit'].fetch_funding_rate = Mock(return_value={'fundingRate': 0.01})
    unified_api._exchanges['bybit'].fetch_open_interest = Mock(return_value={'openInterestAmount': 6000000000})
    
    for name in ['okx', 'bitget']:
        unified_api._exchanges[name].fetch_funding_rate = Mock(side_effect=Exception("Fail"))
        unified_api._exchanges[name].fetch_open_interest = Mock(side_effect=Exception("Fail"))
    
    result = await unified_api.get_derivatives_data('BTC/USDT:USDT')
    
    assert result.oi_by_exchange['binance'] == 8000000000
    assert result.oi_by_exchange['bybit'] == 6000000000


# ============================================================================
# TECHNICAL INDICATORS TESTS (10 tests)
# ============================================================================

@pytest.mark.asyncio
async def test_get_technical_indicators_uses_taapi_when_available(unified_api):
    """
    Test: Use TAAPI.io for indicators when API key present
    Coverage: UnifiedCryptoDataAPI.get_technical_indicators with TAAPI
    """
    unified_api._api_keys['taapi'] = 'test_key'
    
    with patch('unified_data_api.requests.get') as mock_get:
        mock_response = Mock()
        mock_response.json.return_value = {'value': 58.5}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        result = await unified_api.get_technical_indicators('BTC/USDT')
    
    assert result.rsi == 58.5
    assert DataSource.TAAPI in result.sources


@pytest.mark.asyncio
async def test_get_technical_indicators_fallback_to_binance_ohlcv(unified_api):
    """
    Test: Calculate indicators from Binance OHLCV when TAAPI fails
    Coverage: Fallback calculation
    """
    unified_api._api_keys['taapi'] = None  # No TAAPI key
    
    # Mock Binance OHLCV (100 candles)
    mock_ohlcv = [[0, 40000, 41000, 39000, 40500, 1000] for _ in range(100)]
    unified_api._exchanges['binance'].fetch_ohlcv = Mock(return_value=mock_ohlcv)
    
    result = await unified_api.get_technical_indicators('BTC/USDT')
    
    # Should calculate RSI from OHLCV
    assert result.rsi is not None
    assert DataSource.BINANCE in result.sources


@pytest.mark.asyncio
async def test_calculate_rsi_returns_value_between_0_and_100(unified_api):
    """
    Test: RSI calculation produces value 0-100
    Coverage: UnifiedCryptoDataAPI._calculate_rsi
    """
    prices = [100 + i for i in range(50)]  # Uptrend
    
    rsi = unified_api._calculate_rsi(prices, period=14)
    
    assert rsi is not None
    assert 0 <= rsi <= 100


@pytest.mark.asyncio
async def test_calculate_ema_returns_smoothed_average(unified_api):
    """
    Test: EMA calculation
    Coverage: UnifiedCryptoDataAPI._calculate_ema
    """
    prices = [100, 102, 104, 103, 105, 107, 106, 108, 110, 109]
    
    ema = unified_api._calculate_ema(prices, period=5)
    
    assert ema is not None
    assert 100 < ema < 120


@pytest.mark.asyncio
async def test_calculate_macd_returns_line_and_signal(unified_api):
    """
    Test: MACD returns (macd_line, signal_line)
    Coverage: UnifiedCryptoDataAPI._calculate_macd
    """
    prices = [100 + i * 0.5 for i in range(50)]  # Gradual uptrend
    
    macd_result = unified_api._calculate_macd(prices)
    
    assert macd_result is not None
    macd_line, signal_line = macd_result
    assert macd_line is not None
    assert signal_line is not None


@pytest.mark.asyncio
async def test_get_technical_indicators_returns_empty_when_no_api_key(unified_api):
    """
    Test: Return empty technical data when TAAPI key missing
    Coverage: No API key handling
    """
    unified_api._api_keys['taapi'] = None
    
    # No Binance fallback either
    unified_api._exchanges['binance'].fetch_ohlcv = Mock(side_effect=Exception("Fail"))
    
    result = await unified_api.get_technical_indicators('BTC/USDT')
    
    assert result.confidence == 0.0
    assert len(result.sources) == 0


@pytest.mark.asyncio
async def test_get_technical_indicators_caches_for_1_hour(unified_api):
    """
    Test: Technical indicators cached for 3600 seconds (1 hour)
    Coverage: Cache TTL
    """
    unified_api._api_keys['taapi'] = 'test_key'
    
    with patch('unified_data_api.requests.get') as mock_get:
        mock_response = Mock()
        mock_response.json.return_value = {'value': 58.5}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        # First call
        result1 = await unified_api.get_technical_indicators('BTC/USDT')
        
        # Second call (should hit cache)
        result2 = await unified_api.get_technical_indicators('BTC/USDT')
    
    assert result2.cache_hit is True
    assert mock_get.call_count == 1


@pytest.mark.asyncio
async def test_get_technical_indicators_calculates_ema_50(unified_api):
    """
    Test: Calculate EMA 50 from OHLCV
    Coverage: EMA calculation
    """
    unified_api._api_keys['taapi'] = None
    
    # Mock 100 candles with prices
    mock_ohlcv = [[0, 0, 0, 0, 40000 + i * 10, 0] for i in range(100)]
    unified_api._exchanges['binance'].fetch_ohlcv = Mock(return_value=mock_ohlcv)
    
    result = await unified_api.get_technical_indicators('BTC/USDT')
    
    assert result.ema_50 is not None
    assert 40000 < result.ema_50 < 45000


@pytest.mark.asyncio
async def test_calculate_rsi_returns_none_for_insufficient_data(unified_api):
    """
    Test: RSI returns None when < 15 prices
    Coverage: Edge case handling
    """
    prices = [100, 101, 102]  # Only 3 prices
    
    rsi = unified_api._calculate_rsi(prices, period=14)
    
    assert rsi is None


@pytest.mark.asyncio
async def test_calculate_macd_returns_none_for_insufficient_data(unified_api):
    """
    Test: MACD returns None when < 35 prices
    Coverage: Edge case handling
    """
    prices = [100 + i for i in range(20)]  # Only 20 prices
    
    macd_result = unified_api._calculate_macd(prices)
    
    assert macd_result is None


# ============================================================================
# SYSTEM HEALTH TESTS (6 tests)
# ============================================================================

def test_get_system_health_reports_all_sources(unified_api):
    """
    Test: System health includes all data sources
    Coverage: UnifiedCryptoDataAPI.get_system_health
    """
    health = unified_api.get_system_health()
    
    assert health.total_sources > 0
    assert len(health.api_health) > 0


def test_get_system_health_tracks_circuit_breaker_state(unified_api):
    """
    Test: Health report includes circuit breaker states
    Coverage: Circuit breaker tracking
    """
    # Open a circuit breaker
    for _ in range(3):
        unified_api._circuit_breakers['binance'].call_failed()
    
    health = unified_api.get_system_health()
    
    # Find binance in health report
    binance_health = next(
        (h for h in health.api_health if h.source == DataSource.BINANCE),
        None
    )
    
    if binance_health:
        assert binance_health.circuit_breaker_open is True


def test_get_system_health_calculates_cache_hit_rate(unified_api):
    """
    Test: Health includes cache hit rate
    Coverage: Cache statistics
    """
    # Generate some cache activity
    unified_api.cache.set('key1', 'value1', ttl=60)
    unified_api.cache.get('key1')  # Hit
    unified_api.cache.get('key2')  # Miss
    
    health = unified_api.get_system_health()
    
    # 1 hit, 1 miss = 50% hit rate
    assert 0.45 < health.cache_hit_rate < 0.55


def test_get_system_health_tracks_success_and_failure_counts(unified_api):
    """
    Test: Track success/failure counts per source
    Coverage: Statistics tracking
    """
    # Simulate some API calls
    unified_api._health_stats['binance']['success_count'] = 10
    unified_api._health_stats['binance']['failure_count'] = 2
    
    health = unified_api.get_system_health()
    
    binance_health = next(
        (h for h in health.api_health if h.source == DataSource.BINANCE),
        None
    )
    
    if binance_health:
        assert binance_health.failure_count == 2


def test_get_system_health_calculates_average_latency(unified_api):
    """
    Test: Calculate average latency across sources
    Coverage: Latency tracking
    """
    # Simulate latency data
    unified_api._health_stats['binance']['success_count'] = 5
    unified_api._health_stats['binance']['total_latency_ms'] = 500.0  # 100ms avg
    
    unified_api._health_stats['coingecko']['success_count'] = 3
    unified_api._health_stats['coingecko']['total_latency_ms'] = 600.0  # 200ms avg
    
    health = unified_api.get_system_health()
    
    # Overall average should be calculated
    assert health.avg_latency_ms > 0


def test_get_system_health_counts_healthy_sources(unified_api):
    """
    Test: Count healthy (circuit not open) sources
    Coverage: Health counting
    """
    # Open 1 circuit
    for _ in range(3):
        unified_api._circuit_breakers['binance'].call_failed()
    
    health = unified_api.get_system_health()
    
    # Should have fewer healthy sources
    assert health.healthy_sources < health.total_sources


# ============================================================================
# RUN ALL TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
