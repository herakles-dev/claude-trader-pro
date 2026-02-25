import React, { useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from 'react-query'
import { automatedAPI, analyticsAPI } from '../services/api'
import { formatRelativeTime, formatConfidence, getDirectionColor, getConfidenceColor } from '../utils/formatters'
import { MarketRegimeBadge, PatternIndicator } from './common'
import { logComponentData, logAnalyticsData, logPredictionData } from '../utils/debugLogger'
import toast from 'react-hot-toast'

function AutomatedCycle() {
  const queryClient = useQueryClient()

  // Fetch current cycle
  const { data: cycle, isLoading: cycleLoading, isError: cycleError } = useQuery(
    'automated-cycle-current',
    () => automatedAPI.getCurrentCycle(),
    {
      refetchInterval: 60000, // Refresh every minute
      select: (res) => {
        console.log('%c[AUTOMATED CYCLE DEBUG] Cycle raw response:', 'color: #f59e0b', res.data)
        return res.data?.data
      },
      retry: 2,
    }
  )

  // Fetch scheduler status
  const { data: status, isLoading: statusLoading } = useQuery(
    'automated-status',
    () => automatedAPI.getStatus(),
    {
      refetchInterval: 30000,
      select: (res) => {
        console.log('%c[AUTOMATED CYCLE DEBUG] Status raw response:', 'color: #f59e0b', res.data)
        return res.data?.data
      },
      retry: 2,
    }
  )

  // Fetch conditions analytics for market regime
  const { data: conditions } = useQuery(
    ['analytics-conditions', 30],
    () => analyticsAPI.getConditions(30),
    {
      staleTime: 300000,
      select: (res) => {
        console.log('%c[AUTOMATED CYCLE DEBUG] Conditions raw response:', 'color: #f59e0b', res.data)
        return res.data?.data || res.data
      },
    }
  )

  // Fetch pattern analytics for current pattern info
  const { data: patterns } = useQuery(
    ['analytics-patterns', 5],
    () => analyticsAPI.getPatterns(5),
    {
      staleTime: 300000,
      select: (res) => {
        console.log('%c[AUTOMATED CYCLE DEBUG] Patterns raw response:', 'color: #f59e0b', res.data)
        return res.data?.data || res.data
      },
    }
  )

  // Debug logging when data loads
  useEffect(() => {
    if (cycle) {
      logComponentData('AutomatedCycle', 'cycle', cycle)
      console.log('%c[AUTOMATED CYCLE DEBUG] Processed cycle:', 'color: #22c55e', cycle)
      console.log('%c[AUTOMATED CYCLE DEBUG] Prediction:', 'color: #3b82f6', cycle.prediction)
      console.log('%c[AUTOMATED CYCLE DEBUG] Cycle info:', 'color: #a855f7', cycle.cycle_info)
    }
  }, [cycle])

  useEffect(() => {
    if (status) {
      logComponentData('AutomatedCycle', 'status', status)
      console.log('%c[AUTOMATED CYCLE DEBUG] Scheduler status:', 'color: #22c55e', status)
    }
  }, [status])

  useEffect(() => {
    if (conditions) {
      logAnalyticsData('AutomatedCycle.jsx', 'conditions', conditions)
      console.log('%c[AUTOMATED CYCLE DEBUG] Conditions:', 'color: #22c55e', conditions)
      console.log('%c[AUTOMATED CYCLE DEBUG] Market regimes:', 'color: #3b82f6', conditions.market_regimes)
      console.log('%c[AUTOMATED CYCLE DEBUG] Current regime:', 'color: #a855f7', conditions.current_regime)
    }
  }, [conditions])

  useEffect(() => {
    if (patterns) {
      logAnalyticsData('AutomatedCycle.jsx', 'patterns', patterns)
      console.log('%c[AUTOMATED CYCLE DEBUG] Patterns:', 'color: #22c55e', patterns)
    }
  }, [patterns])

  // Manual trigger mutation
  const triggerMutation = useMutation(
    () => automatedAPI.triggerNow(),
    {
      onSuccess: () => {
        toast.success('Manual prediction triggered')
        queryClient.invalidateQueries('automated-cycle-current')
        queryClient.invalidateQueries('automated-status')
        queryClient.invalidateQueries(['prediction-latest'])
        queryClient.invalidateQueries(['predictions'])
      },
      onError: (error) => {
        toast.error(`Failed to trigger prediction: ${error.message}`)
      },
    }
  )

  // Calculate time until next cycle
  const getTimeUntilNext = () => {
    if (!status?.next_run) return null
    const nextRun = new Date(status.next_run)
    const now = new Date()
    const diff = nextRun - now

    if (diff <= 0) return 'Starting soon...'

    const hours = Math.floor(diff / (1000 * 60 * 60))
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60))

    if (hours > 0) {
      return `${hours}h ${minutes}m`
    }
    return `${minutes}m`
  }

  // Get regime accuracy (market_regimes is now an array, not an object)
  const getRegimeAccuracy = (regime) => {
    if (!conditions?.market_regimes || !Array.isArray(conditions.market_regimes) || !regime) return null
    const normalizedRegime = regime.toLowerCase().replace(/\s+/g, '_')
    const found = conditions.market_regimes.find(r => r.regime === normalizedRegime)
    return found ? (found.accuracy_pct || 0) / 100 : null
  }

  // Get best performing regime from array
  const getBestRegime = () => {
    if (!conditions?.market_regimes || !Array.isArray(conditions.market_regimes) || conditions.market_regimes.length === 0) return null
    const sorted = [...conditions.market_regimes].sort((a, b) => (b.accuracy_pct || 0) - (a.accuracy_pct || 0))
    return sorted[0]?.regime?.replace(/_/g, ' ')
  }

  // Get top pattern
  const getTopPattern = () => {
    if (!patterns?.patterns || patterns.patterns.length === 0) return null
    return patterns.patterns[0]
  }

  // Loading state
  if (cycleLoading || statusLoading) {
    return (
      <div className="card p-6">
        <div className="skeleton h-8 w-48 mb-4" />
        <div className="skeleton h-24 mb-4" />
        <div className="skeleton h-16" />
      </div>
    )
  }

  // Error or no cycle state
  if (cycleError || !cycle) {
    return (
      <div className="card p-6">
        <h3 className="text-xl font-bold text-white mb-4">4-Hour Cycle</h3>
        <div className="text-center py-6 space-y-4">
          <div className="text-gray-400">
            {cycleError ? 'Unable to fetch cycle data' : 'No active cycle'}
          </div>
          <button
            onClick={() => triggerMutation.mutate()}
            disabled={triggerMutation.isLoading}
            className="btn-primary"
          >
            {triggerMutation.isLoading ? 'Triggering...' : 'Trigger Now'}
          </button>
        </div>
      </div>
    )
  }

  const { prediction, cycle_info } = cycle
  const directionColor = getDirectionColor(prediction?.direction)
  const confidenceColor = getConfidenceColor(prediction?.confidence)
  const directionIcon = prediction?.direction?.toLowerCase() === 'up' ? '&#x25B2;' : '&#x25BC;'

  const currentRegime = conditions?.current_regime
  const regimeAccuracy = getRegimeAccuracy(currentRegime)
  const topPattern = getTopPattern()

  return (
    <div className="card p-6 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-xl font-bold text-white">4-Hour Cycle</h3>
        <div className="flex items-center space-x-2">
          <span
            className={`w-2 h-2 rounded-full ${
              status?.is_running ? 'bg-green-400 animate-pulse' : 'bg-gray-400'
            }`}
          />
          <span className="text-xs text-gray-400">
            {status?.is_running ? 'Active' : 'Paused'}
          </span>
        </div>
      </div>

      {/* Cycle Progress */}
      {cycle_info && (
        <div className="bg-gray-900/50 rounded-lg p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-gray-400">Cycle Progress</span>
            <span className="text-sm text-gray-300 font-mono">
              {cycle_info.predictions_count || 0} / {cycle_info.total_predictions || 6} predictions
            </span>
          </div>
          <div className="w-full bg-gray-700 rounded-full h-2">
            <div
              className="bg-blue-500 h-2 rounded-full transition-all duration-500"
              style={{
                width: `${((cycle_info.predictions_count || 0) / (cycle_info.total_predictions || 6)) * 100}%`,
              }}
            />
          </div>
          <div className="flex items-center justify-between mt-2 text-xs text-gray-500">
            <span>Started {formatRelativeTime(cycle_info.started_at)}</span>
            <span>Next: {getTimeUntilNext() || 'Unknown'}</span>
          </div>
        </div>
      )}

      {/* Latest Prediction Summary */}
      {prediction && (
        <div className="space-y-3">
          <div className="text-sm font-medium text-gray-400">Latest Decision</div>
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-gray-900/50 rounded-lg p-3 text-center">
              <div className="text-xs text-gray-500 mb-1">Direction</div>
              <div className={`text-xl font-bold ${directionColor}`}>
                <span dangerouslySetInnerHTML={{ __html: directionIcon }} />{' '}
                {prediction.direction?.toUpperCase()}
              </div>
            </div>
            <div className="bg-gray-900/50 rounded-lg p-3 text-center">
              <div className="text-xs text-gray-500 mb-1">Confidence</div>
              <div className={`text-xl font-bold ${confidenceColor}`}>
                {formatConfidence(prediction.confidence)}
              </div>
            </div>
          </div>

          {/* Targets */}
          {(prediction.target_price || prediction.stop_loss) && (
            <div className="grid grid-cols-2 gap-3">
              {prediction.target_price && (
                <div className="bg-green-900/20 border border-green-700/50 rounded-lg p-2 text-center">
                  <div className="text-xs text-gray-500">Target</div>
                  <div className="text-sm font-semibold text-green-400 font-mono">
                    ${prediction.target_price.toLocaleString()}
                  </div>
                </div>
              )}
              {prediction.stop_loss && (
                <div className="bg-red-900/20 border border-red-700/50 rounded-lg p-2 text-center">
                  <div className="text-xs text-gray-500">Stop Loss</div>
                  <div className="text-sm font-semibold text-red-400 font-mono">
                    ${prediction.stop_loss.toLocaleString()}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Market Context Section */}
      {(currentRegime || topPattern) && (
        <div className="pt-3 border-t border-gray-700 space-y-3">
          {/* Current Pattern */}
          {topPattern && (
            <div>
              <div className="text-xs text-gray-500 mb-1">Top Pattern</div>
              <PatternIndicator
                name={topPattern.pattern_name}
                grade={topPattern.grade}
                accuracy={topPattern.accuracy_rate}
                compact={false}
              />
            </div>
          )}

          {/* Market Regime */}
          {currentRegime && (
            <div>
              <div className="text-xs text-gray-500 mb-1">Market Regime</div>
              <MarketRegimeBadge
                regime={currentRegime}
                accuracy={regimeAccuracy}
                showAccuracy={true}
              />
            </div>
          )}
        </div>
      )}

      {/* Actions */}
      <div className="pt-3 border-t border-gray-700 flex items-center justify-between">
        <div className="text-xs text-gray-500">
          {status?.total_cycles || 0} cycles completed
        </div>
        <button
          onClick={() => triggerMutation.mutate()}
          disabled={triggerMutation.isLoading}
          className="btn-secondary text-xs"
        >
          {triggerMutation.isLoading ? 'Triggering...' : 'Manual Trigger'}
        </button>
      </div>
    </div>
  )
}

export default AutomatedCycle
