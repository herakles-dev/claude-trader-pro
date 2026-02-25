"""
Prompt Templates for Claude AI Predictions

Contains system prompts and market context formatting for conservative
and aggressive trading strategies.

Author: AI Integration Specialist
Date: 2025-11-11
"""

from typing import Dict, Any, Optional

# Prompt version for tracking changes
PROMPT_VERSION = "3.2.0"  # Added FRED macro economic integration (DXY, S&P500, Treasury, VIX, Fed Funds)


SYSTEM_PROMPT_CONSERVATIVE = '''You are a conservative cryptocurrency technical analyst with expertise in multi-timeframe analysis and risk management.

RESPONSE FORMAT (valid JSON only):
{
    "trend_analysis": "brief analysis of current market trend",
    "indicator_alignment": "aligned/conflicting/mixed",
    "prediction": "up/down",
    "confidence": 0-100,
    "reasoning": "clear explanation of your prediction based on data"
}

MULTI-TIMEFRAME ANALYSIS RULES:
1. Weight 4-hour timeframe most heavily (50%) - it's the most predictive for 4H moves
2. Daily timeframe (30%) provides macro trend filter - avoid counter-trend trades
3. 1-hour timeframe (20%) helps refine entry timing
4. FULLY ALIGNED timeframes (all agree) = 85%+ confidence target
5. PARTIALLY ALIGNED (2/3 agree) = 65-75% confidence
6. CONFLICTING timeframes (no agreement) = hold, confidence <60%
7. Volume confirmation (OBV + CMF agreeing) adds +5-10% confidence
8. Market regime matters: Strong trending (ADX>30) = higher confidence, Ranging (ADX<20) = lower confidence

TIMEFRAME CONFLICT RESOLUTION:
When timeframes disagree, apply these rules in order:
1. Daily opposes 4H: Confidence <65% (counter-trend is risky, macro filter failed)
2. 4H and 1H conflict but Daily agrees with 4H: Trust 4H (70% confidence)
3. Only 1H differs from 4H+Daily: Proceed with 4H direction (75% confidence)
4. 4H and Daily conflict: HOLD, confidence <55% (major structural uncertainty)
5. All three conflict: HOLD, confidence <50% (wait for clarity)

DATA QUALITY WEIGHTING:
- Overall confidence >0.85: Trust fully, use your stated confidence levels
- Confidence 0.70-0.85: Reduce your confidence by 10% (moderate data quality)
- Confidence <0.70: Reduce your confidence by 20%, explicitly note data quality concerns in reasoning
- Missing data streams: Acknowledge gaps in reasoning, do not speculate about missing data
- Low sample sizes: Treat with skepticism (e.g., "only 2 sources" or "thin volume")

VOLUME CONFIRMATION RULES:
- OBV + CMF both aligned with price direction: +10% confidence boost
- OBV aligned, CMF neutral or missing: +5% confidence boost
- Volume divergence (price rising but volume falling): -15% confidence, flag concern in reasoning
- Extremely low volume: -10% confidence, note "low conviction move"

DERIVATIVES INTERPRETATION:
- Funding rate >0.05%: Overleveraged longs, squeeze risk (-10% confidence for long prediction)
- Funding rate <-0.05%: Overleveraged shorts, squeeze risk (-10% confidence for short prediction)
- Open Interest rising + price rising: Strong trend confirmation (+5% confidence)
- Open Interest falling + price rising: Weak trend, distribution risk (-10% confidence)
- Liquidations >$500M (24h): Extreme volatility expected, reduce confidence by 15%
- Liquidations >$100M (24h): High volatility, reduce confidence by 5%

TAKER FLOW ANALYSIS (Coinglass - KEY LEADING INDICATOR):
- Taker flow measures REAL-TIME buying/selling pressure from market orders
- Taker Buy/Sell Ratio >1.3: Strong buying pressure, aggressive buyers dominating (+10% for up)
- Taker Buy/Sell Ratio >1.1: Buying pressure, favorable for long (+5% for up)
- Taker Buy/Sell Ratio <0.7: Strong selling pressure, aggressive sellers dominating (+10% for down)
- Taker Buy/Sell Ratio <0.9: Selling pressure, favorable for short (+5% for down)
- Ratio 0.9-1.1: Balanced flow, neutral signal
- DIVERGENCE: If taker flow is bullish but funding is extremely positive = caution (squeeze setup)
- CONVERGENCE: If taker flow, funding, and OI all align = high confidence signal (+15%)
- Taker flow is a LEADING indicator - it shows real-time market participant behavior

ON-CHAIN SIGNALS (when available):
- Whale accumulation (>100 large transactions): Bullish leading indicator (+5% for up)
- Whale distribution (>100 outflows): Bearish leading indicator (+5% for down)
- Active addresses increasing >20%: Network growth, bullish (+3% for up)
- TVL increasing >10%: Fundamental strength for DeFi tokens (+5% for up)
- Gas prices extreme (>100 gwei): Network congestion, potential selloff signal

MACRO NEWS INTERPRETATION (Ground News):
- Ground News provides broader financial context beyond crypto-specific news
- If macro sentiment is BEARISH (Fed hawkish, recession fears): Reduce long confidence by 10%
- If macro sentiment is BULLISH (risk-on, liquidity): Boost long confidence by 5%
- Breaking macro events (rate decisions, major policy): Heavily weight in confidence
- Combine crypto news (CryptoPanic) with macro news (Ground News) for full picture
- High confidence AI summaries (>0.7) should be trusted more than headlines alone

TVL SIGNALS (DeFiLlama):
- Total DeFi TVL increasing >5% (24h): Protocol strength, bullish for market (+5%)
- Total DeFi TVL decreasing >5% (24h): Capital flight, bearish signal (-5%)
- Large TVL changes often precede price moves by 4-12 hours
- TVL trend "strongly_bullish" or "moderately_bullish": Favorable DeFi fundamentals
- TVL trend "strongly_bearish": Risk-off environment, reduce long confidence

LIQUIDATION DATA (Coinglass):
- Liquidations >$500M (24h): Extreme volatility expected, reduce confidence by 15%
- Liquidations >$100M (24h): High volatility, reduce confidence by 5%
- Long liquidations dominant (>60% of total): Bearish cascade risk, favor down prediction
- Short liquidations dominant (>60% of total): Bullish squeeze potential, favor up prediction
- Liquidation sentiment "extreme_bearish_cascade": Major downside risk
- Liquidation sentiment "bullish_squeeze": Potential short squeeze setup

SOCIAL SENTIMENT (LunarCrush):
- Galaxy Score >70: Strong social momentum, bullish signal (+5%)
- Galaxy Score <30: Weak social engagement, neutral to bearish
- Social volume surging (>50% change): Viral attention, increased volatility expected
- Sentiment "very_bullish" with high engagement: Strong bullish confirmation (+8%)
- Sentiment "very_bearish" with high engagement: Strong bearish confirmation (+8% for down)
- Divergence between price and social sentiment: Potential reversal signal

MACRO ECONOMIC ENVIRONMENT (FRED - Federal Reserve Economic Data):
- DXY (US Dollar Index) - INVERSE correlation with crypto:
  - DXY rising >0.5%: Bearish for crypto (capital flows to USD) -5% for long prediction
  - DXY falling >0.5%: Bullish for crypto (risk-on, capital seeks yield) +5% for long prediction
  - DXY trend "strongly_bearish": Favorable environment for crypto +8%
  - DXY trend "strongly_bullish": Headwind for crypto -8%
- S&P 500 - POSITIVE correlation (risk proxy):
  - S&P 500 rising: Risk-on environment, supportive for crypto +5%
  - S&P 500 falling >1%: Risk-off, likely crypto headwind -5%
  - S&P 500 trend aligns with crypto prediction: +3% confidence boost
- Treasury Yields (10-Year):
  - Yields rising sharply (>5bps): Tighter conditions, headwind for risk assets -5%
  - Yields falling: Easing conditions, favorable for crypto +5%
  - Yields >4.5%: High opportunity cost, challenging for speculative assets -3%
- Fed Funds Rate / Policy Stance:
  - Policy stance "hawkish" or "very_hawkish": Restrictive environment -10% for long
  - Policy stance "dovish" or "very_dovish": Accommodative environment +10% for long
  - Policy stance "neutral": No adjustment
- VIX (Fear Index) - CONTRARIAN at extremes:
  - VIX >35: Extreme fear, POTENTIAL bottom (contrarian opportunity), but reduce confidence by 10%
  - VIX >25: Elevated fear, reduce confidence by 5% for any prediction
  - VIX 15-25: Normal range, no adjustment
  - VIX <15: Extreme complacency, watch for corrections -3%
- Macro Score Integration:
  - Macro score <35: Challenging environment, cap long confidence at 60%
  - Macro score 35-55: Neutral environment, proceed with technicals
  - Macro score >65: Favorable environment, allow higher confidence for longs
  - Always mention macro environment in your reasoning when available

ANALYSIS RULES:
1. Only provide high confidence (>70) when timeframes align and indicators confirm
2. Admit uncertainty when patterns are unclear or timeframes conflict (confidence 40-60)
3. Consider indicator interplay across ALL timeframes, not just individual values
4. Prioritize capital preservation - false negatives are better than false positives
5. Account for sentiment and derivatives data in your analysis
6. Look for confirmation across timeframes, price action, technicals, sentiment, and on-chain
7. Be explicit about conflicting signals between timeframes and data sources
8. Weight your confidence based on data quality - poor data = lower confidence

HISTORICAL PATTERN ANALYSIS (when provided):
- If similar patterns have occurred before, heavily weight the historical accuracy
- Patterns with >70% historical accuracy should boost your confidence by 10%
- Patterns with <50% historical accuracy should reduce your confidence by 10%
- When multiple patterns align (e.g., "RSI Oversold + Extreme Fear"), look at COMBINED historical performance
- Recent similar conditions (last 7 days) are more relevant than older ones (discount by 20%)
- If historical accuracy is high but sample size is small (<5), treat with caution
- Explicitly reference historical pattern performance in your reasoning

MISSING MULTI-TIMEFRAME DATA (CRITICAL):
If the market context shows "DATA LIMITATION NOTICE" or lacks 4H/1H timeframe data:
- You CANNOT apply the multi-timeframe alignment rules properly
- Maximum confidence should be capped at 65% (not 85%+)
- Rely more heavily on: order book depth, derivatives signals, sentiment
- Explicitly state in your reasoning: "Multi-timeframe data unavailable - confidence reduced"
- The daily trend from EMA cross provides only macro direction, not timing precision
- Without 4H confirmation, treat ANY prediction as lower confidence

CONSERVATIVE PRINCIPLES:
- Require strong evidence before predicting moves
- Weight risk higher than reward
- Favor clarity over speculation
- Acknowledge when market conditions are uncertain
- Trust the multi-timeframe alignment - it's research-validated
- When in doubt, HOLD (confidence <60% = no trade)
- Learn from historical patterns - they reveal what actually worked

Analyze the provided market data and predict the next 4-hour price movement.'''


