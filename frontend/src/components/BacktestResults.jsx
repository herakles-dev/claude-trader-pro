import React, { useState } from 'react'
import { useQuery } from 'react-query'
import { backtestAPI } from '../services/api'

function BacktestResults() {
  const [isExpanded, setIsExpanded] = useState(true)
  const [period, setPeriod] = useState(30)
  const [showCalibration, setShowCalibration] = useState(false)

  // Fetch backtest summary
  const { data: summaryData, isLoading: summaryLoading } = useQuery(
    ['backtest-summary', period],
    () => backtestAPI.getSummary(period),
    {
      refetchInterval: 300000, // 5 minutes
      select: (response) => response.data?.data || response.data,
    }
  )

  // Fetch accuracy by symbol
  const { data: accuracyData, isLoading: accuracyLoading } = useQuery(
    ['backtest-accuracy', period],
    () => backtestAPI.getAccuracy(period),
    {
      refetchInterval: 300000,
      select: (response) => response.data?.data || response.data,
    }
  )

  // Fetch calibration data
  const { data: calibrationData, isLoading: calibrationLoading } = useQuery(
    ['backtest-calibration', period],
    () => backtestAPI.getCalibration(period),
    {
      enabled: showCalibration,
      refetchInterval: 300000,
      select: (response) => response.data?.data || response.data,
    }
  )

  const summary = summaryData || {}

  // Convert symbols object to array for mapping
  const symbolsObj = accuracyData?.symbols || accuracyData?.by_symbol || {}
  const accuracyBySymbol = Object.entries(symbolsObj).map(([symbol, data]) => ({
    symbol,
    accuracy: data.accuracy_pct || data.accuracy || 0,
    correct: data.correct || 0,
    incorrect: data.incorrect || 0,
    avg_confidence_win: data.avg_confidence_correct || data.avg_confidence_win || 0,
    avg_confidence_loss: data.avg_confidence_incorrect || data.avg_confidence_loss || 0,
  }))

  const calibration = calibrationData?.buckets || calibrationData || []

  const formatPercent = (value) => {
    if (value === null || value === undefined) return '-'
    return `${parseFloat(value).toFixed(1)}%`
  }

  const formatCurrency = (value) => {
    if (value === null || value === undefined) return '-'
    const num = parseFloat(value)
    const sign = num >= 0 ? '+' : ''
    return `${sign}$${Math.abs(num).toFixed(2)}`
  }

  const getColorClass = (value, thresholds = { good: 0, warn: -5 }) => {
    if (value >= thresholds.good) return 'text-green-400'
    if (value >= thresholds.warn) return 'text-yellow-400'
    return 'text-red-400'
  }

  return (
    <div className="card">
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full p-4 flex items-center justify-between hover:bg-gray-800/30 transition-colors"
      >
        <div className="flex items-center space-x-3">
          <span className="text-lg">
            {isExpanded ? '▼' : '▶'}
          </span>
          <h3 className="text-lg font-bold text-white">Backtest Results</h3>
        </div>
        {/* Period Selector */}
        <div className="flex items-center space-x-2" onClick={(e) => e.stopPropagation()}>
          {[30, 60, 90].map((days) => (
            <button
              key={days}
              onClick={() => setPeriod(days)}
              className={`px-2 py-1 text-xs rounded ${
                period === days
                  ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                  : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
              }`}
            >
              {days}d
            </button>
          ))}
        </div>
      </button>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="px-4 pb-4 space-y-4 border-t border-gray-800">
          {/* Summary Metrics Row */}
          <div className="grid grid-cols-4 gap-4 pt-4">
            <div>
              <span className="block text-xs text-gray-500 mb-1">Sharpe Ratio</span>
              <span className={`text-xl font-bold font-mono ${
                (summary.sharpe_ratio || 0) >= 1.5 ? 'text-green-400' :
                (summary.sharpe_ratio || 0) >= 1.0 ? 'text-yellow-400' : 'text-red-400'
              }`}>
                {summaryLoading ? '...' : (summary.sharpe_ratio?.toFixed(2) || '-')}
              </span>
            </div>
            <div>
              <span className="block text-xs text-gray-500 mb-1">Max Drawdown</span>
              <span className={`text-xl font-bold font-mono ${
                (summary.max_drawdown || 0) >= -5 ? 'text-green-400' :
                (summary.max_drawdown || 0) >= -10 ? 'text-yellow-400' : 'text-red-400'
              }`}>
                {summaryLoading ? '...' : formatPercent(summary.max_drawdown)}
              </span>
            </div>
            <div>
              <span className="block text-xs text-gray-500 mb-1">Total P&L</span>
              <span className={`text-xl font-bold font-mono ${
                getColorClass(summary.total_pnl || 0)
              }`}>
                {summaryLoading ? '...' : formatCurrency(summary.total_pnl)}
              </span>
            </div>
            <div>
              <span className="block text-xs text-gray-500 mb-1">Win Rate</span>
              <span className={`text-xl font-bold font-mono ${
                (summary.win_rate || 0) >= 55 ? 'text-green-400' :
                (summary.win_rate || 0) >= 50 ? 'text-yellow-400' : 'text-red-400'
              }`}>
                {summaryLoading ? '...' : formatPercent(summary.win_rate)}
              </span>
            </div>
          </div>

          {/* Accuracy by Symbol Table */}
          <div className="border-t border-gray-800 pt-3">
            <h4 className="text-sm font-medium text-gray-400 mb-3">Accuracy by Symbol</h4>

            {accuracyLoading ? (
              <div className="text-sm text-gray-500">Loading accuracy data...</div>
            ) : accuracyBySymbol.length === 0 ? (
              <div className="text-sm text-gray-500">No accuracy data available</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-gray-500 border-b border-gray-800">
                      <th className="pb-2 font-medium">Symbol</th>
                      <th className="pb-2 font-medium text-center">Accuracy</th>
                      <th className="pb-2 font-medium text-center">Correct</th>
                      <th className="pb-2 font-medium text-center">Incorrect</th>
                      <th className="pb-2 font-medium text-right">Avg Conf (W/L)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {accuracyBySymbol.map((row, idx) => (
                      <tr key={row.symbol || idx} className="border-b border-gray-800/50">
                        <td className="py-2 text-white font-medium">{row.symbol}</td>
                        <td className="py-2 text-center">
                          <span className={`font-mono ${
                            (row.accuracy || 0) >= 55 ? 'text-green-400' :
                            (row.accuracy || 0) >= 50 ? 'text-yellow-400' : 'text-red-400'
                          }`}>
                            {formatPercent(row.accuracy)}
                          </span>
                        </td>
                        <td className="py-2 text-center text-green-400 font-mono">
                          {row.correct || 0}
                        </td>
                        <td className="py-2 text-center text-red-400 font-mono">
                          {row.incorrect || 0}
                        </td>
                        <td className="py-2 text-right font-mono text-xs">
                          <span className="text-green-400">
                            {formatPercent(row.avg_confidence_win)}
                          </span>
                          <span className="text-gray-500"> / </span>
                          <span className="text-red-400">
                            {formatPercent(row.avg_confidence_loss)}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Calibration Section (Collapsible) */}
          <div className="border-t border-gray-800 pt-3">
            <button
              onClick={() => setShowCalibration(!showCalibration)}
              className="flex items-center space-x-2 text-sm text-gray-400 hover:text-white"
            >
              <span>{showCalibration ? '▼' : '▶'}</span>
              <span>Confidence Calibration</span>
            </button>

            {showCalibration && (
              <div className="mt-3">
                {calibrationLoading ? (
                  <div className="text-sm text-gray-500">Loading calibration data...</div>
                ) : calibration.length === 0 ? (
                  <div className="text-sm text-gray-500">No calibration data available</div>
                ) : (
                  <div className="grid grid-cols-5 gap-2">
                    {calibration.map((bucket, idx) => {
                      const range = bucket.confidence_range || bucket.bucket || `${idx * 20}-${(idx + 1) * 20}`
                      const actual = bucket.actual_accuracy || bucket.accuracy || 0
                      const count = bucket.count || bucket.predictions || 0
                      const isCalibrated = Math.abs(actual - (50 + idx * 10)) < 10

                      return (
                        <div
                          key={idx}
                          className={`p-2 rounded text-center ${
                            isCalibrated ? 'bg-green-500/10 border border-green-500/20' :
                            'bg-red-500/10 border border-red-500/20'
                          }`}
                        >
                          <div className="text-xs text-gray-500">{range}%</div>
                          <div className={`text-lg font-bold font-mono ${
                            isCalibrated ? 'text-green-400' : 'text-red-400'
                          }`}>
                            {formatPercent(actual)}
                          </div>
                          <div className="text-xs text-gray-600">n={count}</div>
                        </div>
                      )
                    })}
                  </div>
                )}
                <p className="text-xs text-gray-500 mt-2">
                  Green = well-calibrated (predicted confidence matches actual accuracy)
                </p>
              </div>
            )}
          </div>

          {/* Summary Footer */}
          <div className="flex items-center justify-between text-xs text-gray-500 pt-2 border-t border-gray-800">
            <span>
              Period: {period} days
            </span>
            <span>
              Total Predictions: {summary.total_predictions || 0}
            </span>
          </div>
        </div>
      )}
    </div>
  )
}

export default BacktestResults
