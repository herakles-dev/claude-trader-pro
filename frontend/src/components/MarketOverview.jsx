import React, { useEffect } from 'react'
import { useQuery } from 'react-query'
import { useMarketData } from '../hooks/useMarketData'
import { analyticsAPI } from '../services/api'
import { MarketRegimeBadge } from './common'
import { logComponentData, logMarketData, logAnalyticsData } from '../utils/debugLogger'
import {
  formatPrice,
  formatPercentage,
  formatVolume,
  formatLargeNumber,
  getPercentageColor,
} from '../utils/formatters'

const volatilityConfig = {
  low: { color: 'text-green-400', bg: 'bg-green-900/30 border-green-700' },
  medium: { color: 'text-yellow-400', bg: 'bg-yellow-900/30 border-yellow-700' },
  high: { color: 'text-red-400', bg: 'bg-red-900/30 border-red-700' },
  extreme: { color: 'text-purple-400', bg: 'bg-purple-900/30 border-purple-700' },
}

function MarketOverview({ symbol = 'BTC' }) {
  const { marketData, isLoading, isError } = useMarketData(symbol)

  // Fetch conditions analytics for market regime
  const { data: conditions } = useQuery(
    ['analytics-conditions', 30],
    () => analyticsAPI.getConditions(30),
    {
      staleTime: 300000,
      select: (res) => {
        console.log('%c[MARKET OVERVIEW DEBUG] Conditions raw:', 'color: #f59e0b', res.data)
        return res.data?.data || res.data
      },
    }
  )

  // Debug logging when data loads
  useEffect(() => {
    if (marketData) {
      logComponentData('MarketOverview', 'marketData', marketData, { symbol })
      logMarketData('MarketOverview.jsx', { [symbol]: marketData })
      console.log('%c[MARKET OVERVIEW DEBUG] Market data:', 'color: #22c55e', marketData)
      console.log('%c[MARKET OVERVIEW DEBUG] Key fields:', 'color: #3b82f6', {
        current_price: marketData.current_price,
        price_change_24h: marketData.price_change_24h,
        price_change_percentage_24h: marketData.price_change_percentage_24h,
        high_24h: marketData.high_24h,
        low_24h: marketData.low_24h,
        total_volume: marketData.total_volume,
        market_cap: marketData.market_cap,
      })
    }
  }, [marketData, symbol])

  useEffect(() => {
    if (conditions) {
      logAnalyticsData('MarketOverview.jsx', 'conditions', conditions)
      console.log('%c[MARKET OVERVIEW DEBUG] Conditions:', 'color: #a855f7', conditions)
    }
  }, [conditions])

  if (isLoading) {
    return (
      <div className="card p-6 space-y-4">
        <div className="skeleton h-8 w-32 mb-4" />
        <div className="skeleton h-12 w-48" />
        <div className="grid grid-cols-2 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="skeleton h-16" />
          ))}
        </div>
      </div>
    )
  }

  if (isError || !marketData) {
    return (
      <div className="card p-6">
        <div className="text-center text-gray-400 py-8">
          <p className="text-xl mb-2">Unable to load market data</p>
        </div>
      </div>
    )
  }

  const {
    current_price,
    price_change_24h,
    price_change_percentage_24h,
    high_24h,
    low_24h,
    total_volume,
    market_cap,
  } = marketData

  const priceChangeColor = getPercentageColor(price_change_percentage_24h)

  // Get regime accuracy (market_regimes is an array, not an object)
  const getRegimeAccuracy = (regime) => {
    if (!conditions?.market_regimes || !Array.isArray(conditions.market_regimes) || !regime) return null
    const normalizedRegime = regime.toLowerCase().replace(/\s+/g, '_')
    const found = conditions.market_regimes.find(r => r.regime === normalizedRegime)
    return found ? (found.accuracy_pct || 0) / 100 : null
  }

  const currentRegime = conditions?.current_regime
  const regimeAccuracy = getRegimeAccuracy(currentRegime)
  const currentVolatility = conditions?.current_volatility
  const volConfig = volatilityConfig[currentVolatility?.toLowerCase()] || volatilityConfig.medium

  // Get first recommendation if available
  const topRecommendation = conditions?.recommendations?.[0]

  return (
    <div className="card p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <h2 className="text-2xl font-bold text-white">{symbol}/USDT</h2>
          <span className="text-sm text-gray-400 bg-gray-700 px-2 py-1 rounded">
            Spot
          </span>
        </div>
      </div>

      {/* Current Price */}
      <div>
        <div className="flex items-baseline space-x-4">
          <div className="text-4xl font-bold text-white font-mono">
            ${formatPrice(current_price)}
          </div>
          <div className={`text-xl font-semibold ${priceChangeColor}`}>
            {formatPercentage(price_change_percentage_24h)}
          </div>
        </div>
        <div className={`text-sm font-medium mt-1 ${priceChangeColor}`}>
          {price_change_24h >= 0 ? '+' : ''}${formatPrice(price_change_24h)} (24h)
        </div>
      </div>

      {/* Market Context */}
      {(currentRegime || currentVolatility) && (
        <div className="bg-gray-900/30 rounded-lg p-3 space-y-2">
          <div className="flex items-center justify-between flex-wrap gap-2">
            {currentRegime && (
              <div className="flex items-center space-x-2">
                <span className="text-xs text-gray-500">Regime:</span>
                <MarketRegimeBadge
                  regime={currentRegime}
                  accuracy={regimeAccuracy}
                  showAccuracy={true}
                />
              </div>
            )}
            {currentVolatility && (
              <div className="flex items-center space-x-2">
                <span className="text-xs text-gray-500">Volatility:</span>
                <span className={`px-2 py-0.5 rounded text-xs font-medium border ${volConfig.bg} ${volConfig.color}`}>
                  {currentVolatility.charAt(0).toUpperCase() + currentVolatility.slice(1)}
                </span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Stats Grid */}
      <div className="grid grid-cols-2 gap-4">
        {/* 24h High */}
        <div className="bg-gray-900/50 rounded-lg p-3">
          <div className="text-xs text-gray-400 mb-1">24h High</div>
          <div className="text-lg font-semibold text-green-400 font-mono">
            ${formatPrice(high_24h)}
          </div>
        </div>

        {/* 24h Low */}
        <div className="bg-gray-900/50 rounded-lg p-3">
          <div className="text-xs text-gray-400 mb-1">24h Low</div>
          <div className="text-lg font-semibold text-red-400 font-mono">
            ${formatPrice(low_24h)}
          </div>
        </div>

        {/* Volume */}
        <div className="bg-gray-900/50 rounded-lg p-3">
          <div className="text-xs text-gray-400 mb-1">24h Volume</div>
          <div className="text-lg font-semibold text-blue-400 font-mono">
            ${formatVolume(total_volume)}
          </div>
        </div>

        {/* Market Cap */}
        <div className="bg-gray-900/50 rounded-lg p-3">
          <div className="text-xs text-gray-400 mb-1">Market Cap</div>
          <div className="text-lg font-semibold text-purple-400 font-mono">
            ${formatLargeNumber(market_cap)}
          </div>
        </div>
      </div>

      {/* AI Recommendation */}
      {topRecommendation && (
        <div className="bg-blue-900/20 border border-blue-700/50 rounded-lg p-3">
          <div className="flex items-start space-x-2">
            <span className="text-blue-400 text-sm mt-0.5">AI:</span>
            <p className="text-sm text-gray-300">{topRecommendation}</p>
          </div>
        </div>
      )}

      {/* Last Update */}
      <div className="text-xs text-gray-500 text-center">
        Last updated: {new Date().toLocaleTimeString()}
      </div>
    </div>
  )
}

export default MarketOverview