SYSTEM_PROMPT_AGGRESSIVE = '''You are an aggressive cryptocurrency technical analyst focused on short-term trading opportunities with multi-timeframe momentum analysis.

RESPONSE FORMAT (valid JSON only):
{
    "trend_analysis": "brief market trend analysis",
    "indicator_alignment": "aligned/conflicting/mixed",
    "prediction": "up/down",
    "confidence": 0-100,
    "reasoning": "explanation of your prediction"
}

MULTI-TIMEFRAME MOMENTUM RULES:
1. Prioritize 1-hour timeframe momentum (20% weight normally, but 40% for aggressive entries)
2. Trade when 1H and 4H align, even if daily is neutral (partial alignment = 65%+ confidence)
3. Look for early divergences between 1H and 4H as potential reversal signals
4. FULLY ALIGNED = take the trade with 75%+ confidence
5. PARTIALLY ALIGNED with strong 1H momentum = trade with 60-70% confidence
6. Volume confirmation boosts confidence to act quickly
7. In strong trending markets (ADX>25), can trade with lower timeframe alignment

TIMEFRAME CONFLICT RESOLUTION (AGGRESSIVE):
When timeframes disagree, apply these rules:
1. 1H + 4H agree, Daily neutral: TRADE with 65% confidence (acceptable for aggressive)
2. 1H shows early reversal vs 4H: TRADE the 1H signal with 55-60% confidence (early entry)
3. 4H + Daily agree, 1H lags: TRADE with 70% confidence (1H will catch up)
4. Only Daily differs: TRADE if 1H+4H momentum strong (60% confidence)
5. 4H and Daily conflict: HOLD unless 1H shows extreme momentum (>70 RSI or <30)

DATA QUALITY WEIGHTING:
- Overall confidence >0.85: Trust fully, use stated confidence
- Confidence 0.70-0.85: Reduce confidence by 5% (less conservative than conservative mode)
- Confidence <0.70: Reduce confidence by 10%, note concerns but still consider trading
- Missing data: Acknowledge gaps but proceed if core technicals are strong
- Low sample sizes: Reduce confidence by 5% but don't disqualify the trade

VOLUME CONFIRMATION RULES:
- Strong volume surge (>150% average): +15% confidence (momentum confirmed)
- OBV + CMF aligned with direction: +10% confidence
- Volume increasing with trend: +5% confidence
- Volume divergence: -10% confidence (not -15% like conservative)
- Low volume: -5% confidence (less penalized than conservative)

DERIVATIVES AS LEADING INDICATORS:
- Funding rate >0.05%: Potential short squeeze setup (+10% for up prediction if price at support)
- Funding rate <-0.05%: Potential long squeeze setup (+10% for down prediction if price at resistance)
- Open Interest rising >10%: Strong trend, follow it (+10% confidence)
- Open Interest falling + price moving: Weak hands shaking out, potential continuation (+5%)
- Liquidations >$500M: Cascade setup, trade the squeeze direction (+10% confidence)
- Liquidations >$100M: Volatility opportunity (+5% confidence)

TAKER FLOW SIGNALS (Coinglass - REAL-TIME PRESSURE):
- Taker flow is your BEST leading indicator - it shows actual buying/selling pressure NOW
- Taker Buy/Sell Ratio >1.3: Aggressive buyers, ride the momentum (+15% for up)
- Taker Buy/Sell Ratio >1.1: Buying pressure building (+8% for up)
- Taker Buy/Sell Ratio <0.7: Aggressive sellers, ride the downside (+15% for down)
- Taker Buy/Sell Ratio <0.9: Selling pressure building (+8% for down)
- MOMENTUM SETUP: Taker flow + OI increasing + price moving = high conviction trend (+20%)
- SQUEEZE SETUP: Taker flow bullish + extreme negative funding = imminent short squeeze
- DIVERGENCE PLAY: Taker flow bearish but price rising = distribution, fade the rally
- Trade taker flow signals IMMEDIATELY - they are the tape reading of crypto markets

ON-CHAIN SIGNALS (when available):
- Whale accumulation (>100 transactions): Strong bullish, +10% for up prediction
- Whale distribution: Strong bearish, +10% for down prediction
- Active addresses surging (>30%): Network effect, +5% for up
- TVL increasing >15%: Fundamental momentum, +8% for up
- Gas price spike: Network demand, short-term bullish, +3%

MACRO NEWS INTERPRETATION (Ground News):
- Macro news provides early signals before crypto-specific sources
- Macro sentiment BEARISH: Trade the downside momentum (-8% for long, +8% for short)
- Macro sentiment BULLISH: Risk-on environment, favor momentum plays (+8% for long)
- Fed/policy news with high confidence: Act quickly before market prices in
- AI summaries with confidence >0.8 are highly actionable
- Combine macro + crypto news for comprehensive sentiment

TVL SIGNALS (DeFiLlama):
- TVL increasing >10%: Strong momentum signal, +10% for up prediction
- TVL increasing >5%: Positive signal, +5% for up prediction
- TVL decreasing >5%: Negative signal, +5% for down prediction
- TVL trend changes often lead price by 4-12 hours - act early
- "Strongly_bullish" TVL trend: High conviction long setup

LIQUIDATION DATA (Coinglass):
- Liquidations >$500M: Cascade setup, trade the squeeze direction (+10% confidence)
- Liquidations >$100M: Volatility opportunity (+5% confidence)
- Long liquidations dominant (>60%): Short squeeze potential exhausted, favor short
- Short liquidations dominant (>60%): Long squeeze setup, favor long (+12% confidence)
- "Bullish_squeeze" sentiment: High probability long setup
- "Extreme_bearish_cascade": Aggressive short opportunity

SOCIAL SENTIMENT (LunarCrush):
- Galaxy Score >80: Very strong social momentum, aggressive long signal (+10%)
- Galaxy Score increasing + price lagging: Leading indicator, act before price confirms
- Social volume viral (>100% surge): Extreme volatility, increase position size potential
- "Very_bullish" sentiment: Strong entry signal for longs
- "Very_bearish" sentiment: Strong entry signal for shorts
- Social divergence from price: Contrarian opportunity (trade the social signal)

MACRO ECONOMIC ENVIRONMENT (FRED - Federal Reserve Economic Data):
- DXY (US Dollar Index) - INVERSE correlation with crypto:
  - DXY rising sharply (>1%): Strong bearish signal for crypto -8% for long
  - DXY falling sharply (>1%): Strong bullish signal for crypto +10% for long
  - DXY trend reversal: Early signal to position before crypto reacts
- S&P 500 - POSITIVE correlation (risk proxy):
  - S&P 500 rising with momentum: Risk-on, aggressive long opportunity +8%
  - S&P 500 falling sharply: Aggressive short opportunity if crypto follows +10% for short
  - Divergence between S&P and crypto: Trading opportunity (crypto to catch up)
- Treasury Yields (10-Year):
  - Yields falling sharply: Risk-on signal, aggressive long setup +8%
  - Yields rising sharply: Risk-off signal, but also potential for mean reversion plays
- Fed Funds Rate / Policy Stance:
  - Policy pivot signals: Major trading opportunity, act quickly
  - Policy stance "dovish": Aggressive long environment +12%
  - Policy stance "hawkish": Aggressive short or reduce long exposure -10%
- VIX (Fear Index) - CONTRARIAN OPPORTUNITIES:
  - VIX >35: Extreme fear = aggressive buying opportunity (contrarian) +15% for long
  - VIX spike (>20% in 24h): Panic selling, look for reversal entries
  - VIX <15: Complacency, potential short setup on overbought crypto
- Macro Score Integration (Aggressive):
  - Macro score <35: Counter-trend trades risky, but capitulation setups possible
  - Macro score >65: Full aggression on long positions, favorable backdrop
  - Macro divergence from technicals: Trade the macro signal if conviction is high
  - Use macro as CONFIRMATION for aggressive entries, not a filter

ANALYSIS RULES:
1. Act on strong momentum signals even with moderate confidence (50-70)
2. Favor trading opportunities over inaction
3. Prioritize short-term price action and 1H momentum
4. Weight recent data more heavily than historical
5. Derivatives signals are leading indicators - act on them before price confirms
6. Look for early trend reversals between timeframes - capture them early
7. Trade partial alignment when risk/reward is favorable (2:1 minimum)
8. Data quality matters but don't let it paralyze you - trade the best available info

HISTORICAL PATTERN ANALYSIS (when provided):
- Historical patterns are actionable signals, not just context
- If similar patterns have >60% historical accuracy, act on them (+10% confidence)
- Patterns with <40% historical accuracy: consider contrarian position or skip
- Multiple aligned patterns (e.g., "Funding Rate Long Squeeze + RSI Oversold") are high-value setups
- Recent similar conditions (last 7 days) are especially relevant for momentum trades
- Sample size matters less for aggressive trades - even 3-4 historical matches are useful
- Explicitly mention pattern performance when it supports your prediction

AGGRESSIVE PRINCIPLES:
- Capitalize on clear momentum signals quickly
- Balance risk with reward potential
- Be willing to trade on moderate confidence (50-65%) when risk/reward favors it (>2:1)
- Identify opportunities others might wait to confirm
- Use 1H timeframe for early entry signals before 4H confirms
- Don't wait for full alignment if 4H + 1H momentum is strong
- Derivatives and on-chain data can justify trades even with conflicting timeframes
- Accept higher risk for higher reward potential
- Historical patterns that worked before often work again - use them

Analyze the market data and predict the next 4-hour price movement.'''


def get_system_prompt(strategy: str = "conservative") -> str:
    """
    Get system prompt for specified strategy
    
    Args:
        strategy: "conservative" or "aggressive"
        
    Returns:
        System prompt string
    """
    if strategy.lower() == "aggressive":
        return SYSTEM_PROMPT_AGGRESSIVE
    return SYSTEM_PROMPT_CONSERVATIVE


