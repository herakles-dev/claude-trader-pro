import React, { useEffect } from 'react'
import { useQuery } from 'react-query'
import { tradesAPI, signalsAPI } from '../services/api'
import { MiniSparkline } from './common'
import { logComponentData, logTradeData } from '../utils/debugLogger'

function TradePerformance({ symbol = null }) {
  const { data: stats, isLoading, error } = useQuery(
    ['trade-statistics', symbol],
    () => tradesAPI.getStatistics({ symbol, days: 30 }),
    {
      refetchInterval: 60000, // 1 minute
      // API returns { success: true, data: {...stats} }
      select: (response) => {
        console.log('%c[TRADE PERF DEBUG] Stats raw response:', 'color: #f59e0b', response.data)
        return response.data?.data || response.data
      },
    }
  )

  const { data: recentTrades } = useQuery(
    ['recent-trades', symbol],
    () => tradesAPI.getRecent({ symbol, limit: 5 }),
    {
      refetchInterval: 60000,
      // API returns { success: true, data: { trades: [...], total_available } }
      select: (response) => {
        console.log('%c[TRADE PERF DEBUG] Recent trades raw response:', 'color: #f59e0b', response.data)
        return response.data?.data?.trades || []
      },
    }
  )

  // Fetch signal performance for alignment data
  const { data: signalPerf } = useQuery(
    ['signals-performance', symbol || 'BTC/USDT', 30],
    () => signalsAPI.getPerformance({ symbol: symbol || 'BTC/USDT', days: 30 }),
    {
      refetchInterval: 60000,
      select: (response) => {
        console.log('%c[TRADE PERF DEBUG] Signal performance raw response:', 'color: #f59e0b', response.data)
        return response.data?.data || response.data
      },
    }
  )

  // Fetch concentration risk for warning banner
  const { data: concentration } = useQuery(
    ['concentration-risk'],
    () => tradesAPI.getConcentrationRisk(),
    {
      refetchInterval: 60000,
      select: (response) => response.data?.data || response.data,
    }
  )

  // Debug logging when data loads
  useEffect(() => {
    if (stats) {
      logComponentData('TradePerformance', 'stats', stats, { symbol })
      logTradeData('TradePerformance.jsx - Stats', [], stats)
      console.log('%c[TRADE PERF DEBUG] Processed stats:', 'color: #22c55e', stats)
    }
  }, [stats, symbol])

  useEffect(() => {
    if (recentTrades) {
      logTradeData('TradePerformance.jsx - Recent', recentTrades, null)
      console.log('%c[TRADE PERF DEBUG] Recent trades:', 'color: #3b82f6', recentTrades)
    }
  }, [recentTrades])

  useEffect(() => {
    if (signalPerf) {
      logComponentData('TradePerformance', 'signalPerf', signalPerf, { symbol })
      console.log('%c[TRADE PERF DEBUG] Signal performance:', 'color: #a855f7', signalPerf)
    }
  }, [signalPerf, symbol])

  const formatPnL = (value) => {
    if (value === null || value === undefined) return '$0.00'
    const num = parseFloat(value)
    const sign = num >= 0 ? '+' : '-'
    return `${sign}$${Math.abs(num).toFixed(2)}`
  }

  if (isLoading) {
    return (
      <div className="card p-6">
        <div className="skeleton h-8 w-40 mb-4" />
        <div className="skeleton h-16 mb-4" />
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="skeleton h-10" />
          ))}
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="card p-6">
        <h3 className="text-xl font-bold text-white mb-2">Paper Trading</h3>
        <p className="text-red-400 text-sm">Failed to load trade data</p>
      </div>
    )
  }

  const hasTrades = stats?.total_trades > 0
  const pnlColor = stats?.total_pnl >= 0 ? 'text-green-400' : 'text-red-400'
  const winRateColor = stats?.win_rate >= 50 ? 'text-green-400' : stats?.win_rate >= 30 ? 'text-yellow-400' : 'text-red-400'

  // Generate sparkline data from recent trades (for P&L trend)
  const sparklineData = recentTrades?.slice(0, 7).reverse().map(t => t.pnl || 0) || []

  return (
    <div className="card p-6 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-xl font-bold text-white">Paper Trading</h3>
        <div className="flex items-center space-x-2">
          <div className={`w-2 h-2 rounded-full ${hasTrades ? 'bg-green-400' : 'bg-yellow-400'} animate-pulse`} />
          <span className="text-xs text-gray-400">
            {hasTrades ? 'Active' : 'Awaiting Trades'}
          </span>
        </div>
      </div>

      {/* Main P&L Display with Sparkline */}
      <div className="bg-gray-900/50 rounded-lg p-4">
        <div className="flex items-center justify-between">
          <div className="text-center flex-1">
            <span className="block text-sm text-gray-400 mb-1">Total P&L (30d)</span>
            <span className={`text-3xl font-bold font-mono ${pnlColor}`}>
              {formatPnL(stats?.total_pnl)}
            </span>
          </div>
          {sparklineData.length > 2 && (
            <div className="ml-4">
              <MiniSparkline
                data={sparklineData}
                color="auto"
                height={40}
                width={80}
              />
            </div>
          )}
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-gray-900/30 rounded-lg p-3 text-center">
          <span className="block text-xs text-gray-500 mb-1">Win Rate</span>
          <span className={`text-lg font-bold ${winRateColor}`}>
            {stats?.win_rate?.toFixed(1) || '0.0'}%
          </span>
        </div>
        <div className="bg-gray-900/30 rounded-lg p-3 text-center">
          <span className="block text-xs text-gray-500 mb-1">Trades</span>
          <span className="text-lg font-bold text-white">
            {stats?.total_trades || 0}
          </span>
        </div>
        <div className="bg-gray-900/30 rounded-lg p-3 text-center">
          <span className="block text-xs text-gray-500 mb-1">Open</span>
          <span className="text-lg font-bold text-blue-400">
            {stats?.open_trades || 0}
          </span>
        </div>
      </div>

      {/* Win/Loss Bar */}
      {hasTrades && (
        <div className="space-y-1">
          <div className="flex justify-between text-xs text-gray-400">
            <span>W: {stats?.winning_trades || 0}</span>
            <span>L: {stats?.losing_trades || 0}</span>
          </div>
          <div className="h-2 bg-gray-800 rounded-full overflow-hidden flex">
            <div
              className="bg-green-500 h-full transition-all duration-500"
              style={{ width: `${stats?.win_rate || 0}%` }}
            />
            <div
              className="bg-red-500 h-full transition-all duration-500"
              style={{ width: `${100 - (stats?.win_rate || 0)}%` }}
            />
          </div>
        </div>
      )}

      {/* Professional Risk Metrics */}
      {hasTrades && stats?.profit_factor !== undefined && (
        <div className="pt-3 border-t border-gray-700 space-y-3">
          <span className="text-xs text-gray-500 font-semibold">Professional Metrics</span>

          {/* Profit Factor & Risk/Reward */}
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-gray-900/30 rounded-lg p-2">
              <div className="flex justify-between items-center">
                <span className="text-xs text-gray-500">Profit Factor</span>
                <span className={`text-xs px-1.5 py-0.5 rounded ${
                  stats?.profit_factor >= 1.75 ? 'bg-green-500/20 text-green-400' :
                  stats?.profit_factor >= 1 ? 'bg-yellow-500/20 text-yellow-400' :
                  'bg-red-500/20 text-red-400'
                }`}>
                  {stats?.profit_factor >= 1.75 ? 'Healthy' : stats?.profit_factor >= 1 ? 'Marginal' : 'Poor'}
                </span>
              </div>
              <span className={`text-lg font-bold ${
                stats?.profit_factor >= 1.75 ? 'text-green-400' :
                stats?.profit_factor >= 1 ? 'text-yellow-400' :
                'text-red-400'
              }`}>
                {stats?.profit_factor?.toFixed(2) || '--'}
              </span>
              <span className="text-xs text-gray-600 block">Target: 1.75-4.0</span>
            </div>
            <div className="bg-gray-900/30 rounded-lg p-2">
              <span className="text-xs text-gray-500 block">Risk/Reward</span>
              <span className={`text-lg font-bold ${
                stats?.risk_reward_ratio >= 1.5 ? 'text-green-400' :
                stats?.risk_reward_ratio >= 1 ? 'text-yellow-400' :
                'text-red-400'
              }`}>
                {stats?.risk_reward_ratio?.toFixed(2) || '--'}
              </span>
              <span className="text-xs text-gray-600 block">Avg W/L</span>
            </div>
          </div>

          {/* Expectancy & Fee Efficiency */}
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-gray-900/30 rounded-lg p-2">
              <span className="text-xs text-gray-500 block">Expectancy</span>
              <span className={`text-lg font-bold ${
                stats?.expectancy > 0 ? 'text-green-400' : 'text-red-400'
              }`}>
                {stats?.expectancy > 0 ? '+' : ''}${stats?.expectancy?.toFixed(2) || '0.00'}
              </span>
              <span className="text-xs text-gray-600 block">Per trade</span>
            </div>
            <div className="bg-gray-900/30 rounded-lg p-2">
              <span className="text-xs text-gray-500 block">Fee Drag</span>
              <span className={`text-lg font-bold ${
                stats?.fee_efficiency_pct <= 10 ? 'text-green-400' :
                stats?.fee_efficiency_pct <= 20 ? 'text-yellow-400' :
                'text-red-400'
              }`}>
                {stats?.fee_efficiency_pct?.toFixed(1) || '0.0'}%
              </span>
              <span className="text-xs text-gray-600 block">Target: &lt;10%</span>
            </div>
          </div>

          {/* Avg Win/Loss Details (collapsed by default) */}
          <details className="bg-gray-900/20 rounded-lg">
            <summary className="cursor-pointer p-2 text-xs text-gray-500 hover:text-gray-300">
              Win/Loss Details
            </summary>
            <div className="grid grid-cols-2 gap-3 p-2 pt-0">
              <div className="text-center">
                <span className="text-xs text-gray-500 block">Avg Win</span>
                <span className="text-green-400 font-bold">${stats?.avg_win?.toFixed(2) || '0.00'}</span>
                <span className="text-xs text-gray-600 block">({stats?.avg_win_pct?.toFixed(1) || '0.0'}%)</span>
              </div>
              <div className="text-center">
                <span className="text-xs text-gray-500 block">Avg Loss</span>
                <span className="text-red-400 font-bold">-${stats?.avg_loss?.toFixed(2) || '0.00'}</span>
                <span className="text-xs text-gray-600 block">({stats?.avg_loss_pct?.toFixed(1) || '0.0'}%)</span>
              </div>
            </div>
          </details>
        </div>
      )}

      {/* Concentration Risk Warning */}
      {concentration?.concentration_warnings?.length > 0 && (
        <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-3">
          <div className="flex items-start gap-2">
            <span className="text-yellow-400 text-sm">&#9888;</span>
            <div className="space-y-1">
              {concentration.concentration_warnings.slice(0, 2).map((warning, i) => (
                <p key={i} className="text-xs text-yellow-400">{warning}</p>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Signal Alignment & Accuracy Row */}
      {/* API returns alignment_pct and prediction_accuracy_pct as percentages (e.g., 75) */}
      {(signalPerf?.alignment_pct != null || signalPerf?.prediction_accuracy_pct != null ||
        signalPerf?.signal_alignment || signalPerf?.prediction_accuracy) && (
        <div className="grid grid-cols-2 gap-3 pt-2 border-t border-gray-700">
          <div className="bg-gray-900/30 rounded-lg p-2 text-center">
            <span className="block text-xs text-gray-500 mb-0.5">Alignment</span>
            <span className="text-sm font-bold text-purple-400">
              {signalPerf?.alignment_pct != null
                ? `${signalPerf.alignment_pct.toFixed(0)}%`
                : signalPerf?.signal_alignment
                  ? `${(signalPerf.signal_alignment * 100).toFixed(0)}%`
                  : '--'}
            </span>
          </div>
          <div className="bg-gray-900/30 rounded-lg p-2 text-center">
            <span className="block text-xs text-gray-500 mb-0.5">Accuracy</span>
            <span className="text-sm font-bold text-blue-400">
              {signalPerf?.prediction_accuracy_pct != null
                ? `${signalPerf.prediction_accuracy_pct.toFixed(0)}%`
                : signalPerf?.prediction_accuracy
                  ? `${(signalPerf.prediction_accuracy * 100).toFixed(0)}%`
                  : '--'}
            </span>
          </div>
        </div>
      )}

      {/* Recent Trades Mini-List */}
      {recentTrades && recentTrades.length > 0 && (
        <div className="pt-3 border-t border-gray-700">
          <span className="text-xs text-gray-500 mb-2 block">Recent Trades</span>
          <div className="space-y-1">
            {recentTrades.slice(0, 3).map((trade) => (
              <div
                key={trade.id}
                className="flex items-center justify-between text-xs p-2 bg-gray-900/30 rounded"
              >
                <div className="flex items-center space-x-2">
                  <span className={trade.action === 'buy' ? 'text-green-400' : 'text-red-400'}>
                    {trade.action.toUpperCase()}
                  </span>
                  <span className="text-gray-300">{trade.symbol}</span>
                </div>
                <span className={trade.pnl >= 0 ? 'text-green-400' : 'text-red-400'}>
                  {trade.status === 'closed' ? formatPnL(trade.pnl) : trade.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* No Trades Message */}
      {!hasTrades && (
        <div className="text-center py-4 text-gray-500 text-sm">
          <p>No paper trades yet</p>
          <p className="text-xs mt-1">OctoBot will execute trades based on signals</p>
        </div>
      )}
    </div>
  )
}

export default TradePerformance
