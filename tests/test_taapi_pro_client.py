"""
Unit tests for TaapiProClient

Tests bulk endpoint support, rate limiting, caching, and error handling.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend', 'claude-engine', 'external_data_sources'))

from taapi_pro_client import (
    TaapiProClient,
    TaapiRateLimiter,
    TaapiResponse,
    IndicatorConfig
)


class TestIndicatorConfig:
    """Test IndicatorConfig dataclass"""
    
    def test_indicator_config_basic(self):
        """Test basic indicator config"""
        config = IndicatorConfig('rsi', period=14)
        assert config.indicator == 'rsi'
        assert config.period == 14
        assert config.backtrack is None
    
    def test_indicator_config_to_dict_with_period(self):
        """Test to_dict includes period"""
        config = IndicatorConfig('rsi', period=14)
        result = config.to_dict()
        assert result == {'indicator': 'rsi', 'period': 14}
    
    def test_indicator_config_to_dict_without_period(self):
        """Test to_dict excludes None values"""
        config = IndicatorConfig('macd')
        result = config.to_dict()
        assert result == {'indicator': 'macd'}
    
    def test_indicator_config_with_backtrack(self):
        """Test backtrack parameter"""
        config = IndicatorConfig('rsi', period=14, backtrack=50)
        result = config.to_dict()
        assert result == {'indicator': 'rsi', 'period': 14, 'backtrack': 50}


class TestTaapiResponse:
    """Test TaapiResponse dataclass"""
    
    def test_taapi_response_creation(self):
        """Test creating TaapiResponse"""
        response = TaapiResponse(
            symbol='BTC/USDT',
            exchange='binance',
            interval='4h',
            indicators={'rsi': 65.5},
            timestamp=datetime.utcnow()
        )
        assert response.symbol == 'BTC/USDT'
        assert response.indicators['rsi'] == 65.5
        assert response.cache_hit is False
    
    def test_get_indicator_exists(self):
        """Test get_indicator for existing indicator"""
        response = TaapiResponse(
            symbol='BTC/USDT',
            exchange='binance',
            interval='4h',
            indicators={'rsi': 65.5, 'adx': 28.3},
            timestamp=datetime.utcnow()
        )
        assert response.get_indicator('rsi') == 65.5
        assert response.get_indicator('adx') == 28.3
    
    def test_get_indicator_missing(self):
        """Test get_indicator with default for missing indicator"""
        response = TaapiResponse(
            symbol='BTC/USDT',
            exchange='binance',
            interval='4h',
            indicators={},
            timestamp=datetime.utcnow()
        )
        assert response.get_indicator('rsi', default=50.0) == 50.0
    
    def test_get_rsi_dict_format(self):
        """Test get_rsi parses dict format"""
        response = TaapiResponse(
            symbol='BTC/USDT',
            exchange='binance',
            interval='4h',
            indicators={'rsi': {'value': 65.5}},
            timestamp=datetime.utcnow()
        )
        assert response.get_rsi() == 65.5
    
    def test_get_rsi_scalar_format(self):
        """Test get_rsi handles scalar format"""
        response = TaapiResponse(
            symbol='BTC/USDT',
            exchange='binance',
            interval='4h',
            indicators={'rsi': 65.5},
            timestamp=datetime.utcnow()
        )
        assert response.get_rsi() == 65.5
    
    def test_get_macd_dict_format(self):
        """Test get_macd parses MACD dict"""
        response = TaapiResponse(
            symbol='BTC/USDT',
            exchange='binance',
            interval='4h',
            indicators={
                'macd': {
                    'valueMACDLine': 200.0,
                    'valueMACDSignalLine': 180.0,
                    'valueMACDHistogram': 20.0
                }
            },
            timestamp=datetime.utcnow()
        )
        macd = response.get_macd()
        assert macd['line'] == 200.0
        assert macd['signal'] == 180.0
        assert macd['histogram'] == 20.0
    
    def test_get_ema_with_period(self):
        """Test get_ema retrieves specific period"""
        response = TaapiResponse(
            symbol='BTC/USDT',
            exchange='binance',
            interval='4h',
            indicators={'ema_50': {'value': 42000.0}, 'ema_200': {'value': 41000.0}},
            timestamp=datetime.utcnow()
        )
        assert response.get_ema(50) == 42000.0
        assert response.get_ema(200) == 41000.0


class TestTaapiRateLimiter:
    """Test TaapiRateLimiter"""
    
    def test_initialization(self):
        """Test rate limiter initialization with safety buffer"""
        limiter = TaapiRateLimiter(calls_per_minute=2400, calls_per_day=150000)
        # Should apply 80% safety buffer to per-minute: 2400 * 0.8 = 1920
        # Should apply 90% safety buffer to per-day: 150000 * 0.9 = 135000
        assert limiter.calls_per_minute == 1920
        assert limiter.calls_per_day == 135000
        assert limiter.daily_count == 0
    
    @pytest.mark.asyncio
    async def test_acquire_increments_counters(self):
        """Test acquire increments call counters"""
        limiter = TaapiRateLimiter()
        initial_count = limiter.daily_count
        await limiter.acquire()
        assert limiter.daily_count == initial_count + 1
        assert len(limiter.minute_window) == 1
    
    @pytest.mark.asyncio
    async def test_acquire_multiple_calls(self):
        """Test multiple acquires within limits"""
        limiter = TaapiRateLimiter()
        for _ in range(5):
            await limiter.acquire()
        assert limiter.daily_count == 5
        assert len(limiter.minute_window) == 5
    
    def test_get_stats(self):
        """Test get_stats returns correct statistics"""
        limiter = TaapiRateLimiter()
        limiter.daily_count = 100
        stats = limiter.get_stats()
        
        assert stats['daily_count'] == 100
        assert stats['remaining_daily'] > 0
        assert stats['calls_last_minute'] == 0
        assert 'daily_reset_in_seconds' in stats


class TestTaapiProClient:
    """Test TaapiProClient"""
    
    def test_initialization_with_api_key(self):
        """Test client initialization with explicit API key"""
        client = TaapiProClient(api_key='test_key_123')
        assert client.api_key == 'test_key_123'
        assert client.base_url == 'https://api.taapi.io'
        assert client._cache_ttl == 30
    
    def test_initialization_without_api_key_raises(self):
        """Test initialization fails without API key"""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(ValueError, match="TAAPI_API_KEY not provided"):
                TaapiProClient()
    
    def test_build_cache_key(self):
        """Test cache key generation"""
        client = TaapiProClient(api_key='test_key')
        indicators = [
            IndicatorConfig('rsi', period=14),
            IndicatorConfig('macd'),
            IndicatorConfig('ema', period=50)
        ]
        cache_key = client._build_cache_key('BTC/USDT', '4h', indicators)
        # Should sort indicators alphabetically
        assert 'BTC/USDT_4h_' in cache_key
        assert 'ema' in cache_key
        assert 'macd' in cache_key
        assert 'rsi' in cache_key
    
    def test_cache_set_and_get(self):
        """Test cache storage and retrieval"""
        client = TaapiProClient(api_key='test_key')
        response = TaapiResponse(
            symbol='BTC/USDT',
            exchange='binance',
            interval='4h',
            indicators={'rsi': 65.5},
            timestamp=datetime.utcnow()
        )
        
        cache_key = 'test_key'
        client._set_cache(cache_key, response)
        
        retrieved = client._get_from_cache(cache_key)
        assert retrieved is not None
        assert retrieved.cache_hit is True
        assert client._metrics['cache_hits'] == 1
    
    def test_cache_expiration(self):
        """Test cache expires after TTL"""
        client = TaapiProClient(api_key='test_key')
        client._cache_ttl = 0  # Expire immediately
        
        response = TaapiResponse(
            symbol='BTC/USDT',
            exchange='binance',
            interval='4h',
            indicators={'rsi': 65.5},
            timestamp=datetime.utcnow()
        )
        
        cache_key = 'test_key'
        client._set_cache(cache_key, response)
        
        time.sleep(0.1)  # Wait for expiration
        retrieved = client._get_from_cache(cache_key)
        assert retrieved is None
    
    def test_parse_bulk_response_rsi(self):
        """Test parsing RSI from bulk response"""
        client = TaapiProClient(api_key='test_key')
        raw_data = {
            'data': [
                {'indicator': 'rsi', 'value': 65.5}
            ]
        }
        
        response = client._parse_bulk_response(raw_data, 'BTC/USDT', 'binance', '4h', 500.0)
        assert response.indicators['rsi'] == 65.5
        assert response.symbol == 'BTC/USDT'
        assert response.fetch_duration_ms == 500.0
    
    def test_parse_bulk_response_macd(self):
        """Test parsing MACD from bulk response"""
        client = TaapiProClient(api_key='test_key')
        raw_data = {
            'data': [
                {
                    'indicator': 'macd',
                    'valueMACDLine': 200.0,
                    'valueMACDSignalLine': 180.0,
                    'valueMACDHistogram': 20.0
                }
            ]
        }
        
        response = client._parse_bulk_response(raw_data, 'BTC/USDT', 'binance', '4h', 500.0)
        assert response.indicators['macd']['line'] == 200.0
        assert response.indicators['macd']['signal'] == 180.0
        assert response.indicators['macd']['histogram'] == 20.0
    
    def test_parse_bulk_response_multiple_indicators(self):
        """Test parsing multiple indicators from bulk response"""
        client = TaapiProClient(api_key='test_key')
        raw_data = {
            'data': [
                {'indicator': 'rsi', 'value': 65.5},
                {'indicator': 'adx', 'value': 28.3},
                {'indicator': 'ema', 'period': 50, 'value': 42000.0}
            ]
        }
        
        response = client._parse_bulk_response(raw_data, 'BTC/USDT', 'binance', '4h', 500.0)
        assert response.indicators['rsi'] == 65.5
        assert response.indicators['adx'] == 28.3
        assert response.indicators['ema_50'] == 42000.0
    
    @pytest.mark.asyncio
    async def test_get_technical_snapshot_uses_cache(self):
        """Test get_technical_snapshot uses cache on second call"""
        client = TaapiProClient(api_key='test_key')
        
        # Mock the request method to return a response
        mock_response = {
            'data': [
                {'indicator': 'rsi', 'value': 65.5}
            ]
        }
        client._make_request_with_retry = AsyncMock(return_value=mock_response)
        
        # First call - should hit API
        response1 = await client.get_technical_snapshot('BTC/USDT')
        assert client._metrics['api_calls'] == 1
        assert client._metrics['cache_misses'] == 1
        
        # Second call - should hit cache
        response2 = await client.get_technical_snapshot('BTC/USDT')
        assert client._metrics['api_calls'] == 1  # Still 1, didn't call API again
        assert client._metrics['cache_hits'] == 1
        assert response2.cache_hit is True
    
    def test_get_metrics(self):
        """Test get_metrics returns correct statistics"""
        client = TaapiProClient(api_key='test_key')
        client._metrics['api_calls'] = 100
        client._metrics['cache_hits'] = 30
        client._metrics['cache_misses'] = 70
        client._metrics['errors'] = 2
        
        metrics = client.get_metrics()
        assert metrics['api_calls'] == 100
        assert metrics['cache_hits'] == 30
        assert metrics['cache_misses'] == 70
        assert metrics['cache_hit_rate'] == 0.3  # 30 / 100
        assert metrics['errors'] == 2
        assert 'rate_limiter' in metrics
    
    def test_clear_cache(self):
        """Test cache clearing"""
        client = TaapiProClient(api_key='test_key')
        client._cache['key1'] = ('value1', time.time())
        client._cache['key2'] = ('value2', time.time())
        
        assert len(client._cache) == 2
        client.clear_cache()
        assert len(client._cache) == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