def format_basic_market_context(snapshot: Dict[str, Any]) -> str:
    """
    Format basic market snapshot (Binance fallback mode)

    Args:
        snapshot: Market snapshot dictionary from UnifiedDataClient

    Returns:
        Formatted market context string
    """
    import logging
    logger = logging.getLogger(__name__)

    # Debug: Log snapshot keys to trace data flow
    logger.info(f"format_basic_market_context called with keys: {list(snapshot.keys())}")
    coinglass_derivs_check = snapshot.get('coinglass_derivatives')
    logger.info(f"coinglass_derivatives present: {coinglass_derivs_check is not None}, confidence: {coinglass_derivs_check.get('confidence', 'N/A') if coinglass_derivs_check else 'N/A'}")

    symbol = snapshot['symbol']
    market = snapshot['market']
    sentiment = snapshot.get('sentiment')
    technical = snapshot.get('technical')
    derivatives = snapshot.get('derivatives')
    
    # Build context parts
    context_parts = []
    
    # Header
    context_parts.append(f"MARKET ANALYSIS REQUEST")
    context_parts.append(f"Symbol: {symbol}")
    context_parts.append(f"Timestamp: {snapshot['timestamp']}")
    context_parts.append(f"Overall Data Confidence: {snapshot['overall_confidence']:.2f}/1.0")
    context_parts.append("")
    
    # Price & Market Data
    context_parts.append("PRICE & MARKET DATA:")
    context_parts.append(f"  Current Price: ${market['price']:,.2f}")
    
    if market.get('price_change_24h') is not None:
        change_24h = market['price_change_24h']
        direction = "↑" if change_24h >= 0 else "↓"
        context_parts.append(f"  24h Change: {direction} {abs(change_24h):.2f}%")
    
    if market.get('high_24h') and market.get('low_24h'):
        context_parts.append(f"  24h Range: ${market['low_24h']:,.2f} - ${market['high_24h']:,.2f}")
    
    if market.get('volume_24h'):
        context_parts.append(f"  24h Volume: ${market['volume_24h']:,.0f}")
    
    if market.get('market_cap'):
        context_parts.append(f"  Market Cap: ${market['market_cap']:,.0f}")
    
    context_parts.append(f"  Data Confidence: {market['confidence']:.2f}/1.0")
    context_parts.append(f"  Sources: {', '.join(market['sources'])}")
    context_parts.append("")
    
    # Sentiment Analysis
    if sentiment:
        context_parts.append("SENTIMENT ANALYSIS:")
        context_parts.append(f"  Composite Score: {sentiment['score']:.1f}/100")
        
        if sentiment.get('fear_greed_index') is not None:
            fgi = sentiment['fear_greed_index']
            label = sentiment.get('fear_greed_label', 'Unknown')
            context_parts.append(f"  Fear & Greed Index: {fgi:.0f}/100 ({label})")
        
        # Only show Reddit data if actually available (has posts)
        if sentiment.get('reddit_score') is not None and sentiment.get('reddit_posts_24h', 0) > 0:
            reddit_score = sentiment['reddit_score']
            posts = sentiment['reddit_posts_24h']
            sentiment_label = "Bullish" if reddit_score > 60 else "Bearish" if reddit_score < 40 else "Neutral"
            context_parts.append(f"  Reddit Sentiment: {reddit_score:.1f}/100 ({sentiment_label})")
            context_parts.append(f"  Reddit Activity: {posts} posts analyzed (24h)")
        
        context_parts.append(f"  Data Confidence: {sentiment['confidence']:.2f}/1.0")
        context_parts.append("")
    
    # Technical Indicators
    if technical:
        context_parts.append("TECHNICAL INDICATORS:")
        
        if technical.get('rsi_14') is not None:
            rsi = technical['rsi_14']
            rsi_signal = technical.get('rsi_signal', 'neutral')
            rsi_interpretation = (
                "Oversold" if rsi < 30 else
                "Overbought" if rsi > 70 else
                "Neutral"
            )
            context_parts.append(f"  RSI(14): {rsi:.2f} - {rsi_interpretation} ({rsi_signal})")
        
        if technical.get('macd_histogram') is not None:
            macd_hist = technical['macd_histogram']
            macd_trend = technical.get('macd_trend', 'neutral')
            macd_signal = "Bullish momentum" if macd_hist > 0 else "Bearish momentum"
            context_parts.append(f"  MACD Histogram: {macd_hist:.2f} - {macd_signal} ({macd_trend})")
        
        # EMA indicators - show available data with trend context
        if technical.get('ema_50') is not None:
            ema_50 = technical['ema_50']
            context_parts.append(f"  EMA(50): ${ema_50:,.2f}")

        if technical.get('ema_200') is not None:
            ema_200 = technical['ema_200']
            context_parts.append(f"  EMA(200): ${ema_200:,.2f}")

            # Add Golden/Death Cross analysis if both EMAs available
            if technical.get('ema_50') is not None:
                if technical['ema_50'] > ema_200:
                    context_parts.append(f"  Trend: BULLISH (Golden Cross - EMA50 > EMA200)")
                else:
                    context_parts.append(f"  Trend: BEARISH (Death Cross - EMA50 < EMA200)")

        # Also show EMA(20) if available for short-term trend
        if technical.get('ema_20') is not None:
            ema_20 = technical['ema_20']
            context_parts.append(f"  EMA(20): ${ema_20:,.2f}")
        
        context_parts.append(f"  Data Confidence: {technical['confidence']:.2f}/1.0")
        context_parts.append("")

        # Volume Indicators (if available)
        if technical.get('obv') is not None or technical.get('cmf') is not None:
            context_parts.append("VOLUME INDICATORS:")

            if technical.get('obv') is not None:
                obv = technical['obv']
                obv_trend = "Rising (Accumulation)" if obv > 0 else "Falling (Distribution)"
                context_parts.append(f"  OBV: {obv:,.0f} - {obv_trend}")

            if technical.get('cmf') is not None:
                cmf = technical['cmf']
                if cmf > 0.05:
                    cmf_signal = "Strong Buying Pressure"
                elif cmf > 0:
                    cmf_signal = "Moderate Buying Pressure"
                elif cmf < -0.05:
                    cmf_signal = "Strong Selling Pressure"
                elif cmf < 0:
                    cmf_signal = "Moderate Selling Pressure"
                else:
                    cmf_signal = "Neutral"
                context_parts.append(f"  CMF: {cmf:.3f} - {cmf_signal}")

            context_parts.append("")

    # Derivatives Market (Enhanced interpretation)
    if derivatives:
        context_parts.append("DERIVATIVES MARKET:")
        
        # Funding rate with enhanced interpretation
        if derivatives.get('avg_funding_rate') is not None:
            funding = derivatives['avg_funding_rate']
            funding_pct = funding * 100
            
            # Provide nuanced interpretation based on funding extremes
            if funding > 0.05:
                funding_signal = "⚠️ EXTREME BULLISH: Overleveraged longs, short squeeze risk high"
            elif funding > 0.01:
                funding_signal = "Bullish (longs paying shorts, sustainable)"
            elif funding < -0.05:
                funding_signal = "⚠️ EXTREME BEARISH: Overleveraged shorts, long squeeze risk high"
            elif funding < -0.01:
                funding_signal = "Bearish (shorts paying longs, sustainable)"
            else:
                funding_signal = "Neutral (balanced positioning)"
            
            context_parts.append(f"  Funding Rate: {funding_pct:.4f}% - {funding_signal}")
        
        # Open Interest with trend context
        if derivatives.get('total_open_interest'):
            oi = derivatives['total_open_interest']
            context_parts.append(f"  Total Open Interest: ${oi:,.0f}")
            
            if derivatives.get('oi_change_24h') is not None:
                oi_change = derivatives['oi_change_24h']
                oi_direction = "↑" if oi_change >= 0 else "↓"
                
                # Enhanced OI interpretation
                if abs(oi_change) > 10:
                    if oi_change > 0:
                        oi_signal = "STRONG growth - new positions entering (trend confirmation)"
                    else:
                        oi_signal = "SHARP decline - positions closing (trend exhaustion warning)"
                elif abs(oi_change) > 5:
                    oi_signal = "Growing positions" if oi_change > 0 else "Decreasing positions"
                else:
                    oi_signal = "Stable (low conviction move)"
                
                context_parts.append(f"  OI Change (24h): {oi_direction} {abs(oi_change):.2f}% - {oi_signal}")
        
        # Liquidations with volatility context
        if derivatives.get('liquidations_24h_usd'):
            liq = derivatives['liquidations_24h_usd']
            
            # Add volatility interpretation
            if liq > 500_000_000:
                liq_signal = "⚠️ EXTREME CASCADE: High volatility, potential trend acceleration"
            elif liq > 100_000_000:
                liq_signal = "HIGH: Significant liquidations, elevated volatility expected"
            elif liq > 50_000_000:
                liq_signal = "MODERATE: Normal volatility"
            else:
                liq_signal = "LOW: Calm market conditions"
            
            context_parts.append(f"  Liquidations (24h): ${liq:,.0f} - {liq_signal}")
        
        context_parts.append(f"  Data Confidence: {derivatives['confidence']:.2f}/1.0")
        context_parts.append("")

    # Coinglass Derivatives Intelligence (Enhanced with taker flow)
    coinglass_derivs = snapshot.get('coinglass_derivatives')
    if coinglass_derivs and coinglass_derivs.get('confidence', 0) > 0:
        context_parts.append("COINGLASS DERIVATIVES INTELLIGENCE:")

        # Open Interest (more comprehensive than CCXT)
        oi_data = coinglass_derivs.get('open_interest', {})
        if oi_data.get('total_usd'):
            oi_usd = oi_data['total_usd']
            oi_change = oi_data.get('change_24h_pct')
            oi_trend = oi_data.get('trend', 'unknown')

            context_parts.append(f"  Aggregated Open Interest: ${oi_usd:,.0f}")
            if oi_change is not None:
                oi_dir = "↑" if oi_change >= 0 else "↓"
                context_parts.append(f"  OI Change (24h): {oi_dir} {abs(oi_change):.2f}%")
            context_parts.append(f"  OI Trend: {oi_trend.replace('_', ' ').title()}")

        # Funding Rates (with sentiment)
        funding_data = coinglass_derivs.get('funding_rate', {})
        if funding_data.get('current_pct') is not None:
            funding_pct = funding_data['current_pct']
            funding_sentiment = funding_data.get('sentiment', 'unknown')

            # Enhanced funding interpretation
            if funding_pct > 0.1:
                funding_signal = "⚠️ EXTREME LONG CROWDING: High funding = longs paying premium, squeeze risk"
            elif funding_pct > 0.05:
                funding_signal = "Very bullish positioning: Longs heavily dominant"
            elif funding_pct > 0.01:
                funding_signal = "Bullish: Longs paying shorts"
            elif funding_pct < -0.1:
                funding_signal = "⚠️ EXTREME SHORT CROWDING: Negative funding = shorts paying, squeeze risk"
            elif funding_pct < -0.05:
                funding_signal = "Very bearish positioning: Shorts heavily dominant"
            elif funding_pct < -0.01:
                funding_signal = "Bearish: Shorts paying longs"
            else:
                funding_signal = "Neutral: Balanced positioning"

            context_parts.append(f"  Funding Rate: {funding_pct:.4f}% - {funding_signal}")
            context_parts.append(f"  Funding Sentiment: {funding_sentiment.replace('_', ' ').title()}")

        # TAKER FLOW (Unique to Coinglass - KEY INDICATOR)
        taker_data = coinglass_derivs.get('taker_flow', {})
        if taker_data.get('buy_sell_ratio') is not None:
            ratio = taker_data['buy_sell_ratio']
            net_flow = taker_data.get('net_flow_usd', 0)
            flow_sentiment = taker_data.get('sentiment', 'unknown')

            # Taker flow interpretation - real-time buying/selling pressure
            if ratio > 1.3:
                taker_signal = "🟢 STRONG BUY PRESSURE: Aggressive buyers dominating tape"
            elif ratio > 1.1:
                taker_signal = "Buying pressure: More market buys than sells"
            elif ratio < 0.7:
                taker_signal = "🔴 STRONG SELL PRESSURE: Aggressive sellers dominating tape"
            elif ratio < 0.9:
                taker_signal = "Selling pressure: More market sells than buys"
            else:
                taker_signal = "Balanced: No clear directional pressure"

            context_parts.append(f"  Taker Buy/Sell Ratio: {ratio:.3f} - {taker_signal}")
            if net_flow != 0:
                flow_dir = "Buy" if net_flow > 0 else "Sell"
                context_parts.append(f"  Net Taker Flow (24h): ${abs(net_flow):,.0f} {flow_dir}")
            context_parts.append(f"  Flow Sentiment: {flow_sentiment.replace('_', ' ').title()}")

        # Liquidations from Coinglass snapshot
        liq_data = coinglass_derivs.get('liquidations', {})
        if liq_data.get('total_24h_usd'):
            total_liq = liq_data['total_24h_usd']
            long_liq = liq_data.get('long_24h_usd', 0)
            short_liq = liq_data.get('short_24h_usd', 0)
            liq_sentiment = liq_data.get('sentiment', 'normal')
            dominant = liq_data.get('dominant_side', 'balanced')

            context_parts.append(f"  Liquidations (24h): ${total_liq:,.0f}")
            if long_liq > 0 or short_liq > 0:
                context_parts.append(f"    Longs: ${long_liq:,.0f} | Shorts: ${short_liq:,.0f}")
            context_parts.append(f"    Dominant Side: {dominant.title()} | Sentiment: {liq_sentiment.replace('_', ' ').title()}")

        context_parts.append(f"  Data Source: Coinglass V4 (Confidence: {coinglass_derivs['confidence']:.2f})")
        context_parts.append("")

    # On-Chain Intelligence (Enhanced with whale tracking and exchange flows)
    onchain = snapshot.get('onchain')
    if onchain:
        context_parts.append("ON-CHAIN INTELLIGENCE:")

        # Whale transactions (leading indicator)
        if onchain.get('whale_transactions_24h') is not None:
            whales = onchain['whale_transactions_24h']

            # Provide interpretation based on whale activity
            if whales > 150:
                whale_signal = "⚠️ EXTREME: Heavy whale activity, major move likely"
            elif whales > 100:
                whale_signal = "HIGH: Significant whale activity, monitor closely"
            elif whales > 50:
                whale_signal = "MODERATE: Normal whale activity"
            else:
                whale_signal = "LOW: Minimal whale activity"

            context_parts.append(f"  Whale Transactions (24h): {whales} - {whale_signal}")

        # Whale volume
        if onchain.get('whale_volume_usd_24h') is not None:
            volume = onchain['whale_volume_usd_24h']
            context_parts.append(f"  Whale Volume (24h): ${volume:,.0f}")

        # Largest transaction
        if onchain.get('largest_transaction_usd') is not None:
            largest = onchain['largest_transaction_usd']
            context_parts.append(f"  Largest Transaction: ${largest:,.0f}")

        # Exchange flows (key leading indicator)
        if onchain.get('exchange_inflow_usd_24h') is not None or onchain.get('exchange_outflow_usd_24h') is not None:
            context_parts.append("  Exchange Flows:")
            if onchain.get('exchange_inflow_usd_24h') is not None:
                inflow = onchain['exchange_inflow_usd_24h']
                context_parts.append(f"    Inflow (24h): ${inflow:,.0f}")
            if onchain.get('exchange_outflow_usd_24h') is not None:
                outflow = onchain['exchange_outflow_usd_24h']
                context_parts.append(f"    Outflow (24h): ${outflow:,.0f}")
            if onchain.get('net_exchange_flow_usd') is not None:
                net_flow = onchain['net_exchange_flow_usd']
                flow_direction = "↓ to exchanges (bearish)" if net_flow > 0 else "↑ from exchanges (bullish)"
                context_parts.append(f"    Net Flow: ${abs(net_flow):,.0f} {flow_direction}")
            if onchain.get('flow_sentiment') is not None:
                flow_sent = onchain['flow_sentiment']
                context_parts.append(f"    Flow Sentiment: {flow_sent.upper()}")

        # SOPR (Spent Output Profit Ratio)
        if onchain.get('sopr') is not None:
            sopr = onchain['sopr']
            sopr_signal = onchain.get('sopr_signal', 'neutral')
            if sopr > 1.05:
                sopr_interpretation = "Profit-taking dominant (potential top)"
            elif sopr > 1.0:
                sopr_interpretation = "Holders in profit (healthy)"
            elif sopr < 0.95:
                sopr_interpretation = "Capitulation (potential bottom)"
            else:
                sopr_interpretation = "Break-even zone"
            context_parts.append(f"  SOPR: {sopr:.4f} - {sopr_interpretation} ({sopr_signal})")

        # Active addresses (network growth indicator)
        if onchain.get('active_addresses_24h') is not None:
            addresses = onchain['active_addresses_24h']
            context_parts.append(f"  Active Addresses (24h): {addresses:,}")

        # New addresses
        if onchain.get('new_addresses_24h') is not None:
            new_addr = onchain['new_addresses_24h']
            context_parts.append(f"  New Addresses (24h): {new_addr:,}")

        # Transaction count (network usage)
        if onchain.get('transaction_count_24h') is not None:
            txns = onchain['transaction_count_24h']
            context_parts.append(f"  Transaction Count (24h): {txns:,}")

        # Exchange balance
        if onchain.get('exchange_balance') is not None:
            balance = onchain['exchange_balance']
            context_parts.append(f"  Exchange Balance: {balance:,.2f}")

        # TVL (DeFi fundamental strength)
        if onchain.get('tvl') is not None:
            tvl = onchain['tvl']

            if onchain.get('tvl_change_24h') is not None:
                tvl_change = onchain['tvl_change_24h']
                tvl_direction = "↑" if tvl_change >= 0 else "↓"

                # Interpret TVL changes
                if abs(tvl_change) > 15:
                    if tvl_change > 0:
                        tvl_signal = "STRONG growth - capital inflow, bullish fundamental"
                    else:
                        tvl_signal = "SHARP decline - capital flight, bearish fundamental"
                elif abs(tvl_change) > 10:
                    tvl_signal = "Notable change" if tvl_change > 0 else "Concerning decline"
                elif abs(tvl_change) > 5:
                    tvl_signal = "Growing" if tvl_change > 0 else "Declining"
                else:
                    tvl_signal = "Stable"

                context_parts.append(f"  Total Value Locked: ${tvl:,.0f} ({tvl_direction} {abs(tvl_change):.1f}% 24h) - {tvl_signal}")
            else:
                context_parts.append(f"  Total Value Locked: ${tvl:,.0f}")

        # Gas prices (Ethereum network congestion)
        if onchain.get('gas_price_gwei') is not None:
            gas_gwei = onchain['gas_price_gwei']

            # Interpret gas prices (Ethereum context)
            if gas_gwei > 100:
                gas_signal = "⚠️ EXTREME congestion - high network demand"
            elif gas_gwei > 50:
                gas_signal = "HIGH - elevated network activity"
            elif gas_gwei > 20:
                gas_signal = "MODERATE - normal activity"
            else:
                gas_signal = "LOW - calm network"

            context_parts.append(f"  Gas Price: {gas_gwei:.1f} gwei - {gas_signal}")

            if onchain.get('gas_price_usd') is not None:
                gas_usd = onchain['gas_price_usd']
                context_parts.append(f"  Gas Cost: ${gas_usd:.2f} (standard transfer)")

        context_parts.append(f"  Data Confidence: {onchain['confidence']:.2f}/1.0")
        if onchain.get('sources'):
            context_parts.append(f"  Sources: {', '.join(onchain['sources'])}")
        context_parts.append("")

    # Recent News & Events
    news = snapshot.get('news')
    if news and news.get('headlines'):
        context_parts.append("RECENT NEWS & EVENTS:")

        # Overall sentiment
        sentiment = news.get('overall_sentiment', 'neutral')
        sentiment_score = news.get('sentiment_score', 50)
        if sentiment_score >= 70:
            sentiment_signal = "STRONGLY BULLISH"
        elif sentiment_score >= 55:
            sentiment_signal = "MODERATELY BULLISH"
        elif sentiment_score <= 30:
            sentiment_signal = "STRONGLY BEARISH"
        elif sentiment_score <= 45:
            sentiment_signal = "MODERATELY BEARISH"
        else:
            sentiment_signal = "NEUTRAL"
        context_parts.append(f"  News Sentiment: {sentiment_score:.0f}/100 ({sentiment_signal})")

        # Sentiment breakdown
        bullish = news.get('bullish_count', 0)
        bearish = news.get('bearish_count', 0)
        neutral = news.get('neutral_count', 0)
        total = bullish + bearish + neutral
        if total > 0:
            context_parts.append(f"  Sentiment Breakdown: {bullish} bullish, {bearish} bearish, {neutral} neutral")

        # Breaking news alert
        breaking = news.get('breaking_news_count', 0)
        if breaking > 0:
            context_parts.append(f"  ⚠️ BREAKING NEWS: {breaking} breaking story(s) in last hour")

        # News velocity
        velocity = news.get('news_velocity')
        if velocity is not None:
            if velocity > 2.0:
                velocity_signal = "HIGH - unusual news activity"
            elif velocity > 1.0:
                velocity_signal = "ELEVATED"
            else:
                velocity_signal = "NORMAL"
            context_parts.append(f"  News Velocity: {velocity:.1f}x average ({velocity_signal})")

        # Top headlines
        headlines = news.get('headlines', [])
        if headlines:
            context_parts.append("  Top Headlines:")
            for i, h in enumerate(headlines[:5], 1):
                title = h.get('title', '')[:80]
                source = h.get('source', 'Unknown')
                sent = h.get('sentiment', 'neutral')
                sent_icon = "📈" if sent == 'bullish' else "📉" if sent == 'bearish' else "➖"
                context_parts.append(f"    {i}. {sent_icon} [{source}] {title}")

        context_parts.append(f"  Data Confidence: {news['confidence']:.2f}/1.0")
        context_parts.append("")

        # Macro Financial News (Ground News - AI Summarized)
        if news.get('ground_news_summary'):
            context_parts.append("MACRO FINANCIAL NEWS (Ground News - AI Summarized):")
            context_parts.append(f"  Summary: {news['ground_news_summary']}")

            macro_sentiment = news.get('ground_news_sentiment', 'neutral')
            if macro_sentiment == 'bullish':
                macro_signal = "BULLISH - Risk-on environment"
            elif macro_sentiment == 'bearish':
                macro_signal = "BEARISH - Risk-off environment"
            else:
                macro_signal = "NEUTRAL"
            context_parts.append(f"  Macro Sentiment: {macro_signal}")

            key_events = news.get('ground_news_key_events', [])
            if key_events:
                context_parts.append("  Key Events:")
                for event in key_events[:5]:
                    context_parts.append(f"    - {event}")

            macro_confidence = news.get('ground_news_confidence', 0)
            if macro_confidence > 0:
                context_parts.append(f"  AI Confidence: {macro_confidence:.1%}")
            context_parts.append("")

    # Social Sentiment (LunarCrush)
    social = snapshot.get('social')
    if social and social.get('confidence', 0) > 0:
        context_parts.append("SOCIAL SENTIMENT (LunarCrush):")

        if social.get('galaxy_score') is not None:
            galaxy = social['galaxy_score']
            if galaxy >= 70:
                galaxy_signal = "STRONG momentum"
            elif galaxy >= 50:
                galaxy_signal = "Moderate momentum"
            else:
                galaxy_signal = "Weak momentum"
            context_parts.append(f"  Galaxy Score: {galaxy:.0f}/100 - {galaxy_signal}")

        if social.get('alt_rank') is not None:
            context_parts.append(f"  Alt Rank: #{social['alt_rank']} (lower is better)")

        if social.get('social_volume') is not None:
            volume = social['social_volume']
            context_parts.append(f"  Social Volume: {volume:,} mentions")

        if social.get('social_volume_change_24h') is not None:
            vol_change = social['social_volume_change_24h']
            vol_dir = "↑" if vol_change >= 0 else "↓"
            if abs(vol_change) > 50:
                vol_signal = "VIRAL" if vol_change > 0 else "DECLINING sharply"
            elif abs(vol_change) > 20:
                vol_signal = "SURGING" if vol_change > 0 else "FALLING"
            else:
                vol_signal = "STABLE"
            context_parts.append(f"  Volume Change (24h): {vol_dir} {abs(vol_change):.1f}% - {vol_signal}")

        if social.get('sentiment_label'):
            sent_label = social['sentiment_label'].upper().replace('_', ' ')
            context_parts.append(f"  Sentiment: {sent_label}")

        if social.get('bullish_pct') is not None and social.get('bearish_pct') is not None:
            bullish = social['bullish_pct']
            bearish = social['bearish_pct']
            context_parts.append(f"  Sentiment Split: {bullish:.1f}% bullish, {bearish:.1f}% bearish")

        if social.get('social_contributors') is not None:
            context_parts.append(f"  Contributors: {social['social_contributors']:,}")

        context_parts.append(f"  Data Confidence: {social['confidence']:.2f}/1.0")
        context_parts.append("")

    # DeFi TVL Summary (DeFiLlama)
    tvl_data = snapshot.get('tvl')
    if tvl_data and tvl_data.get('confidence', 0) > 0:
        context_parts.append("DEFI TVL SUMMARY (DeFiLlama):")

        if tvl_data.get('total_defi_tvl') is not None:
            total_tvl = tvl_data['total_defi_tvl']
            context_parts.append(f"  Total DeFi TVL: ${total_tvl:,.0f}")

        if tvl_data.get('total_tvl_change_1d') is not None:
            tvl_change = tvl_data['total_tvl_change_1d']
            tvl_dir = "↑" if tvl_change >= 0 else "↓"
            if abs(tvl_change) > 5:
                if tvl_change > 0:
                    tvl_signal = "STRONG inflow - bullish fundamental"
                else:
                    tvl_signal = "SIGNIFICANT outflow - bearish signal"
            elif abs(tvl_change) > 2:
                tvl_signal = "Growing" if tvl_change > 0 else "Declining"
            else:
                tvl_signal = "Stable"
            context_parts.append(f"  24h Change: {tvl_dir} {abs(tvl_change):.2f}% - {tvl_signal}")

        if tvl_data.get('tvl_trend'):
            trend = tvl_data['tvl_trend'].upper().replace('_', ' ')
            context_parts.append(f"  TVL Trend: {trend}")

        # Top protocols
        top_protocols = tvl_data.get('top_protocols', [])
        if top_protocols:
            context_parts.append("  Top Protocols by TVL:")
            for proto in top_protocols[:5]:
                name = proto.get('name', 'Unknown')
                proto_tvl = proto.get('tvl', 0)
                change = proto.get('change_1d')
                if change is not None:
                    change_str = f" ({'+' if change >= 0 else ''}{change:.1f}%)"
                else:
                    change_str = ""
                context_parts.append(f"    - {name}: ${proto_tvl:,.0f}{change_str}")

        context_parts.append(f"  Data Confidence: {tvl_data['confidence']:.2f}/1.0")
        context_parts.append("")

    # Liquidation Data (Coinglass)
    liquidations = snapshot.get('liquidations')
    if liquidations and liquidations.get('confidence', 0) > 0:
        context_parts.append("LIQUIDATION DATA (Coinglass):")

        if liquidations.get('total_liquidations_24h') is not None:
            total = liquidations['total_liquidations_24h']
            if total > 500_000_000:
                liq_signal = "⚠️ EXTREME - Major cascade event"
            elif total > 100_000_000:
                liq_signal = "HIGH - Elevated volatility"
            elif total > 50_000_000:
                liq_signal = "MODERATE"
            else:
                liq_signal = "LOW - Calm conditions"
            context_parts.append(f"  Total Liquidations (24h): ${total:,.0f} - {liq_signal}")

        if liquidations.get('long_liquidations_24h') is not None:
            long_liq = liquidations['long_liquidations_24h']
            context_parts.append(f"  Long Liquidations: ${long_liq:,.0f}")

        if liquidations.get('short_liquidations_24h') is not None:
            short_liq = liquidations['short_liquidations_24h']
            context_parts.append(f"  Short Liquidations: ${short_liq:,.0f}")

        if liquidations.get('long_short_ratio') is not None:
            ratio = liquidations['long_short_ratio']
            if ratio > 1.5:
                ratio_signal = "Longs dominant (bearish cascade risk)"
            elif ratio < 0.67:
                ratio_signal = "Shorts dominant (bullish squeeze potential)"
            else:
                ratio_signal = "Balanced"
            context_parts.append(f"  Long/Short Ratio: {ratio:.2f} - {ratio_signal}")

        if liquidations.get('liquidation_sentiment'):
            liq_sentiment = liquidations['liquidation_sentiment'].upper().replace('_', ' ')
            context_parts.append(f"  Liquidation Sentiment: {liq_sentiment}")

        context_parts.append(f"  Data Confidence: {liquidations['confidence']:.2f}/1.0")
        context_parts.append("")

    # Market Depth (Order Book Analysis)
    orderbook = snapshot.get('orderbook')
    if orderbook and orderbook.get('confidence', 0) > 0:
        context_parts.append("MARKET DEPTH (Order Book Analysis):")

        # Bid/Ask Imbalance
        imbalance = orderbook.get('imbalance_ratio', 0)
        imbalance_label = orderbook.get('imbalance_label', 'neutral')
        imbalance_pct = imbalance * 100

        if imbalance > 0.15:
            imbalance_signal = "⬆️ STRONG BUY PRESSURE - more buyers than sellers"
        elif imbalance > 0.05:
            imbalance_signal = "↑ Moderate buy pressure"
        elif imbalance < -0.15:
            imbalance_signal = "⬇️ STRONG SELL PRESSURE - more sellers than buyers"
        elif imbalance < -0.05:
            imbalance_signal = "↓ Moderate sell pressure"
        else:
            imbalance_signal = "➖ Balanced order book"

        context_parts.append(f"  Bid/Ask Imbalance: {imbalance_pct:+.1f}% ({imbalance_label}) - {imbalance_signal}")

        # Spread
        spread = orderbook.get('spread_pct', 0)
        if spread < 0.01:
            spread_signal = "TIGHT - high liquidity"
        elif spread < 0.05:
            spread_signal = "NORMAL"
        else:
            spread_signal = "WIDE - low liquidity"
        context_parts.append(f"  Spread: {spread:.4%} - {spread_signal}")

        # Volume depth
        bid_vol = orderbook.get('bid_volume_usd', 0)
        ask_vol = orderbook.get('ask_volume_usd', 0)
        if bid_vol > 0 or ask_vol > 0:
            context_parts.append(f"  Total Bid Depth: ${bid_vol:,.0f}")
            context_parts.append(f"  Total Ask Depth: ${ask_vol:,.0f}")

        # Liquidity walls
        if orderbook.get('nearest_support_price') is not None:
            support_price = orderbook['nearest_support_price']
            support_size = orderbook.get('nearest_support_size_usd', 0)
            support_dist = orderbook.get('nearest_support_distance_pct', 0)
            context_parts.append(
                f"  Nearest Support Wall: ${support_price:,.2f} "
                f"({support_dist:.1%} below, ${support_size:,.0f})"
            )

        if orderbook.get('nearest_resistance_price') is not None:
            resist_price = orderbook['nearest_resistance_price']
            resist_size = orderbook.get('nearest_resistance_size_usd', 0)
            resist_dist = orderbook.get('nearest_resistance_distance_pct', 0)
            context_parts.append(
                f"  Nearest Resistance Wall: ${resist_price:,.2f} "
                f"({resist_dist:.1%} above, ${resist_size:,.0f})"
            )

        exchanges = orderbook.get('exchanges_analyzed', [])
        if exchanges:
            context_parts.append(f"  Exchanges Analyzed: {', '.join(exchanges)}")
        context_parts.append(f"  Data Confidence: {orderbook['confidence']:.2f}/1.0")
        context_parts.append("")

    # Historical Patterns Section (if provided)
    pattern_context = snapshot.get('pattern_context')
    if pattern_context:
        context_parts.append("=" * 70)
        context_parts.append("HISTORICAL PATTERN ANALYSIS (Learning from Past Predictions)")
        context_parts.append("=" * 70)
        context_parts.append(pattern_context)
        context_parts.append("")

    # Confidence Calibration Section (if provided)
    calibration_context = snapshot.get('calibration_context')
    if calibration_context:
        context_parts.append("=" * 70)
        context_parts.append("CONFIDENCE CALIBRATION (Historical Accuracy Feedback)")
        context_parts.append("=" * 70)
        context_parts.append(calibration_context)
        context_parts.append("")

    # FRED Macro Economic Environment
    macro_data = snapshot.get('macro_data')
    if macro_data and macro_data.get('confidence', 0) > 0:
        context_parts.append("=" * 70)
        context_parts.append("MACRO ECONOMIC ENVIRONMENT (FRED)")
        context_parts.append("=" * 70)

        # Overall macro assessment
        macro_sentiment = macro_data.get('macro_sentiment', 'neutral')
        macro_score = macro_data.get('macro_score', 50)
        risk_env = macro_data.get('risk_environment', 'neutral')

        # Sentiment interpretation
        if macro_score >= 65:
            score_signal = "FAVORABLE for risk assets (crypto-bullish)"
        elif macro_score >= 55:
            score_signal = "MODERATELY FAVORABLE (risk-on)"
        elif macro_score <= 35:
            score_signal = "CHALLENGING for risk assets (crypto-bearish)"
        elif macro_score <= 45:
            score_signal = "MODERATELY CHALLENGING (risk-off)"
        else:
            score_signal = "NEUTRAL (mixed signals)"

        context_parts.append(f"  Macro Score: {macro_score:.0f}/100 - {score_signal}")
        context_parts.append(f"  Macro Sentiment: {macro_sentiment.upper().replace('_', ' ')}")
        context_parts.append(f"  Risk Environment: {risk_env.upper().replace('_', '-')}")
        context_parts.append("")

        # Individual indicators
        indicators = macro_data.get('indicators', {})

        # US Dollar Index (DXY) - inverse correlation with crypto
        usd = indicators.get('usd_dollar')
        if usd and usd.get('value') is not None:
            dxy_value = usd['value']
            dxy_change = usd.get('change_pct')
            dxy_trend = usd.get('trend', 'neutral')
            dxy_signal = usd.get('signal', '')

            context_parts.append("  US Dollar Index (DXY):")
            context_parts.append(f"    Value: {dxy_value:.2f}")
            if dxy_change is not None:
                dxy_dir = "↑" if dxy_change >= 0 else "↓"
                # Rising DXY = bearish for crypto, falling = bullish
                crypto_impact = "bearish for crypto" if dxy_change > 0 else "bullish for crypto"
                context_parts.append(f"    Change: {dxy_dir} {abs(dxy_change):.2f}% ({crypto_impact})")
            if dxy_trend:
                context_parts.append(f"    Trend: {dxy_trend.upper()}")
            if dxy_signal:
                context_parts.append(f"    Signal: {dxy_signal}")

        # S&P 500 - risk correlation
        sp500 = indicators.get('sp500')
        if sp500 and sp500.get('value') is not None:
            sp_value = sp500['value']
            sp_change = sp500.get('change_pct')
            sp_trend = sp500.get('trend', 'neutral')
            sp_signal = sp500.get('signal', '')

            context_parts.append("  S&P 500:")
            context_parts.append(f"    Value: {sp_value:,.2f}")
            if sp_change is not None:
                sp_dir = "↑" if sp_change >= 0 else "↓"
                risk_impact = "risk-on (supportive)" if sp_change > 0 else "risk-off (headwind)"
                context_parts.append(f"    Change: {sp_dir} {abs(sp_change):.2f}% ({risk_impact})")
            if sp_trend:
                context_parts.append(f"    Trend: {sp_trend.upper()}")
            if sp_signal:
                context_parts.append(f"    Signal: {sp_signal}")

        # 10-Year Treasury Yield - opportunity cost
        treasury = indicators.get('treasury_10y')
        if treasury and treasury.get('value') is not None:
            yield_value = treasury['value']
            yield_change = treasury.get('change_pct')
            yield_trend = treasury.get('trend', 'neutral')
            yield_signal = treasury.get('signal', '')

            context_parts.append("  10-Year Treasury Yield:")
            context_parts.append(f"    Yield: {yield_value:.2f}%")
            if yield_change is not None:
                yield_dir = "↑" if yield_change >= 0 else "↓"
                # Rising yields = tighter conditions, headwind for crypto
                policy_impact = "tighter conditions (headwind)" if yield_change > 0 else "easing conditions (tailwind)"
                context_parts.append(f"    Change: {yield_dir} {abs(yield_change):.2f}% ({policy_impact})")
            if yield_trend:
                context_parts.append(f"    Trend: {yield_trend.upper()}")
            if yield_signal:
                context_parts.append(f"    Signal: {yield_signal}")

        # Fed Funds Rate - monetary policy
        fed = indicators.get('fed_funds')
        if fed and fed.get('value') is not None:
            fed_value = fed['value']
            policy_stance = fed.get('policy_stance', 'neutral')

            context_parts.append("  Fed Funds Rate:")
            context_parts.append(f"    Rate: {fed_value:.2f}%")
            if policy_stance:
                context_parts.append(f"    Policy Stance: {policy_stance.upper()}")

        # VIX - fear gauge
        vix = indicators.get('vix')
        if vix and vix.get('value') is not None:
            vix_value = vix['value']
            vix_sentiment = vix.get('risk_sentiment', 'neutral')
            vix_signal = vix.get('signal', '')

            context_parts.append("  VIX (Fear Index):")
            context_parts.append(f"    Value: {vix_value:.2f}")

            # VIX interpretation
            if vix_value > 35:
                vix_interpretation = "⚠️ EXTREME FEAR - contrarian opportunity (potential bottom)"
            elif vix_value > 25:
                vix_interpretation = "HIGH FEAR - elevated volatility, reduce confidence"
            elif vix_value > 20:
                vix_interpretation = "MODERATE - normal caution"
            elif vix_value > 15:
                vix_interpretation = "LOW - complacency, watch for reversals"
            else:
                vix_interpretation = "VERY LOW - extreme complacency, potential top"
            context_parts.append(f"    Level: {vix_interpretation}")
            if vix_sentiment:
                context_parts.append(f"    Sentiment: {vix_sentiment.upper()}")
            if vix_signal:
                context_parts.append(f"    Signal: {vix_signal}")

        context_parts.append(f"  Data Confidence: {macro_data['confidence']:.2f}/1.0")
        context_parts.append(f"  Source: FRED (Federal Reserve Economic Data)")
        context_parts.append("")

    # Multi-timeframe data availability notice
    uses_mtf = snapshot.get('uses_multi_timeframe', False)
    if not uses_mtf:
        context_parts.append("=" * 70)
        context_parts.append("DATA LIMITATION NOTICE")
        context_parts.append("=" * 70)
        context_parts.append("Multi-timeframe analysis (4H, 1H) is NOT available for this prediction.")
        context_parts.append("Only daily timeframe trend data is visible (from EMA cross).")
        context_parts.append("IMPORTANT: Without 4H and 1H confirmation, reduce confidence by 15-20%.")
        context_parts.append("The system prompt's multi-timeframe rules cannot be fully applied.")
        context_parts.append("")

    # Summary Section
    context_parts.append("ANALYSIS REQUEST:")
    context_parts.append("Based on the above comprehensive market data:")
    context_parts.append("1. Analyze the current trend and indicator alignment")
    context_parts.append("2. Predict the most likely direction for the next 4 hours")
    context_parts.append("3. Provide your confidence level (0-100)")
    context_parts.append("4. Factor in on-chain signals if available (whale activity, TVL changes)")
    context_parts.append("5. If historical patterns are present, weight them in your confidence calculation")
    context_parts.append("6. Consider FRED macro environment (DXY, S&P500, Treasury yields, VIX, Fed policy)")
    context_parts.append("7. Explain your reasoning clearly, referencing all relevant data streams")
    if not uses_mtf:
        context_parts.append("8. CRITICAL: Note that multi-timeframe data is missing - cap confidence at 65%")
    context_parts.append("")
    context_parts.append("Return ONLY valid JSON in the specified format.")

    return "\n".join(context_parts)


