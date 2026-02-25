import React, { useEffect, useState } from 'react'
import { useQuery } from 'react-query'
import { useLatestPrediction, useTriggerPrediction } from '../hooks/usePredictions'
import { analyticsAPI, automatedAPI } from '../services/api'
import { CalibrationBadge } from './common'
import { logComponentData, logPredictionData, logAnalyticsData } from '../utils/debugLogger'
import {
  formatConfidence,
  formatRelativeTime,
  getConfidenceColor,
  getDirectionColor,
} from '../utils/formatters'

function PredictionCard({ symbol = 'BTC' }) {
  const { prediction, isLoading, isError } = useLatestPrediction(symbol)
  const { triggerPrediction, isTriggering } = useTriggerPrediction()
  const [showPrompt, setShowPrompt] = useState(false)
  const [promptData, setPromptData] = useState(null)
  const [promptLoading, setPromptLoading] = useState(false)

  // Fetch calibration data to show historical accuracy at confidence level
  const { data: calibration } = useQuery(
    ['analytics-calibration', 30],
    () => analyticsAPI.getCalibration(30),
    {
      staleTime: 300000,
      select: (res) => {
        console.log('%c[PREDICTION CARD DEBUG] Calibration raw:', 'color: #f59e0b', res.data)
        return res.data?.data || res.data
      },
    }
  )

  // Debug logging when data loads
  useEffect(() => {
    if (prediction) {
      logComponentData('PredictionCard', 'prediction', prediction, { symbol })
      logPredictionData('PredictionCard.jsx', [prediction], null)
      console.log('%c[PREDICTION CARD DEBUG] Prediction:', 'color: #22c55e', prediction)
      console.log('%c[PREDICTION CARD DEBUG] Key fields:', 'color: #3b82f6', {
        direction: prediction.direction,
        confidence: prediction.confidence,
        strategy: prediction.strategy,
        created_at: prediction.created_at,
        target_price: prediction.target_price,
        stop_loss: prediction.stop_loss,
        cost_tracking: prediction.cost_tracking,
      })
    }
  }, [prediction, symbol])

  useEffect(() => {
    if (calibration) {
      logAnalyticsData('PredictionCard.jsx', 'calibration', calibration)
      console.log('%c[PREDICTION CARD DEBUG] Calibration:', 'color: #a855f7', calibration)
    }
  }, [calibration])

  const handleTrigger = () => {
    const strategy = localStorage.getItem('trading_strategy') || 'conservative'
    triggerPrediction({ symbol, strategy })
  }

  // Fetch prompt data when user expands the section
  const handleTogglePrompt = async () => {
    if (!showPrompt && !promptData && prediction?.id) {
      setPromptLoading(true)
      try {
        const response = await automatedAPI.getPredictionPrompt(prediction.id)
        setPromptData(response.data?.data || response.data)
      } catch (error) {
        console.error('Failed to fetch prompt:', error)
        setPromptData({ error: 'Failed to load prompt data' })
      } finally {
        setPromptLoading(false)
      }
    }
    setShowPrompt(!showPrompt)
  }

  // Find historical accuracy for current confidence level
  const getHistoricalAccuracy = (confidence) => {
    if (!calibration?.buckets || !confidence) return null
    const confValue = confidence
    // Find the bucket that contains this confidence level
    const bucket = calibration.buckets.find(b => {
      const mid = b.confidence_range?.mid || b.stated_confidence
      return Math.abs(mid - confValue) < 0.1
    })
    return bucket?.actual_accuracy
  }

  if (isLoading) {
    return (
      <div className="card p-6 space-y-4">
        <div className="skeleton h-8 w-48 mb-4" />
        <div className="skeleton h-32" />
        <div className="skeleton h-20" />
      </div>
    )
  }

  if (isError || !prediction) {
    return (
      <div className="card p-6">
        <h3 className="text-xl font-bold text-white mb-4">Latest Prediction</h3>
        <div className="text-center py-8 space-y-4">
          <p className="text-gray-400">No prediction available</p>
          <button
            onClick={handleTrigger}
            disabled={isTriggering}
            className="btn-primary"
          >
            {isTriggering ? 'Generating...' : 'Generate Prediction'}
          </button>
        </div>
      </div>
    )
  }

  const {
    direction,
    confidence,
    reasoning,
    strategy,
    created_at,
    target_price,
    stop_loss,
    cost_tracking,
    claude_model,
  } = prediction

  const directionColor = getDirectionColor(direction)
  const confidenceColor = getConfidenceColor(confidence)
  const directionIcon = direction?.toLowerCase() === 'up' ? '&#x25B2;' : '&#x25BC;'

  // Get historical accuracy for this confidence level
  const historicalAccuracy = getHistoricalAccuracy(confidence)

  // Extract data points from reasoning for display
  const extractDataPoint = (text, pattern) => {
    const match = text?.match(pattern)
    return match ? match[1] : null
  }

  const priceChange = extractDataPoint(reasoning, /(-?\d+\.?\d*)%/)
  const fearGreed = extractDataPoint(reasoning, /Fear & Greed[^(]*\(([^)]+)\)/)
  const sentimentMention = reasoning?.toLowerCase().includes('reddit') || reasoning?.toLowerCase().includes('sentiment')

  return (
    <div className="card p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-xl font-bold text-white">Latest Prediction</h3>
        <button
          onClick={handleTrigger}
          disabled={isTriggering}
          className="btn-secondary text-sm"
        >
          {isTriggering ? 'Generating...' : 'Refresh'}
        </button>
      </div>

      {/* Direction & Confidence */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-gray-900/50 rounded-lg p-4 text-center">
          <div className="text-sm text-gray-400 mb-2">Direction</div>
          <div className={`text-3xl font-bold ${directionColor}`}>
            <span dangerouslySetInnerHTML={{ __html: directionIcon }} /> {direction?.toUpperCase()}
          </div>
        </div>

        <div className="bg-gray-900/50 rounded-lg p-4 text-center">
          <div className="text-sm text-gray-400 mb-2">Confidence</div>
          <div className={`text-3xl font-bold ${confidenceColor}`}>
            {formatConfidence(confidence)}
          </div>
          {/* Historical accuracy and calibration badge */}
          {historicalAccuracy !== null && (
            <div className="mt-2 space-y-1">
              <div className="text-xs text-gray-500">
                Historical: {(historicalAccuracy * 100).toFixed(0)}%
              </div>
              <CalibrationBadge stated={confidence} actual={historicalAccuracy} />
            </div>
          )}
        </div>
      </div>

      {/* Target & Stop Loss */}
      {(target_price || stop_loss) && (
        <div className="grid grid-cols-2 gap-4">
          {target_price && (
            <div className="bg-green-900/20 border border-green-700 rounded-lg p-3">
              <div className="text-xs text-gray-400 mb-1">Target Price</div>
              <div className="text-lg font-semibold text-green-400 font-mono">
                ${target_price.toFixed(2)}
              </div>
            </div>
          )}

          {stop_loss && (
            <div className="bg-red-900/20 border border-red-700 rounded-lg p-3">
              <div className="text-xs text-gray-400 mb-1">Stop Loss</div>
              <div className="text-lg font-semibold text-red-400 font-mono">
                ${stop_loss.toFixed(2)}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Data Sources */}
      <div className="space-y-2">
        <div className="text-sm font-medium text-gray-400">Data Sources Used</div>
        <div className="bg-gray-900/50 rounded-lg p-3 space-y-2">
          <div className="grid grid-cols-2 gap-2 text-xs">
            {priceChange && (
              <div className="flex items-center justify-between bg-gray-800/50 rounded px-2 py-1">
                <span className="text-gray-400">24h Price:</span>
                <span className={priceChange.startsWith('-') ? 'text-red-400' : 'text-green-400'}>
                  {priceChange}%
                </span>
              </div>
            )}
            {fearGreed && (
              <div className="flex items-center justify-between bg-gray-800/50 rounded px-2 py-1">
                <span className="text-gray-400">Fear & Greed:</span>
                <span className="text-yellow-400">{fearGreed}</span>
              </div>
            )}
            {sentimentMention && (
              <div className="flex items-center justify-between bg-gray-800/50 rounded px-2 py-1">
                <span className="text-gray-400">Sentiment:</span>
                <span className="text-purple-400">Analyzed</span>
              </div>
            )}
          </div>
          <div className="text-xs text-gray-500 mt-2 pt-2 border-t border-gray-700">
            Sources: Binance, CoinGecko, Alternative.me, Reddit, Derivatives Data
          </div>
        </div>
      </div>

      {/* Reasoning */}
      <div className="space-y-2">
        <div className="text-sm font-medium text-gray-400">Claude&apos;s Analysis</div>
        <div className="bg-gray-900/50 rounded-lg p-4">
          <p className="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">
            {reasoning || 'No reasoning provided'}
          </p>
        </div>
      </div>

      {/* AI Prompt Section - Collapsible */}
      <div className="space-y-2">
        <button
          onClick={handleTogglePrompt}
          className="flex items-center justify-between w-full text-sm font-medium text-gray-400 hover:text-gray-300 transition-colors"
        >
          <span>View AI Prompt</span>
          <span className={`transform transition-transform ${showPrompt ? 'rotate-180' : ''}`}>
            &#9660;
          </span>
        </button>

        {showPrompt && (
          <div className="bg-gray-900/50 rounded-lg p-4 space-y-4">
            {promptLoading ? (
              <div className="text-sm text-gray-400 animate-pulse">Loading prompt...</div>
            ) : promptData?.error ? (
              <div className="text-sm text-red-400">{promptData.error}</div>
            ) : promptData ? (
              <>
                {/* System Prompt */}
                <div className="space-y-2">
                  <div className="text-xs font-semibold text-blue-400 uppercase tracking-wide">
                    System Prompt ({promptData.strategy})
                  </div>
                  <div className="bg-gray-800/50 rounded p-3 max-h-48 overflow-y-auto">
                    <pre className="text-xs text-gray-300 whitespace-pre-wrap font-mono">
                      {promptData.system_prompt || 'No system prompt available'}
                    </pre>
                  </div>
                </div>

                {/* User Prompt (Market Context) */}
                <div className="space-y-2">
                  <div className="text-xs font-semibold text-green-400 uppercase tracking-wide">
                    Market Context Sent to AI
                  </div>
                  <div className="bg-gray-800/50 rounded p-3 max-h-64 overflow-y-auto">
                    <pre className="text-xs text-gray-300 whitespace-pre-wrap font-mono">
                      {promptData.user_prompt || 'No market context available'}
                    </pre>
                  </div>
                </div>

                {/* Prompt Metadata */}
                <div className="flex items-center justify-between text-xs text-gray-500 pt-2 border-t border-gray-700">
                  <span>Prompt v{promptData.prompt_version || '?'}</span>
                  <span>Model: {promptData.ai_model || 'Unknown'}</span>
                </div>
              </>
            ) : (
              <div className="text-sm text-gray-400">No prompt data available</div>
            )}
          </div>
        )}
      </div>

      {/* Metadata */}
      <div className="flex items-center justify-between text-xs text-gray-500 pt-4 border-t border-gray-700">
        <div className="flex items-center space-x-4">
          <span className="badge badge-info">{strategy}</span>
          <span>{formatRelativeTime(created_at)}</span>
        </div>
        {cost_tracking && (
          <div className="flex items-center space-x-3">
            <span title={`Model: ${claude_model || 'Unknown'}`}>
              {claude_model?.includes('haiku') ? 'Haiku' : claude_model?.includes('sonnet') ? 'Sonnet' : 'Claude'}
            </span>
            <span title={`${cost_tracking.input_tokens || 0} input + ${cost_tracking.output_tokens || 0} output tokens`}>
              ${(cost_tracking.total_cost_usd || 0).toFixed(4)}
            </span>
            <span title="API Latency">
              {(cost_tracking.api_latency_ms || 0) / 1000}s
            </span>
          </div>
        )}
      </div>
    </div>
  )
}

export default PredictionCard
