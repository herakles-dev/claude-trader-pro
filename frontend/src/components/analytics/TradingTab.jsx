import React, { useState } from 'react'
import { useSignalPerformance, useDailySignalPerformance } from '../../hooks/useSignalPerformance'
import {
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'

const COLORS = {
  primary: '#3b82f6',
  success: '#22c55e',
  danger: '#ef4444',
  warning: '#f59e0b',
  purple: '#a855f7',
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload || !payload.length) return null
  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-3 shadow-xl">
      <p className="text-sm text-white font-medium mb-2">{label}</p>
      {payload.map((entry, index) => (
        <p key={index} className="text-sm" style={{ color: entry.color }}>
          {entry.name}: {typeof entry.value === 'number'
            ? entry.name.includes('P&L') || entry.name.includes('PnL')
              ? `$${entry.value.toFixed(2)}`
              : entry.value
            : entry.value}
        </p>
      ))}
    </div>
  )
}

function TradingTab({ timeRange }) {
  const [symbol] = useState('BTC/USDT')
  const days = timeRange === '7d' ? 7 : timeRange === '30d' ? 30 : timeRange === '90d' ? 90 : 365

  const { data: performance, isLoading: perfLoading, isError: perfError } = useSignalPerformance({
    symbol,
    days
  })

  const { data: dailyData, isLoading: dailyLoading, isError: dailyError } = useDailySignalPerformance({
    symbol,
    days
  })

  const isLoading = perfLoading || dailyLoading
  const isError = perfError || dailyError

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="card p-6">
              <div className="skeleton h-4 w-24 mb-2" />
              <div className="skeleton h-8 w-32" />
            </div>
          ))}
        </div>
        <div className="card p-6">
          <div className="skeleton h-6 w-48 mb-4" />
          <div className="skeleton h-64" />
        </div>
      </div>
    )
  }

  if (isError) {
    return (
      <div className="card p-6 text-center">
        <div className="text-red-400 mb-2">Failed to load trading performance data</div>
        <p className="text-gray-500 text-sm">Please try again later</p>
      </div>
    )
  }

  // Transform daily data for chart
  // Backend returns daily_pnl, correct_predictions, profitable_trades
  const chartData = dailyData?.days
    ? dailyData.days.map(day => ({
        date: day.date,
        predictions: day.predictions || 0,
        trades: day.trades || 0,
        pnl: day.daily_pnl || day.pnl || 0,
        accuracy: day.predictions > 0
          ? ((day.correct_predictions || 0) / day.predictions) * 100
          : 0,
      }))
    : []

  // Map backend field names to what the component expects
  // Backend returns *_pct fields as actual percentages (e.g., 62.5 for 62.5%)
  // Convert to decimals for consistent formatting
  const predictionAccuracy = performance?.prediction_accuracy_pct != null
    ? performance.prediction_accuracy_pct / 100
    : performance?.prediction_accuracy
  const winRate = performance?.win_rate_pct != null
    ? performance.win_rate_pct / 100
    : performance?.trade_win_rate
  const signalAlignment = performance?.alignment_pct != null
    ? performance.alignment_pct / 100
    : performance?.signal_alignment

  // Calculate correct_predictions and winning_trades from daily data if not provided
  const correctPredictions = performance?.correct_predictions ||
    (dailyData?.days?.reduce((sum, d) => sum + (d.correct_predictions || 0), 0) || 0)
  const winningTrades = performance?.winning_trades ||
    (dailyData?.days?.reduce((sum, d) => sum + (d.profitable_trades || 0), 0) || 0)

  // Calculate conversion rate (trades / predictions)
  const conversionRate = performance?.conversion_rate != null
    ? performance.conversion_rate
    : (performance?.total_predictions > 0 && performance?.total_trades > 0)
      ? performance.total_trades / performance.total_predictions
      : null

  const formatPnL = (value) => {
    if (value === null || value === undefined) return '$0.00'
    const num = parseFloat(value)
    const sign = num >= 0 ? '+' : '-'
    return `${sign}$${Math.abs(num).toFixed(2)}`
  }

  const pnlColor = (performance?.total_pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'

  return (
    <div className="space-y-6">
      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="stat-card">
          <div className="stat-label">Prediction Accuracy</div>
          <div className="stat-value text-blue-400">
            {predictionAccuracy != null
              ? `${(predictionAccuracy * 100).toFixed(1)}%`
              : '--'}
          </div>
          <div className="text-xs text-gray-500">
            {correctPredictions} / {performance?.total_predictions || 0} correct
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-label">Trade Win Rate</div>
          <div className="stat-value text-green-400">
            {winRate != null
              ? `${(winRate * 100).toFixed(1)}%`
              : '--'}
          </div>
          <div className="text-xs text-gray-500">
            {winningTrades} wins / {performance?.total_trades || 0} trades
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-label">Total P&L</div>
          <div className={`stat-value ${pnlColor}`}>
            {formatPnL(performance?.total_pnl)}
          </div>
          <div className="text-xs text-gray-500">
            Paper trading results
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-label">Signal Alignment</div>
          <div className="stat-value text-purple-400">
            {signalAlignment != null
              ? `${(signalAlignment * 100).toFixed(1)}%`
              : '--'}
          </div>
          <div className="text-xs text-gray-500">
            Trades following signals
          </div>
        </div>
      </div>

      {/* Daily Performance Chart */}
      <div className="card p-6">
        <h3 className="text-xl font-bold text-white mb-4">Daily Performance (Predictions vs P&L)</h3>
        {chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height={350}>
            <ComposedChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis
                dataKey="date"
                stroke="#9ca3af"
                style={{ fontSize: '12px' }}
                tickFormatter={(value) => {
                  const date = new Date(value)
                  return `${date.getMonth() + 1}/${date.getDate()}`
                }}
              />
              <YAxis
                yAxisId="left"
                stroke="#9ca3af"
                style={{ fontSize: '12px' }}
              />
              <YAxis
                yAxisId="right"
                orientation="right"
                stroke="#9ca3af"
                style={{ fontSize: '12px' }}
                tickFormatter={(value) => `$${value}`}
              />
              <Tooltip content={<CustomTooltip />} />
              <Legend />
              <Bar
                yAxisId="left"
                dataKey="predictions"
                name="Predictions"
                fill={COLORS.primary}
                radius={[4, 4, 0, 0]}
                opacity={0.8}
              />
              <Bar
                yAxisId="left"
                dataKey="trades"
                name="Trades"
                fill={COLORS.purple}
                radius={[4, 4, 0, 0]}
                opacity={0.8}
              />
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="pnl"
                name="Daily P&L"
                stroke={COLORS.success}
                strokeWidth={2}
                dot={{ fill: COLORS.success, r: 4 }}
              />
            </ComposedChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-64 flex items-center justify-center text-gray-500">
            No daily performance data available
          </div>
        )}
      </div>

      {/* Additional Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card p-6">
          <h4 className="text-sm font-medium text-gray-400 mb-3">Prediction → Trade Conversion</h4>
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-gray-300">Total Predictions</span>
              <span className="font-bold text-white">{performance?.total_predictions || 0}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-300">Signals Sent</span>
              <span className="font-bold text-blue-400">{performance?.total_predictions || 0}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-300">Trades Executed</span>
              <span className="font-bold text-green-400">{performance?.total_trades || 0}</span>
            </div>
            <div className="mt-2 pt-2 border-t border-gray-700">
              <div className="flex justify-between items-center">
                <span className="text-gray-400 text-sm">Conversion Rate</span>
                <span className="font-bold text-purple-400">
                  {conversionRate != null
                    ? `${(conversionRate * 100).toFixed(1)}%`
                    : '--'}
                </span>
              </div>
            </div>
          </div>
        </div>

        <div className="card p-6">
          <h4 className="text-sm font-medium text-gray-400 mb-3">P&L Breakdown</h4>
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-gray-300">Avg Win</span>
              <span className="font-bold text-green-400">
                {formatPnL(performance?.avg_win)}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-300">Avg Loss</span>
              <span className="font-bold text-red-400">
                {formatPnL(performance?.avg_loss)}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-300">Best Trade</span>
              <span className="font-bold text-green-400">
                {formatPnL(performance?.best_trade)}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-300">Worst Trade</span>
              <span className="font-bold text-red-400">
                {formatPnL(performance?.worst_trade)}
              </span>
            </div>
          </div>
        </div>

        <div className="card p-6">
          <h4 className="text-sm font-medium text-gray-400 mb-3">Signal Quality</h4>
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-gray-300">High Confidence Accuracy</span>
              <span className="font-bold text-green-400">
                {performance?.high_confidence_accuracy
                  ? `${(performance.high_confidence_accuracy * 100).toFixed(1)}%`
                  : '--'}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-300">Low Confidence Accuracy</span>
              <span className="font-bold text-yellow-400">
                {performance?.low_confidence_accuracy
                  ? `${(performance.low_confidence_accuracy * 100).toFixed(1)}%`
                  : '--'}
              </span>
            </div>
            <div className="mt-2 pt-2 border-t border-gray-700">
              <div className="flex justify-between items-center">
                <span className="text-gray-400 text-sm">Confidence Threshold</span>
                <span className="text-gray-300">70%</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default TradingTab
