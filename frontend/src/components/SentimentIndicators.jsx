import React from 'react'
import { useAllSentiment } from '../hooks/useSentiment'

function SentimentIndicators() {
  const { sentiment, isLoading, isError } = useAllSentiment()

  if (isLoading) {
    return (
      <div className="card p-6 space-y-4">
        <div className="skeleton h-8 w-48 mb-4" />
        <div className="skeleton h-32" />
      </div>
    )
  }

  if (isError || !sentiment) {
    return (
      <div className="card p-6">
        <div className="text-center text-gray-400 py-8">
          <p className="text-xl mb-2">&#9888;&#65039;</p>
          <p>Unable to load sentiment data</p>
        </div>
      </div>
    )
  }

  const { fear_greed, trend, history, source } = sentiment

  // Fear & Greed color mapping
  const getFearGreedColor = (value) => {
    if (value >= 75) return 'text-green-400'
    if (value >= 55) return 'text-lime-400'
    if (value >= 45) return 'text-yellow-400'
    if (value >= 25) return 'text-orange-400'
    return 'text-red-400'
  }

  const getFearGreedLabel = (value) => {
    if (value >= 75) return 'Extreme Greed'
    if (value >= 55) return 'Greed'
    if (value >= 45) return 'Neutral'
    if (value >= 25) return 'Fear'
    return 'Extreme Fear'
  }

  const getFearGreedBg = (value) => {
    if (value >= 75) return 'bg-green-400'
    if (value >= 55) return 'bg-lime-400'
    if (value >= 45) return 'bg-yellow-400'
    if (value >= 25) return 'bg-orange-400'
    return 'bg-red-400'
  }

  const getTrendIcon = (trend) => {
    if (trend === 'improving') return { icon: '\u2191', color: 'text-green-400', label: 'Improving' }
    if (trend === 'declining') return { icon: '\u2193', color: 'text-red-400', label: 'Declining' }
    return { icon: '\u2192', color: 'text-gray-400', label: 'Stable' }
  }

  const fearGreedValue = fear_greed?.value || 50
  const trendInfo = getTrendIcon(trend)

  return (
    <div className="card p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-xl font-bold text-white">Market Sentiment</h3>
        {source && (
          <span className="text-xs text-gray-500 bg-gray-800 px-2 py-1 rounded">
            {source}
          </span>
        )}
      </div>

      {/* Fear & Greed Index */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-gray-400">
            Fear & Greed Index
          </span>
          <span className="text-xs text-gray-500">
            {fear_greed?.timestamp
              ? `Updated ${new Date(fear_greed.timestamp).toLocaleTimeString()}`
              : 'Live'}
          </span>
        </div>

        {/* Gauge */}
        <div className="relative h-32 bg-gray-900/50 rounded-lg p-4 flex items-center justify-center">
          <div className="text-center">
            <div className={`text-5xl font-bold ${getFearGreedColor(fearGreedValue)}`}>
              {fearGreedValue}
            </div>
            <div className={`text-sm font-medium mt-2 ${getFearGreedColor(fearGreedValue)}`}>
              {fear_greed?.classification || getFearGreedLabel(fearGreedValue)}
            </div>
          </div>
        </div>

        {/* Progress bar */}
        <div className="w-full bg-gray-700 rounded-full h-2 overflow-hidden">
          <div
            className={`h-full ${getFearGreedBg(fearGreedValue)} transition-all duration-500`}
            style={{ width: `${fearGreedValue}%` }}
          />
        </div>

        <div className="flex justify-between text-xs text-gray-500">
          <span>Extreme Fear</span>
          <span>Neutral</span>
          <span>Extreme Greed</span>
        </div>
      </div>

      {/* 7-Day Trend */}
      {trend && (
        <div className="space-y-3 pt-4 border-t border-gray-700">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-gray-400">
              7-Day Trend
            </span>
            <div className={`flex items-center space-x-1 ${trendInfo.color}`}>
              <span className="text-lg">{trendInfo.icon}</span>
              <span className="text-sm font-medium">{trendInfo.label}</span>
            </div>
          </div>

          {/* Mini chart showing history */}
          {history && history.length > 1 && (
            <div className="bg-gray-900/50 rounded-lg p-3">
              <div className="flex items-end justify-between h-16 space-x-1">
                {history.slice(0, 7).reverse().map((day, idx) => {
                  const heightPercent = (day.value / 100) * 100
                  return (
                    <div
                      key={idx}
                      className="flex-1 flex flex-col items-center"
                    >
                      <div
                        className={`w-full rounded-t ${getFearGreedBg(day.value)} transition-all`}
                        style={{ height: `${heightPercent}%`, minHeight: '4px' }}
                        title={`${day.value} - ${day.classification}`}
                      />
                      <span className="text-[10px] text-gray-500 mt-1">
                        {idx === 0 ? 'Today' : idx === 6 ? '7d' : ''}
                      </span>
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Source attribution */}
      <div className="text-center pt-2 border-t border-gray-700">
        <span className="text-xs text-gray-500">
          Live data from Alternative.me
        </span>
      </div>
    </div>
  )
}

export default SentimentIndicators