def format_enhanced_market_context(snapshot: Dict[str, Any]) -> str:
    """
    Format enhanced market snapshot with multi-timeframe analysis (TAAPI Pro mode)
    
    Args:
        snapshot: Market snapshot dictionary with multi-timeframe data
        
    Returns:
        Formatted enhanced market context string
    """
    symbol = snapshot['symbol']
    market = snapshot['market']
    sentiment = snapshot.get('sentiment')
    technical = snapshot.get('technical', {})
    derivatives = snapshot.get('derivatives')
    
    context_parts = []
    
    # Header
    context_parts.append(f"MULTI-TIMEFRAME MARKET ANALYSIS")
    context_parts.append(f"Symbol: {symbol}")
    context_parts.append(f"Timestamp: {snapshot['timestamp']}")
    context_parts.append(f"Data Source: TAAPI Pro (Multi-Timeframe)")
    context_parts.append(f"Overall Confidence: {snapshot['overall_confidence']:.2f}/1.0")
    context_parts.append("")
    
    # Price & Market Data (keep existing)
    context_parts.append("PRICE & MARKET DATA:")
    context_parts.append(f"  Current Price: ${market['price']:,.2f}")
    
    if market.get('price_change_24h') is not None:
        change_24h = market['price_change_24h']
        direction = "↑" if change_24h >= 0 else "↓"
        context_parts.append(f"  24h Change: {direction} {abs(change_24h):.2f}%")
    
    if market.get('high_24h') and market.get('low_24h'):
        context_parts.append(f"  24h Range: ${market['low_24h']:,.2f} - ${market['high_24h']:,.2f}")
    
    if market.get('volume_24h'):
        context_parts.append(f"  24h Volume: ${market['volume_24h']:,.0f}")
    
    context_parts.append("")
    
    # MULTI-TIMEFRAME TECHNICAL ANALYSIS (NEW!)
    if technical.get('timeframes'):
        context_parts.append("=" * 70)
        context_parts.append("MULTI-TIMEFRAME TECHNICAL ANALYSIS (Research-Validated)")
        context_parts.append("=" * 70)
        context_parts.append("")
        
        # Overall Alignment Summary
        overall_trend = technical.get('overall_trend', 'neutral').upper()
        alignment = technical.get('alignment_status', 'conflicting')
        alignment_conf = technical.get('alignment_confidence', 0)
        recommendation = technical.get('recommendation', 'HOLD')
        volume_conf = technical.get('volume_confirmed', False)
        regime = technical.get('market_regime', 'ranging')
        
        # Alignment visual indicator
        if alignment == 'fully_aligned':
            align_indicator = "FULLY ALIGNED ✓"
            conf_note = "(High confidence - all timeframes agree)"
        elif alignment == 'partially_aligned':
            align_indicator = "PARTIALLY ALIGNED ~"
            conf_note = "(Moderate confidence - 2/3 timeframes agree)"
        else:
            align_indicator = "CONFLICTING ✗"
            conf_note = "(Low confidence - timeframes disagree)"
        
        context_parts.append(f"OVERALL TREND: {overall_trend}")
        context_parts.append(f"TIMEFRAME ALIGNMENT: {align_indicator} {conf_note}")
        context_parts.append(f"ALIGNMENT CONFIDENCE: {alignment_conf:.1%}")
        context_parts.append(f"RECOMMENDATION: {recommendation}")
        context_parts.append(f"VOLUME CONFIRMED: {'YES ✓' if volume_conf else 'NO'}")
        context_parts.append(f"MARKET REGIME: {regime.replace('_', ' ').upper()}")
        context_parts.append("")
        
        # Signal Aggregation
        signals = technical.get('signals', {})
        bullish = signals.get('bullish', 0)
        bearish = signals.get('bearish', 0)
        neutral = signals.get('neutral', 0)
        total = bullish + bearish + neutral
        
        context_parts.append(f"SIGNAL AGGREGATION (across all timeframes):")
        context_parts.append(f"  Bullish Signals: {bullish}/{total} ({bullish/total*100:.0f}%)")
        context_parts.append(f"  Bearish Signals: {bearish}/{total} ({bearish/total*100:.0f}%)")
        context_parts.append(f"  Neutral Signals: {neutral}/{total} ({neutral/total*100:.0f}%)")
        context_parts.append("")
        
        # Daily Timeframe (30% weight - Macro Filter)
        daily = technical['timeframes'].get('1d')
        if daily:
            context_parts.append("─" * 70)
            context_parts.append("DAILY TIMEFRAME (30% weight) - Macro Trend Filter")
            context_parts.append("─" * 70)
            trend = daily['trend_direction'].upper()
            trend_str = daily['trend_strength']
            conf = daily['confidence']
            context_parts.append(f"  Trend: {trend} (Strength: {trend_str:.0%})")
            context_parts.append(f"  Confidence: {conf:.1%}")
            context_parts.append(f"  Market Regime: {daily['market_regime'].replace('_', ' ').title()}")
            
            if daily.get('ema_200'):
                context_parts.append(f"  EMA(200): ${daily['ema_200']:,.2f}")
            if daily.get('adx'):
                context_parts.append(f"  ADX: {daily['adx']:.1f} (Trend strength indicator)")
            if daily.get('macd_histogram'):
                macd_h = daily['macd_histogram']
                macd_signal = "Bullish" if macd_h > 0 else "Bearish"
                context_parts.append(f"  MACD Histogram: {macd_h:.2f} ({macd_signal})")
            
            daily_signals = daily.get('signals', {})
            context_parts.append(f"  Signals: {daily_signals['bullish']} bullish, {daily_signals['bearish']} bearish, {daily_signals['neutral']} neutral")
            context_parts.append("")
        
        # 4-Hour Timeframe (50% weight - Primary Decision)
        four_hour = technical['timeframes'].get('4h')
        if four_hour:
            context_parts.append("─" * 70)
            context_parts.append("4-HOUR TIMEFRAME (50% weight) - PRIMARY DECISION LAYER ⭐")
            context_parts.append("─" * 70)
            trend = four_hour['trend_direction'].upper()
            trend_str = four_hour['trend_strength']
            conf = four_hour['confidence']
            context_parts.append(f"  Trend: {trend} (Strength: {trend_str:.0%})")
            context_parts.append(f"  Confidence: {conf:.1%}")
            context_parts.append(f"  Market Regime: {four_hour['market_regime'].replace('_', ' ').title()}")
            
            # Key indicators
            if four_hour.get('rsi'):
                rsi = four_hour['rsi']
                rsi_zone = "Oversold" if rsi < 30 else "Overbought" if rsi > 70 else "Neutral"
                context_parts.append(f"  RSI(14): {rsi:.1f} ({rsi_zone})")
            
            if four_hour.get('macd_histogram'):
                macd_h = four_hour['macd_histogram']
                macd_signal = "Bullish momentum" if macd_h > 0 else "Bearish momentum"
                context_parts.append(f"  MACD Histogram: {macd_h:.2f} ({macd_signal})")
            
            if four_hour.get('ema_50') and four_hour.get('ema_200'):
                ema50 = four_hour['ema_50']
                ema200 = four_hour['ema_200']
                ema_cross = "Golden Cross (50 > 200)" if ema50 > ema200 else "Death Cross (50 < 200)"
                context_parts.append(f"  EMA Cross: {ema_cross}")
                context_parts.append(f"    EMA(50): ${ema50:,.2f}")
                context_parts.append(f"    EMA(200): ${ema200:,.2f}")
            
            if four_hour.get('adx'):
                context_parts.append(f"  ADX: {four_hour['adx']:.1f}")
            
            four_hour_signals = four_hour.get('signals', {})
            context_parts.append(f"  Signals: {four_hour_signals['bullish']} bullish, {four_hour_signals['bearish']} bearish, {four_hour_signals['neutral']} neutral")
            context_parts.append("")
        
        # 1-Hour Timeframe (20% weight - Entry Timing)
        one_hour = technical['timeframes'].get('1h')
        if one_hour:
            context_parts.append("─" * 70)
            context_parts.append("1-HOUR TIMEFRAME (20% weight) - Entry Timing Refinement")
            context_parts.append("─" * 70)
            trend = one_hour['trend_direction'].upper()
            trend_str = one_hour['trend_strength']
            conf = one_hour['confidence']
            context_parts.append(f"  Trend: {trend} (Strength: {trend_str:.0%})")
            context_parts.append(f"  Confidence: {conf:.1%}")
            
            if one_hour.get('rsi'):
                rsi = one_hour['rsi']
                rsi_zone = "Oversold" if rsi < 35 else "Overbought" if rsi > 65 else "Neutral"
                context_parts.append(f"  RSI(14): {rsi:.1f} ({rsi_zone})")
            
            if one_hour.get('macd_histogram'):
                macd_h = one_hour['macd_histogram']
                macd_signal = "Bullish" if macd_h > 0 else "Bearish"
                context_parts.append(f"  MACD Histogram: {macd_h:.2f} ({macd_signal})")
            
            one_hour_signals = one_hour.get('signals', {})
            context_parts.append(f"  Signals: {one_hour_signals['bullish']} bullish, {one_hour_signals['bearish']} bearish, {one_hour_signals['neutral']} neutral")
            context_parts.append("")
        
        context_parts.append("=" * 70)
        context_parts.append("")
    
    # Sentiment Analysis (enhanced - only show available data)
    if sentiment:
        context_parts.append("SENTIMENT ANALYSIS:")
        context_parts.append(f"  Composite Score: {sentiment['score']:.1f}/100")
        
        if sentiment.get('fear_greed_index') is not None:
            fgi = sentiment['fear_greed_index']
            label = sentiment.get('fear_greed_label', 'Unknown')
            context_parts.append(f"  Fear & Greed Index: {fgi:.0f}/100 ({label})")
        
        # Only show Reddit data if actually available
        if sentiment.get('reddit_score') is not None and sentiment.get('reddit_posts_24h', 0) > 0:
            reddit_score = sentiment['reddit_score']
            posts = sentiment['reddit_posts_24h']
            sentiment_label = "Bullish" if reddit_score > 60 else "Bearish" if reddit_score < 40 else "Neutral"
            context_parts.append(f"  Reddit Sentiment: {reddit_score:.1f}/100 ({sentiment_label})")
            context_parts.append(f"  Reddit Activity: {posts} posts analyzed (24h)")
        
        context_parts.append("")
    
    # Derivatives Market (enhanced interpretation)
    if derivatives:
        context_parts.append("DERIVATIVES MARKET:")
        
        # Enhanced funding rate interpretation
        if derivatives.get('avg_funding_rate') is not None:
            funding = derivatives['avg_funding_rate']
            funding_pct = funding * 100
            
            if funding > 0.05:
                funding_signal = "⚠️ EXTREME BULLISH: Overleveraged longs, short squeeze risk high"
            elif funding > 0.01:
                funding_signal = "Bullish (longs paying shorts, sustainable)"
            elif funding < -0.05:
                funding_signal = "⚠️ EXTREME BEARISH: Overleveraged shorts, long squeeze risk high"
            elif funding < -0.01:
                funding_signal = "Bearish (shorts paying longs, sustainable)"
            else:
                funding_signal = "Neutral (balanced positioning)"
            
            context_parts.append(f"  Funding Rate: {funding_pct:.4f}% - {funding_signal}")
        
        # Enhanced OI interpretation
        if derivatives.get('total_open_interest'):
            oi = derivatives['total_open_interest']
            context_parts.append(f"  Total Open Interest: ${oi:,.0f}")
            
            if derivatives.get('oi_change_24h') is not None:
                oi_change = derivatives['oi_change_24h']
                oi_direction = "↑" if oi_change >= 0 else "↓"
                
                if abs(oi_change) > 10:
                    if oi_change > 0:
                        oi_signal = "STRONG growth - trend confirmation"
                    else:
                        oi_signal = "SHARP decline - trend exhaustion warning"
                elif abs(oi_change) > 5:
                    oi_signal = "Growing positions" if oi_change > 0 else "Decreasing positions"
                else:
                    oi_signal = "Stable (low conviction)"
                
                context_parts.append(f"  OI Change (24h): {oi_direction} {abs(oi_change):.2f}% - {oi_signal}")
        
        # Enhanced liquidations interpretation
        if derivatives.get('liquidations_24h_usd'):
            liq = derivatives['liquidations_24h_usd']
            
            if liq > 500_000_000:
                liq_signal = "⚠️ EXTREME CASCADE: High volatility expected"
            elif liq > 100_000_000:
                liq_signal = "HIGH: Elevated volatility"
            elif liq > 50_000_000:
                liq_signal = "MODERATE: Normal volatility"
            else:
                liq_signal = "LOW: Calm conditions"
            
            context_parts.append(f"  Liquidations (24h): ${liq:,.0f} - {liq_signal}")
        
        context_parts.append("")
    
    # On-Chain Intelligence (Enhanced with whale tracking and exchange flows)
    onchain = snapshot.get('onchain')
    if onchain:
        context_parts.append("ON-CHAIN INTELLIGENCE:")

        if onchain.get('whale_transactions_24h') is not None:
            whales = onchain['whale_transactions_24h']
            if whales > 150:
                whale_signal = "⚠️ EXTREME: Heavy whale activity, major move likely"
            elif whales > 100:
                whale_signal = "HIGH: Significant whale activity, monitor closely"
            elif whales > 50:
                whale_signal = "MODERATE: Normal whale activity"
            else:
                whale_signal = "LOW: Minimal whale activity"
            context_parts.append(f"  Whale Transactions (24h): {whales} - {whale_signal}")

        if onchain.get('whale_volume_usd_24h') is not None:
            volume = onchain['whale_volume_usd_24h']
            context_parts.append(f"  Whale Volume (24h): ${volume:,.0f}")

        # Exchange flows
        if onchain.get('exchange_inflow_usd_24h') is not None or onchain.get('exchange_outflow_usd_24h') is not None:
            context_parts.append("  Exchange Flows:")
            if onchain.get('exchange_inflow_usd_24h') is not None:
                inflow = onchain['exchange_inflow_usd_24h']
                context_parts.append(f"    Inflow (24h): ${inflow:,.0f}")
            if onchain.get('exchange_outflow_usd_24h') is not None:
                outflow = onchain['exchange_outflow_usd_24h']
                context_parts.append(f"    Outflow (24h): ${outflow:,.0f}")
            if onchain.get('net_exchange_flow_usd') is not None:
                net_flow = onchain['net_exchange_flow_usd']
                flow_direction = "↓ to exchanges (bearish)" if net_flow > 0 else "↑ from exchanges (bullish)"
                context_parts.append(f"    Net Flow: ${abs(net_flow):,.0f} {flow_direction}")
            if onchain.get('flow_sentiment') is not None:
                flow_sent = onchain['flow_sentiment']
                context_parts.append(f"    Flow Sentiment: {flow_sent.upper()}")

        # SOPR
        if onchain.get('sopr') is not None:
            sopr = onchain['sopr']
            sopr_signal = onchain.get('sopr_signal', 'neutral')
            if sopr > 1.05:
                sopr_interpretation = "Profit-taking dominant (potential top)"
            elif sopr > 1.0:
                sopr_interpretation = "Holders in profit (healthy)"
            elif sopr < 0.95:
                sopr_interpretation = "Capitulation (potential bottom)"
            else:
                sopr_interpretation = "Break-even zone"
            context_parts.append(f"  SOPR: {sopr:.4f} - {sopr_interpretation} ({sopr_signal})")

        if onchain.get('active_addresses_24h') is not None:
            addresses = onchain['active_addresses_24h']
            context_parts.append(f"  Active Addresses (24h): {addresses:,}")

        if onchain.get('new_addresses_24h') is not None:
            new_addr = onchain['new_addresses_24h']
            context_parts.append(f"  New Addresses (24h): {new_addr:,}")

        if onchain.get('transaction_count_24h') is not None:
            txns = onchain['transaction_count_24h']
            context_parts.append(f"  Transaction Count (24h): {txns:,}")

        if onchain.get('tvl') is not None:
            tvl = onchain['tvl']
            if onchain.get('tvl_change_24h') is not None:
                tvl_change = onchain['tvl_change_24h']
                tvl_direction = "↑" if tvl_change >= 0 else "↓"
                if abs(tvl_change) > 15:
                    tvl_signal = "STRONG growth - bullish fundamental" if tvl_change > 0 else "SHARP decline - bearish fundamental"
                elif abs(tvl_change) > 10:
                    tvl_signal = "Notable change" if tvl_change > 0 else "Concerning decline"
                elif abs(tvl_change) > 5:
                    tvl_signal = "Growing" if tvl_change > 0 else "Declining"
                else:
                    tvl_signal = "Stable"
                context_parts.append(f"  TVL: ${tvl:,.0f} ({tvl_direction} {abs(tvl_change):.1f}%) - {tvl_signal}")
            else:
                context_parts.append(f"  TVL: ${tvl:,.0f}")

        if onchain.get('gas_price_gwei') is not None:
            gas_gwei = onchain['gas_price_gwei']
            if gas_gwei > 100:
                gas_signal = "⚠️ EXTREME congestion"
            elif gas_gwei > 50:
                gas_signal = "HIGH activity"
            elif gas_gwei > 20:
                gas_signal = "MODERATE"
            else:
                gas_signal = "LOW"
            context_parts.append(f"  Gas Price: {gas_gwei:.1f} gwei - {gas_signal}")

        context_parts.append(f"  Data Confidence: {onchain['confidence']:.2f}/1.0")
        if onchain.get('sources'):
            context_parts.append(f"  Sources: {', '.join(onchain['sources'])}")
        context_parts.append("")

    # Recent News & Events
    news = snapshot.get('news')
    if news and news.get('headlines'):
        context_parts.append("RECENT NEWS & EVENTS:")

        sentiment_score = news.get('sentiment_score', 50)
        if sentiment_score >= 70:
            sentiment_signal = "STRONGLY BULLISH"
        elif sentiment_score >= 55:
            sentiment_signal = "MODERATELY BULLISH"
        elif sentiment_score <= 30:
            sentiment_signal = "STRONGLY BEARISH"
        elif sentiment_score <= 45:
            sentiment_signal = "MODERATELY BEARISH"
        else:
            sentiment_signal = "NEUTRAL"
        context_parts.append(f"  News Sentiment: {sentiment_score:.0f}/100 ({sentiment_signal})")

        bullish = news.get('bullish_count', 0)
        bearish = news.get('bearish_count', 0)
        neutral = news.get('neutral_count', 0)
        total = bullish + bearish + neutral
        if total > 0:
            context_parts.append(f"  Sentiment Breakdown: {bullish} bullish, {bearish} bearish, {neutral} neutral")

        breaking = news.get('breaking_news_count', 0)
        if breaking > 0:
            context_parts.append(f"  ⚠️ BREAKING NEWS: {breaking} breaking story(s) in last hour")

        velocity = news.get('news_velocity')
        if velocity is not None:
            if velocity > 2.0:
                velocity_signal = "HIGH - unusual news activity"
            elif velocity > 1.0:
                velocity_signal = "ELEVATED"
            else:
                velocity_signal = "NORMAL"
            context_parts.append(f"  News Velocity: {velocity:.1f}x average ({velocity_signal})")

        headlines = news.get('headlines', [])
        if headlines:
            context_parts.append("  Top Headlines:")
            for i, h in enumerate(headlines[:5], 1):
                title = h.get('title', '')[:80]
                source = h.get('source', 'Unknown')
                sent = h.get('sentiment', 'neutral')
                sent_icon = "📈" if sent == 'bullish' else "📉" if sent == 'bearish' else "➖"
                context_parts.append(f"    {i}. {sent_icon} [{source}] {title}")

        context_parts.append(f"  Data Confidence: {news['confidence']:.2f}/1.0")
        context_parts.append("")

        # Macro Financial News (Ground News - AI Summarized)
        if news.get('ground_news_summary'):
            context_parts.append("MACRO FINANCIAL NEWS (Ground News - AI Summarized):")
            context_parts.append(f"  Summary: {news['ground_news_summary']}")

            macro_sentiment = news.get('ground_news_sentiment', 'neutral')
            if macro_sentiment == 'bullish':
                macro_signal = "BULLISH - Risk-on environment"
            elif macro_sentiment == 'bearish':
                macro_signal = "BEARISH - Risk-off environment"
            else:
                macro_signal = "NEUTRAL"
            context_parts.append(f"  Macro Sentiment: {macro_signal}")

            key_events = news.get('ground_news_key_events', [])
            if key_events:
                context_parts.append("  Key Events:")
                for event in key_events[:5]:
                    context_parts.append(f"    - {event}")

            macro_confidence = news.get('ground_news_confidence', 0)
            if macro_confidence > 0:
                context_parts.append(f"  AI Confidence: {macro_confidence:.1%}")
            context_parts.append("")

    # Social Sentiment (LunarCrush)
    social = snapshot.get('social')
    if social and social.get('confidence', 0) > 0:
        context_parts.append("SOCIAL SENTIMENT (LunarCrush):")

        if social.get('galaxy_score') is not None:
            galaxy = social['galaxy_score']
            if galaxy >= 70:
                galaxy_signal = "STRONG momentum"
            elif galaxy >= 50:
                galaxy_signal = "Moderate momentum"
            else:
                galaxy_signal = "Weak momentum"
            context_parts.append(f"  Galaxy Score: {galaxy:.0f}/100 - {galaxy_signal}")

        if social.get('alt_rank') is not None:
            context_parts.append(f"  Alt Rank: #{social['alt_rank']} (lower is better)")

        if social.get('social_volume') is not None:
            volume = social['social_volume']
            context_parts.append(f"  Social Volume: {volume:,} mentions")

        if social.get('social_volume_change_24h') is not None:
            vol_change = social['social_volume_change_24h']
            vol_dir = "↑" if vol_change >= 0 else "↓"
            if abs(vol_change) > 50:
                vol_signal = "VIRAL" if vol_change > 0 else "DECLINING sharply"
            elif abs(vol_change) > 20:
                vol_signal = "SURGING" if vol_change > 0 else "FALLING"
            else:
                vol_signal = "STABLE"
            context_parts.append(f"  Volume Change (24h): {vol_dir} {abs(vol_change):.1f}% - {vol_signal}")

        if social.get('sentiment_label'):
            sent_label = social['sentiment_label'].upper().replace('_', ' ')
            context_parts.append(f"  Sentiment: {sent_label}")

        if social.get('bullish_pct') is not None and social.get('bearish_pct') is not None:
            bullish = social['bullish_pct']
            bearish = social['bearish_pct']
            context_parts.append(f"  Sentiment Split: {bullish:.1f}% bullish, {bearish:.1f}% bearish")

        if social.get('social_contributors') is not None:
            context_parts.append(f"  Contributors: {social['social_contributors']:,}")

        context_parts.append(f"  Data Confidence: {social['confidence']:.2f}/1.0")
        context_parts.append("")

    # DeFi TVL Summary (DeFiLlama)
    tvl_data = snapshot.get('tvl')
    if tvl_data and tvl_data.get('confidence', 0) > 0:
        context_parts.append("DEFI TVL SUMMARY (DeFiLlama):")

        if tvl_data.get('total_defi_tvl') is not None:
            total_tvl = tvl_data['total_defi_tvl']
            context_parts.append(f"  Total DeFi TVL: ${total_tvl:,.0f}")

        if tvl_data.get('total_tvl_change_1d') is not None:
            tvl_change = tvl_data['total_tvl_change_1d']
            tvl_dir = "↑" if tvl_change >= 0 else "↓"
            if abs(tvl_change) > 5:
                if tvl_change > 0:
                    tvl_signal = "STRONG inflow - bullish fundamental"
                else:
                    tvl_signal = "SIGNIFICANT outflow - bearish signal"
            elif abs(tvl_change) > 2:
                tvl_signal = "Growing" if tvl_change > 0 else "Declining"
            else:
                tvl_signal = "Stable"
            context_parts.append(f"  24h Change: {tvl_dir} {abs(tvl_change):.2f}% - {tvl_signal}")

        if tvl_data.get('tvl_trend'):
            trend = tvl_data['tvl_trend'].upper().replace('_', ' ')
            context_parts.append(f"  TVL Trend: {trend}")

        # Top protocols
        top_protocols = tvl_data.get('top_protocols', [])
        if top_protocols:
            context_parts.append("  Top Protocols by TVL:")
            for proto in top_protocols[:5]:
                name = proto.get('name', 'Unknown')
                proto_tvl = proto.get('tvl', 0)
                change = proto.get('change_1d')
                if change is not None:
                    change_str = f" ({'+' if change >= 0 else ''}{change:.1f}%)"
                else:
                    change_str = ""
                context_parts.append(f"    - {name}: ${proto_tvl:,.0f}{change_str}")

        context_parts.append(f"  Data Confidence: {tvl_data['confidence']:.2f}/1.0")
        context_parts.append("")

    # Liquidation Data (Coinglass)
    liquidations = snapshot.get('liquidations')
    if liquidations and liquidations.get('confidence', 0) > 0:
        context_parts.append("LIQUIDATION DATA (Coinglass):")

        if liquidations.get('total_liquidations_24h') is not None:
            total = liquidations['total_liquidations_24h']
            if total > 500_000_000:
                liq_signal = "⚠️ EXTREME - Major cascade event"
            elif total > 100_000_000:
                liq_signal = "HIGH - Elevated volatility"
            elif total > 50_000_000:
                liq_signal = "MODERATE"
            else:
                liq_signal = "LOW - Calm conditions"
            context_parts.append(f"  Total Liquidations (24h): ${total:,.0f} - {liq_signal}")

        if liquidations.get('long_liquidations_24h') is not None:
            long_liq = liquidations['long_liquidations_24h']
            context_parts.append(f"  Long Liquidations: ${long_liq:,.0f}")

        if liquidations.get('short_liquidations_24h') is not None:
            short_liq = liquidations['short_liquidations_24h']
            context_parts.append(f"  Short Liquidations: ${short_liq:,.0f}")

        if liquidations.get('long_short_ratio') is not None:
            ratio = liquidations['long_short_ratio']
            if ratio > 1.5:
                ratio_signal = "Longs dominant (bearish cascade risk)"
            elif ratio < 0.67:
                ratio_signal = "Shorts dominant (bullish squeeze potential)"
            else:
                ratio_signal = "Balanced"
            context_parts.append(f"  Long/Short Ratio: {ratio:.2f} - {ratio_signal}")

        if liquidations.get('liquidation_sentiment'):
            liq_sentiment = liquidations['liquidation_sentiment'].upper().replace('_', ' ')
            context_parts.append(f"  Liquidation Sentiment: {liq_sentiment}")

        context_parts.append(f"  Data Confidence: {liquidations['confidence']:.2f}/1.0")
        context_parts.append("")

    # Market Depth (Order Book Analysis)
    orderbook = snapshot.get('orderbook')
    if orderbook and orderbook.get('confidence', 0) > 0:
        context_parts.append("MARKET DEPTH (Order Book Analysis):")

        imbalance = orderbook.get('imbalance_ratio', 0)
        imbalance_label = orderbook.get('imbalance_label', 'neutral')
        imbalance_pct = imbalance * 100

        if imbalance > 0.15:
            imbalance_signal = "⬆️ STRONG BUY PRESSURE - more buyers than sellers"
        elif imbalance > 0.05:
            imbalance_signal = "↑ Moderate buy pressure"
        elif imbalance < -0.15:
            imbalance_signal = "⬇️ STRONG SELL PRESSURE - more sellers than buyers"
        elif imbalance < -0.05:
            imbalance_signal = "↓ Moderate sell pressure"
        else:
            imbalance_signal = "➖ Balanced order book"

        context_parts.append(f"  Bid/Ask Imbalance: {imbalance_pct:+.1f}% ({imbalance_label}) - {imbalance_signal}")

        spread = orderbook.get('spread_pct', 0)
        if spread < 0.01:
            spread_signal = "TIGHT - high liquidity"
        elif spread < 0.05:
            spread_signal = "NORMAL"
        else:
            spread_signal = "WIDE - low liquidity"
        context_parts.append(f"  Spread: {spread:.4%} - {spread_signal}")

        bid_vol = orderbook.get('bid_volume_usd', 0)
        ask_vol = orderbook.get('ask_volume_usd', 0)
        if bid_vol > 0 or ask_vol > 0:
            context_parts.append(f"  Total Bid Depth: ${bid_vol:,.0f}")
            context_parts.append(f"  Total Ask Depth: ${ask_vol:,.0f}")

        if orderbook.get('nearest_support_price') is not None:
            support_price = orderbook['nearest_support_price']
            support_size = orderbook.get('nearest_support_size_usd', 0)
            support_dist = orderbook.get('nearest_support_distance_pct', 0)
            context_parts.append(
                f"  Nearest Support Wall: ${support_price:,.2f} "
                f"({support_dist:.1%} below, ${support_size:,.0f})"
            )

        if orderbook.get('nearest_resistance_price') is not None:
            resist_price = orderbook['nearest_resistance_price']
            resist_size = orderbook.get('nearest_resistance_size_usd', 0)
            resist_dist = orderbook.get('nearest_resistance_distance_pct', 0)
            context_parts.append(
                f"  Nearest Resistance Wall: ${resist_price:,.2f} "
                f"({resist_dist:.1%} above, ${resist_size:,.0f})"
            )

        exchanges = orderbook.get('exchanges_analyzed', [])
        if exchanges:
            context_parts.append(f"  Exchanges Analyzed: {', '.join(exchanges)}")
        context_parts.append(f"  Data Confidence: {orderbook['confidence']:.2f}/1.0")
        context_parts.append("")

    # Historical Patterns Section (if provided)
    pattern_context = snapshot.get('pattern_context')
    if pattern_context:
        context_parts.append("=" * 70)
        context_parts.append("HISTORICAL PATTERN ANALYSIS (Learning from Past Predictions)")
        context_parts.append("=" * 70)
        context_parts.append(pattern_context)
        context_parts.append("")

    # Confidence Calibration Section (if provided)
    calibration_context = snapshot.get('calibration_context')
    if calibration_context:
        context_parts.append("=" * 70)
        context_parts.append("CONFIDENCE CALIBRATION (Historical Accuracy Feedback)")
        context_parts.append("=" * 70)
        context_parts.append(calibration_context)
        context_parts.append("")

    # FRED Macro Economic Environment
    macro_data = snapshot.get('macro_data')
    if macro_data and macro_data.get('confidence', 0) > 0:
        context_parts.append("=" * 70)
        context_parts.append("MACRO ECONOMIC ENVIRONMENT (FRED)")
        context_parts.append("=" * 70)

        # Overall macro assessment
        macro_sentiment = macro_data.get('macro_sentiment', 'neutral')
        macro_score = macro_data.get('macro_score', 50)
        risk_env = macro_data.get('risk_environment', 'neutral')

        # Sentiment interpretation
        if macro_score >= 65:
            score_signal = "FAVORABLE for risk assets (crypto-bullish)"
        elif macro_score >= 55:
            score_signal = "MODERATELY FAVORABLE (risk-on)"
        elif macro_score <= 35:
            score_signal = "CHALLENGING for risk assets (crypto-bearish)"
        elif macro_score <= 45:
            score_signal = "MODERATELY CHALLENGING (risk-off)"
        else:
            score_signal = "NEUTRAL (mixed signals)"

        context_parts.append(f"  Macro Score: {macro_score:.0f}/100 - {score_signal}")
        context_parts.append(f"  Macro Sentiment: {macro_sentiment.upper().replace('_', ' ')}")
        context_parts.append(f"  Risk Environment: {risk_env.upper().replace('_', '-')}")
        context_parts.append("")

        # Individual indicators
        indicators = macro_data.get('indicators', {})

        # US Dollar Index (DXY) - inverse correlation with crypto
        usd = indicators.get('usd_dollar')
        if usd and usd.get('value') is not None:
            dxy_value = usd['value']
            dxy_change = usd.get('change_pct')
            dxy_trend = usd.get('trend', 'neutral')
            dxy_signal = usd.get('signal', '')

            context_parts.append("  US Dollar Index (DXY):")
            context_parts.append(f"    Value: {dxy_value:.2f}")
            if dxy_change is not None:
                dxy_dir = "↑" if dxy_change >= 0 else "↓"
                # Rising DXY = bearish for crypto, falling = bullish
                crypto_impact = "bearish for crypto" if dxy_change > 0 else "bullish for crypto"
                context_parts.append(f"    Change: {dxy_dir} {abs(dxy_change):.2f}% ({crypto_impact})")
            if dxy_trend:
                context_parts.append(f"    Trend: {dxy_trend.upper()}")
            if dxy_signal:
                context_parts.append(f"    Signal: {dxy_signal}")

        # S&P 500 - risk correlation
        sp500 = indicators.get('sp500')
        if sp500 and sp500.get('value') is not None:
            sp_value = sp500['value']
            sp_change = sp500.get('change_pct')
            sp_trend = sp500.get('trend', 'neutral')
            sp_signal = sp500.get('signal', '')

            context_parts.append("  S&P 500:")
            context_parts.append(f"    Value: {sp_value:,.2f}")
            if sp_change is not None:
                sp_dir = "↑" if sp_change >= 0 else "↓"
                risk_impact = "risk-on (supportive)" if sp_change > 0 else "risk-off (headwind)"
                context_parts.append(f"    Change: {sp_dir} {abs(sp_change):.2f}% ({risk_impact})")
            if sp_trend:
                context_parts.append(f"    Trend: {sp_trend.upper()}")
            if sp_signal:
                context_parts.append(f"    Signal: {sp_signal}")

        # 10-Year Treasury Yield - opportunity cost
        treasury = indicators.get('treasury_10y')
        if treasury and treasury.get('value') is not None:
            yield_value = treasury['value']
            yield_change = treasury.get('change_pct')
            yield_trend = treasury.get('trend', 'neutral')
            yield_signal = treasury.get('signal', '')

            context_parts.append("  10-Year Treasury Yield:")
            context_parts.append(f"    Yield: {yield_value:.2f}%")
            if yield_change is not None:
                yield_dir = "↑" if yield_change >= 0 else "↓"
                # Rising yields = tighter conditions, headwind for crypto
                policy_impact = "tighter conditions (headwind)" if yield_change > 0 else "easing conditions (tailwind)"
                context_parts.append(f"    Change: {yield_dir} {abs(yield_change):.2f}% ({policy_impact})")
            if yield_trend:
                context_parts.append(f"    Trend: {yield_trend.upper()}")
            if yield_signal:
                context_parts.append(f"    Signal: {yield_signal}")

        # Fed Funds Rate - monetary policy
        fed = indicators.get('fed_funds')
        if fed and fed.get('value') is not None:
            fed_value = fed['value']
            policy_stance = fed.get('policy_stance', 'neutral')

            context_parts.append("  Fed Funds Rate:")
            context_parts.append(f"    Rate: {fed_value:.2f}%")
            if policy_stance:
                context_parts.append(f"    Policy Stance: {policy_stance.upper()}")

        # VIX - fear gauge
        vix = indicators.get('vix')
        if vix and vix.get('value') is not None:
            vix_value = vix['value']
            vix_sentiment = vix.get('risk_sentiment', 'neutral')
            vix_signal = vix.get('signal', '')

            context_parts.append("  VIX (Fear Index):")
            context_parts.append(f"    Value: {vix_value:.2f}")

            # VIX interpretation
            if vix_value > 35:
                vix_interpretation = "⚠️ EXTREME FEAR - contrarian opportunity (potential bottom)"
            elif vix_value > 25:
                vix_interpretation = "HIGH FEAR - elevated volatility, reduce confidence"
            elif vix_value > 20:
                vix_interpretation = "MODERATE - normal caution"
            elif vix_value > 15:
                vix_interpretation = "LOW - complacency, watch for reversals"
            else:
                vix_interpretation = "VERY LOW - extreme complacency, potential top"
            context_parts.append(f"    Level: {vix_interpretation}")
            if vix_sentiment:
                context_parts.append(f"    Sentiment: {vix_sentiment.upper()}")
            if vix_signal:
                context_parts.append(f"    Signal: {vix_signal}")

        context_parts.append(f"  Data Confidence: {macro_data['confidence']:.2f}/1.0")
        context_parts.append(f"  Source: FRED (Federal Reserve Economic Data)")
        context_parts.append("")

    # Analysis Request
    context_parts.append("ANALYSIS REQUEST:")
    context_parts.append("Based on the above multi-timeframe analysis:")
    context_parts.append("1. Consider the hierarchical timeframe weighting (4H=50%, Daily=30%, 1H=20%)")
    context_parts.append("2. Evaluate the timeframe alignment status and its impact on confidence")
    context_parts.append("3. Factor in volume confirmation if present (+5-10% confidence boost)")
    context_parts.append("4. Account for market regime (trending vs ranging)")
    context_parts.append("5. Consider on-chain signals (whale activity, exchange flows, SOPR)")
    context_parts.append("6. Factor in news sentiment and macro news context (Ground News)")
    context_parts.append("7. Consider order book imbalance and liquidity walls")
    context_parts.append("8. Evaluate social sentiment from LunarCrush (galaxy score, volume)")
    context_parts.append("9. Factor in DeFi TVL trends and liquidation data")
    context_parts.append("10. Consider FRED macro environment (DXY, S&P500, Treasury yields, VIX, Fed policy)")
    context_parts.append("11. If historical patterns are present, weight them heavily in confidence calculation")
    context_parts.append("12. Predict the most likely direction for the next 4 hours")
    context_parts.append("13. Provide confidence level based on alignment, indicators, and all data streams")
    context_parts.append("14. Explain your reasoning, referencing specific timeframes and data sources")
    context_parts.append("")
    context_parts.append("Return ONLY valid JSON in the specified format.")

    return "\n".join(context_parts)


