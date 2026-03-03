"""
Unit tests for MultiTimeframeAnalysis

Tests hierarchical timeframe analysis, alignment calculation, and confidence scoring.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend', 'claude-engine', 'external_data_sources'))

from multi_timeframe_analysis import (
    MultiTimeframeAnalysis,
    TimeframeAnalysis,
    MultiTimeframeResult,
    TrendDirection,
    IndicatorAlignment,
    MarketRegime
)
from taapi_pro_client import TaapiProClient, TaapiResponse


class TestTrendDirection:
    """Test TrendDirection enum"""
    
    def test_trend_direction_values(self):
        """Test enum values"""
        assert TrendDirection.BULLISH.value == "bullish"
        assert TrendDirection.BEARISH.value == "bearish"
        assert TrendDirection.NEUTRAL.value == "neutral"


class TestIndicatorAlignment:
    """Test IndicatorAlignment enum"""
    
    def test_alignment_values(self):
        """Test alignment status values"""
        assert IndicatorAlignment.FULLY_ALIGNED.value == "fully_aligned"
        assert IndicatorAlignment.PARTIALLY_ALIGNED.value == "partially_aligned"
        assert IndicatorAlignment.CONFLICTING.value == "conflicting"


class TestMarketRegime:
    """Test MarketRegime enum"""
    
    def test_market_regime_values(self):
        """Test market regime values"""
        assert MarketRegime.STRONG_TRENDING.value == "strong_trending"
        assert MarketRegime.TRENDING.value == "trending"
        assert MarketRegime.RANGING.value == "ranging"


class TestTimeframeAnalysis:
    """Test TimeframeAnalysis dataclass"""
    
    def test_timeframe_analysis_creation(self):
        """Test creating TimeframeAnalysis"""
        analysis = TimeframeAnalysis(
            timeframe='4h',
            trend_direction=TrendDirection.BULLISH,
            trend_strength=0.8,
            rsi=65.5,
            confidence=0.85
        )
        assert analysis.timeframe == '4h'
        assert analysis.trend_direction == TrendDirection.BULLISH
        assert analysis.trend_strength == 0.8
        assert analysis.rsi == 65.5
    
    def test_get_signal_bias_bullish(self):
        """Test signal bias calculation for bullish trend"""
        analysis = TimeframeAnalysis(
            timeframe='4h',
            trend_direction=TrendDirection.BULLISH,
            trend_strength=0.8,
            bullish_signals=5,
            bearish_signals=2,
            neutral_signals=1
        )
        assert analysis.get_signal_bias() == TrendDirection.BULLISH
    
    def test_get_signal_bias_bearish(self):
        """Test signal bias calculation for bearish trend"""
        analysis = TimeframeAnalysis(
            timeframe='4h',
            trend_direction=TrendDirection.BEARISH,
            trend_strength=0.7,
            bullish_signals=2,
            bearish_signals=6,
            neutral_signals=0
        )
        assert analysis.get_signal_bias() == TrendDirection.BEARISH
    
    def test_get_signal_bias_neutral(self):
        """Test signal bias calculation for neutral trend"""
        analysis = TimeframeAnalysis(
            timeframe='4h',
            trend_direction=TrendDirection.NEUTRAL,
            trend_strength=0.5,
            bullish_signals=3,
            bearish_signals=3,
            neutral_signals=2
        )
        assert analysis.get_signal_bias() == TrendDirection.NEUTRAL


class TestMultiTimeframeResult:
    """Test MultiTimeframeResult dataclass"""
    
    def test_multi_timeframe_result_creation(self):
        """Test creating MultiTimeframeResult"""
        result = MultiTimeframeResult(
            symbol='BTC/USDT',
            timestamp=datetime.utcnow(),
            overall_trend=TrendDirection.BULLISH,
            alignment_status=IndicatorAlignment.FULLY_ALIGNED,
            alignment_confidence=0.85,
            recommendation='BUY',
            confidence_score=0.85
        )
        assert result.symbol == 'BTC/USDT'
        assert result.overall_trend == TrendDirection.BULLISH
        assert result.recommendation == 'BUY'
    
    def test_to_dict_conversion(self):
        """Test converting result to dict"""
        four_hour = TimeframeAnalysis(
            timeframe='4h',
            trend_direction=TrendDirection.BULLISH,
            trend_strength=0.8,
            rsi=65.5,
            confidence=0.85,
            bullish_signals=5,
            bearish_signals=2,
            neutral_signals=1
        )
        
        result = MultiTimeframeResult(
            symbol='BTC/USDT',
            timestamp=datetime(2025, 11, 11, 12, 0, 0),
            four_hour=four_hour,
            overall_trend=TrendDirection.BULLISH,
            alignment_status=IndicatorAlignment.PARTIALLY_ALIGNED,
            alignment_confidence=0.75,
            total_bullish_signals=5,
            total_bearish_signals=2,
            total_neutral_signals=1,
            recommendation='BUY',
            confidence_score=0.75
        )
        
        result_dict = result.to_dict()
        assert result_dict['symbol'] == 'BTC/USDT'
        assert result_dict['overall_trend'] == 'bullish'
        assert result_dict['alignment_status'] == 'partially_aligned'
        assert result_dict['recommendation'] == 'BUY'
        assert result_dict['signals']['bullish'] == 5
        assert result_dict['timeframes']['4h'] is not None


class TestMultiTimeframeAnalysis:
    """Test MultiTimeframeAnalysis class"""
    
    @pytest.fixture
    def mock_taapi_client(self):
        """Create mock TAAPI client"""
        client = MagicMock(spec=TaapiProClient)
        return client
    
    @pytest.fixture
    def analyzer(self, mock_taapi_client):
        """Create analyzer with mock client"""
        return MultiTimeframeAnalysis(mock_taapi_client)
    
    def test_initialization(self, mock_taapi_client):
        """Test analyzer initialization"""
        analyzer = MultiTimeframeAnalysis(mock_taapi_client)
        assert analyzer.taapi_client == mock_taapi_client
    
    def test_analyze_daily_bullish_ema200(self, analyzer):
        """Test daily analysis with bullish EMA 200 signal"""
        data = TaapiResponse(
            symbol='BTC/USDT',
            exchange='binance',
            interval='1d',
            indicators={
                'close': 42000.0,
                'ema_200': 40000.0,
                'adx': 35.0,
                'macd': {
                    'line': 200.0,
                    'signal': 180.0,
                    'histogram': 20.0
                }
            },
            timestamp=datetime.utcnow()
        )
        
        analysis = analyzer._analyze_daily(data)
        
        assert analysis.timeframe == '1d'
        assert analysis.trend_direction == TrendDirection.BULLISH
        assert analysis.market_regime == MarketRegime.STRONG_TRENDING
        assert analysis.trend_strength == 0.9
        assert analysis.bullish_signals >= 2
    
    def test_analyze_daily_bearish_macd(self, analyzer):
        """Test daily analysis with bearish MACD"""
        data = TaapiResponse(
            symbol='BTC/USDT',
            exchange='binance',
            interval='1d',
            indicators={
                'close': 43000.0,
                'ema_200': 45000.0,
                'adx': 25.0,
                'macd': {
                    'line': 180.0,
                    'signal': 200.0,
                    'histogram': -20.0
                }
            },
            timestamp=datetime.utcnow()
        )
        
        analysis = analyzer._analyze_daily(data)
        
        assert analysis.trend_direction == TrendDirection.BEARISH
        assert analysis.market_regime == MarketRegime.TRENDING
        assert analysis.bearish_signals >= 1
    
    def test_analyze_four_hour_oversold_rsi(self, analyzer):
        """Test 4H analysis with oversold RSI"""
        data = TaapiResponse(
            symbol='BTC/USDT',
            exchange='binance',
            interval='4h',
            indicators={
                'rsi': 25.0,  # Oversold
                'macd': {
                    'line': 200.0,
                    'signal': 180.0,
                    'histogram': 20.0
                },
                'ema_50': 42000.0,
                'ema_200': 41000.0,
                'adx': 28.0,
                'stochrsi': {'k': 15.0},
                'cmf': 0.08,
                'mfi': 18.0
            },
            timestamp=datetime.utcnow()
        )
        
        analysis = analyzer._analyze_four_hour(data)
        
        assert analysis.timeframe == '4h'
        assert analysis.rsi == 25.0
        assert analysis.bullish_signals >= 4  # RSI oversold + MACD + EMA cross + StochRSI + CMF + MFI
        assert analysis.trend_direction == TrendDirection.BULLISH
    
    def test_analyze_four_hour_overbought_rsi(self, analyzer):
        """Test 4H analysis with overbought RSI"""
        data = TaapiResponse(
            symbol='BTC/USDT',
            exchange='binance',
            interval='4h',
            indicators={
                'rsi': 75.0,  # Overbought
                'macd': {
                    'line': 180.0,
                    'signal': 200.0,
                    'histogram': -20.0
                },
                'ema_50': 41000.0,
                'ema_200': 42000.0,
                'adx': 22.0
            },
            timestamp=datetime.utcnow()
        )
        
        analysis = analyzer._analyze_four_hour(data)
        
        assert analysis.rsi == 75.0
        assert analysis.bearish_signals >= 3  # RSI overbought + MACD + EMA death cross
        assert analysis.trend_direction == TrendDirection.BEARISH
    
    def test_analyze_four_hour_volume_confirmation(self, analyzer):
        """Test volume confirmation logic"""
        data = TaapiResponse(
            symbol='BTC/USDT',
            exchange='binance',
            interval='4h',
            indicators={
                'rsi': 55.0,
                'obv': 1000.0,  # Positive
                'cmf': 0.08,  # Positive accumulation
                'adx': 25.0
            },
            timestamp=datetime.utcnow()
        )
        
        analysis = analyzer._analyze_four_hour(data)
        
        assert analysis.volume_confirmed is True
        assert analysis.confidence > 0.5
    
    def test_analyze_one_hour_bullish_ema_cross(self, analyzer):
        """Test 1H analysis with bullish EMA cross"""
        data = TaapiResponse(
            symbol='BTC/USDT',
            exchange='binance',
            interval='1h',
            indicators={
                'close': 43100.0,
                'rsi': 60.0,
                'macd': {
                    'line': 100.0,
                    'signal': 90.0,
                    'histogram': 10.0
                },
                'ema_9': 43000.0,
                'ema_21': 42800.0,  # EMA9 > EMA21 = bullish
                'vwap': 42500.0
            },
            timestamp=datetime.utcnow()
        )
        
        analysis = analyzer._analyze_one_hour(data)
        
        assert analysis.timeframe == '1h'
        assert analysis.trend_direction == TrendDirection.BULLISH
        assert analysis.bullish_signals >= 3
    
    def test_calculate_alignment_fully_aligned_bullish(self, analyzer):
        """Test alignment calculation when all timeframes bullish"""
        daily = TimeframeAnalysis(
            timeframe='1d',
            trend_direction=TrendDirection.BULLISH,
            trend_strength=0.8,
            confidence=0.85,
            bullish_signals=2,
            bearish_signals=0,
            neutral_signals=0
        )
        
        four_hour = TimeframeAnalysis(
            timeframe='4h',
            trend_direction=TrendDirection.BULLISH,
            trend_strength=0.9,
            confidence=0.88,
            bullish_signals=7,
            bearish_signals=1,
            neutral_signals=0,
            volume_confirmed=True
        )
        
        one_hour = TimeframeAnalysis(
            timeframe='1h',
            trend_direction=TrendDirection.BULLISH,
            trend_strength=0.7,
            confidence=0.75,
            bullish_signals=3,
            bearish_signals=0,
            neutral_signals=1
        )
        
        result = analyzer._calculate_alignment(daily, four_hour, one_hour)
        
        assert result['overall_trend'] == TrendDirection.BULLISH
        assert result['alignment_status'] == IndicatorAlignment.FULLY_ALIGNED
        assert result['alignment_confidence'] >= 0.85
        assert result['recommendation'] == 'BUY'
        assert result['volume_confirmed'] is True
        assert result['total_bullish'] == 12  # 2 + 7 + 3
    
    def test_calculate_alignment_partially_aligned(self, analyzer):
        """Test alignment when 2/3 timeframes agree"""
        daily = TimeframeAnalysis(
            timeframe='1d',
            trend_direction=TrendDirection.BULLISH,
            trend_strength=0.8,
            confidence=0.85,
            bullish_signals=2,
            bearish_signals=0,
            neutral_signals=0
        )
        
        four_hour = TimeframeAnalysis(
            timeframe='4h',
            trend_direction=TrendDirection.BULLISH,
            trend_strength=0.7,
            confidence=0.78,
            bullish_signals=5,
            bearish_signals=2,
            neutral_signals=0
        )
        
        one_hour = TimeframeAnalysis(
            timeframe='1h',
            trend_direction=TrendDirection.BEARISH,
            trend_strength=0.6,
            confidence=0.65,
            bullish_signals=1,
            bearish_signals=3,
            neutral_signals=0
        )
        
        result = analyzer._calculate_alignment(daily, four_hour, one_hour)
        
        assert result['overall_trend'] == TrendDirection.BULLISH  # 2/3 bullish
        assert result['alignment_status'] == IndicatorAlignment.PARTIALLY_ALIGNED
        assert result['alignment_confidence'] >= 0.65
        assert result['alignment_confidence'] < 0.85
    
    def test_calculate_alignment_conflicting(self, analyzer):
        """Test alignment when all timeframes disagree"""
        daily = TimeframeAnalysis(
            timeframe='1d',
            trend_direction=TrendDirection.BULLISH,
            trend_strength=0.7,
            confidence=0.70,
            bullish_signals=2,
            bearish_signals=0,
            neutral_signals=0
        )
        
        four_hour = TimeframeAnalysis(
            timeframe='4h',
            trend_direction=TrendDirection.BEARISH,
            trend_strength=0.6,
            confidence=0.65,
            bullish_signals=2,
            bearish_signals=5,
            neutral_signals=1
        )
        
        one_hour = TimeframeAnalysis(
            timeframe='1h',
            trend_direction=TrendDirection.NEUTRAL,
            trend_strength=0.5,
            confidence=0.55,
            bullish_signals=1,
            bearish_signals=1,
            neutral_signals=2
        )
        
        result = analyzer._calculate_alignment(daily, four_hour, one_hour)
        
        assert result['alignment_status'] == IndicatorAlignment.CONFLICTING
        assert result['overall_trend'] == TrendDirection.NEUTRAL
        assert result['recommendation'] == 'HOLD'
        assert result['alignment_confidence'] <= 0.60
    
    def test_calculate_alignment_weighted_confidence(self, analyzer):
        """Test hierarchical weighting (Daily 30%, 4H 50%, 1H 20%)"""
        daily = TimeframeAnalysis(
            timeframe='1d',
            trend_direction=TrendDirection.BULLISH,
            trend_strength=0.8,
            confidence=0.90,  # High confidence
            bullish_signals=2,
            bearish_signals=0,
            neutral_signals=0
        )
        
        four_hour = TimeframeAnalysis(
            timeframe='4h',
            trend_direction=TrendDirection.BULLISH,
            trend_strength=0.9,
            confidence=0.85,  # High confidence
            bullish_signals=7,
            bearish_signals=1,
            neutral_signals=0
        )
        
        one_hour = TimeframeAnalysis(
            timeframe='1h',
            trend_direction=TrendDirection.BULLISH,
            trend_strength=0.6,
            confidence=0.60,  # Lower confidence
            bullish_signals=2,
            bearish_signals=1,
            neutral_signals=1
        )
        
        result = analyzer._calculate_alignment(daily, four_hour, one_hour)
        
        # Weighted confidence = (0.90*0.3 + 0.85*0.5 + 0.60*0.2) / 1.0 = 0.815
        # Plus base confidence for FULLY_ALIGNED
        assert result['alignment_confidence'] >= 0.80
        assert result['confidence_score'] >= 0.80


@pytest.mark.asyncio
class TestMultiTimeframeAnalysisIntegration:
    """Integration tests for full analysis flow"""
    
    @pytest.fixture
    def mock_taapi_client(self):
        """Create mock TAAPI client"""
        client = MagicMock(spec=TaapiProClient)
        return client
    
    @pytest.fixture
    def analyzer(self, mock_taapi_client):
        """Create analyzer"""
        return MultiTimeframeAnalysis(mock_taapi_client)
    
    async def test_analyze_full_flow(self, analyzer, mock_taapi_client):
        """Test complete analysis flow"""
        # Mock multi-timeframe snapshot
        mock_taapi_client.get_multi_timeframe_snapshot = AsyncMock(return_value={
            '1d': TaapiResponse(
                symbol='BTC/USDT',
                exchange='binance',
                interval='1d',
                indicators={'ema_200': 40000.0, 'adx': 30.0, 'macd': {'histogram': 50.0}},
                timestamp=datetime.utcnow()
            ),
            '4h': TaapiResponse(
                symbol='BTC/USDT',
                exchange='binance',
                interval='4h',
                indicators={'rsi': 65.0, 'macd': {'histogram': 20.0}, 'ema_50': 42000.0, 'ema_200': 41000.0, 'adx': 28.0},
                timestamp=datetime.utcnow()
            ),
            '1h': TaapiResponse(
                symbol='BTC/USDT',
                exchange='binance',
                interval='1h',
                indicators={'rsi': 60.0, 'macd': {'histogram': 10.0}, 'ema_9': 43000.0, 'ema_21': 42800.0},
                timestamp=datetime.utcnow()
            )
        })
        
        result = await analyzer.analyze('BTC/USDT')
        
        assert result.symbol == 'BTC/USDT'
        assert result.overall_trend in [TrendDirection.BULLISH, TrendDirection.BEARISH, TrendDirection.NEUTRAL]
        assert result.daily is not None
        assert result.four_hour is not None
        assert result.one_hour is not None
        assert result.confidence_score >= 0.0
        assert result.confidence_score <= 1.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