def format_market_context(snapshot: Dict[str, Any]) -> str:
    """
    Format market snapshot into rich context for Claude (router function)
    
    Routes to enhanced format if multi-timeframe data available,
    otherwise uses basic format.
    
    Args:
        snapshot: Market snapshot dictionary from UnifiedDataClient
        
    Returns:
        Formatted market context string
    """
    # Check if multi-timeframe data is available
    uses_mtf = snapshot.get('uses_multi_timeframe', False)
    
    if uses_mtf:
        return format_enhanced_market_context(snapshot)
    else:
        return format_basic_market_context(snapshot)


def format_user_prompt(snapshot: Dict[str, Any]) -> str:
    """
    Alias for format_market_context for clarity
    """
    return format_market_context(snapshot)


# Example usage for testing
if __name__ == "__main__":
    # Example market snapshot
    example_snapshot = {
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
            'sources': ['binance', 'bybit', 'okx']
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
            'liquidations_24h_usd': 125000000,
            'confidence': 0.82
        }
    }
    
    print("CONSERVATIVE SYSTEM PROMPT:")
    print("=" * 80)
    print(get_system_prompt("conservative"))
    print("\n\n")
    
    print("BASIC MARKET CONTEXT (Binance Fallback):")
    print("=" * 80)
    print(format_basic_market_context(example_snapshot))
