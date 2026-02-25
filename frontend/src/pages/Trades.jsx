import React, { useState, useEffect } from 'react'
import { useQuery } from 'react-query'
import { tradesAPI } from '../services/api'
import LivePositions from '../components/LivePositions'
import OctoBotDashboard from '../components/OctoBotDashboard'
import BacktestResults from '../components/BacktestResults'
import { logComponentData, logTradeData } from '../utils/debugLogger'

function Trades() {
  const [filters, setFilters] = useState({
    symbol: '',
    status: '',
    executionType: '', // 'auto', 'manual', or ''
    page: 1,
    pageSize: 25,
  })

  const offset = (filters.page - 1) * filters.pageSize

  const { data: tradesData, isLoading, error } = useQuery(
    ['trade-history', filters],
    () => tradesAPI.getHistory({
      symbol: filters.symbol || undefined,
      status: filters.status || undefined,
      limit: filters.pageSize,
      offset,
    }),
    {
      refetchInterval: 30000,
      select: (response) => response.data?.data || response.data,
      keepPreviousData: true,
    }
  )

  const { data: stats } = useQuery(
    ['trade-statistics-full'],
    () => tradesAPI.getStatistics({ days: 90 }),
    {
      refetchInterval: 60000,
      select: (response) => response.data?.data || response.data,
    }
  )

  const trades = tradesData?.trades || []
  const totalCount = tradesData?.total_available || tradesData?.total_count || trades.length
  const totalPages = Math.ceil(totalCount / filters.pageSize) || 1

  // Debug logging when data loads
  useEffect(() => {
    if (tradesData) {
      logComponentData('Trades', 'tradesData', tradesData, { filters })
      logTradeData('Trades.jsx - Trade History', trades, null)
      console.log('%c[TRADES DEBUG] Raw tradesData:', 'color: #f59e0b', tradesData)
      console.log('%c[TRADES DEBUG] Extracted trades array:', 'color: #22c55e', trades)
      console.log('%c[TRADES DEBUG] Total count:', 'color: #3b82f6', totalCount)
    }
  }, [tradesData, trades, totalCount])

  useEffect(() => {
    if (stats) {
      logTradeData('Trades.jsx - Statistics', [], stats)
      console.log('%c[TRADES DEBUG] Statistics:', 'color: #a855f7', stats)
      // Check for expected stat fields
      const expectedFields = ['total_trades', 'total_pnl', 'total_net_pnl', 'win_rate', 'net_win_rate', 'total_fees_paid']
      const presentFields = expectedFields.filter(f => stats[f] !== undefined)
      const missingFields = expectedFields.filter(f => stats[f] === undefined)
      console.log('%c[TRADES DEBUG] Present stat fields:', 'color: #22c55e', presentFields)
      if (missingFields.length > 0) {
        console.warn('%c[TRADES DEBUG] Missing stat fields:', 'color: #ef4444', missingFields)
      }
    }
  }, [stats])

  const formatPrice = (price) => {
    if (price === null || price === undefined) return '-'
    return `$${parseFloat(price).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
  }

  const formatPnL = (value) => {
    if (value === null || value === undefined) return '-'
    const num = parseFloat(value)
    const sign = num >= 0 ? '+' : '-'
    return `${sign}$${Math.abs(num).toFixed(2)}`
  }

  const formatDate = (dateStr) => {
    if (!dateStr) return '-'
    return new Date(dateStr).toLocaleString()
  }

  // Filter trades by execution type (client-side until backend supports it)
  const filteredTrades = trades.filter((trade) => {
    if (!filters.executionType) return true
    if (filters.executionType === 'auto') return trade.was_auto_executed === true
    if (filters.executionType === 'manual') return trade.was_auto_executed === false
    return true
  })

  // Render execution badge
  const renderExecutionBadge = (trade) => {
    const isAuto = trade.was_auto_executed === true
    const isManual = trade.was_auto_executed === false
    const isSynced = !!trade.octobot_synced_at

    return (
      <div className="flex items-center space-x-1">
        {isAuto && (
          <span
            className="px-1.5 py-0.5 rounded text-xs font-bold bg-purple-500/20 text-purple-400"
            title={trade.execution_confidence ? `Confidence: ${(trade.execution_confidence * 100).toFixed(1)}%` : 'Auto-executed by scheduler'}
          >
            AUTO
          </span>
        )}
        {isManual && (
          <span className="px-1.5 py-0.5 rounded text-xs font-bold bg-gray-500/20 text-gray-400">
            MANUAL
          </span>
        )}
        {isSynced && (
          <span
            className="text-green-500 text-xs"
            title={`Synced: ${new Date(trade.octobot_synced_at).toLocaleString()}`}
          >
            &#x21BB;
          </span>
        )}
      </div>
    )
  }

  const handleFilterChange = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value, page: 1 }))
  }

  const symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT']

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">Trade History</h1>
          <p className="text-gray-400 mt-1">Paper trading performance and open positions</p>
        </div>
      </div>

      {/* Stats Summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-4">
        <div className="card p-4">
          <span className="block text-xs text-gray-500 mb-1">Net P&L (90d)</span>
          <span className={`text-xl font-bold font-mono ${(stats?.total_net_pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {formatPnL(stats?.total_net_pnl)}
          </span>
          <span className="block text-xs text-gray-600 mt-1">After fees</span>
        </div>
        <div className="card p-4">
          <span className="block text-xs text-gray-500 mb-1">Gross P&L</span>
          <span className={`text-xl font-bold font-mono ${(stats?.total_pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {formatPnL(stats?.total_pnl)}
          </span>
          <span className="block text-xs text-gray-600 mt-1">Before fees</span>
        </div>
        <div className="card p-4 border-l-2 border-yellow-500/30">
          <span className="block text-xs text-gray-500 mb-1">Total Fees</span>
          <span className="text-xl font-bold font-mono text-yellow-400">
            -${(stats?.total_fees_paid || 0).toFixed(2)}
          </span>
          <span className="block text-xs text-gray-600 mt-1">Avg: ${(stats?.avg_fee_per_trade || 0).toFixed(2)}/trade</span>
        </div>
        <div className="card p-4">
          <span className="block text-xs text-gray-500 mb-1">Net Win Rate</span>
          <span className={`text-xl font-bold ${(stats?.net_win_rate || 0) >= 50 ? 'text-green-400' : 'text-yellow-400'}`}>
            {(stats?.net_win_rate || 0).toFixed(1)}%
          </span>
          <span className="block text-xs text-gray-600 mt-1">Gross: {(stats?.win_rate || 0).toFixed(1)}%</span>
        </div>
        <div className="card p-4">
          <span className="block text-xs text-gray-500 mb-1">Total Trades</span>
          <span className="text-xl font-bold text-white">{stats?.total_trades || 0}</span>
        </div>
        <div className="card p-4">
          <span className="block text-xs text-gray-500 mb-1">Winning (Net)</span>
          <span className="text-xl font-bold text-green-400">{stats?.net_winning_trades || 0}</span>
          <span className="block text-xs text-gray-600 mt-1">Gross: {stats?.winning_trades || 0}</span>
        </div>
        <div className="card p-4">
          <span className="block text-xs text-gray-500 mb-1">Losing (Net)</span>
          <span className="text-xl font-bold text-red-400">{stats?.net_losing_trades || 0}</span>
          <span className="block text-xs text-gray-600 mt-1">Gross: {stats?.losing_trades || 0}</span>
        </div>
      </div>

      {/* Professional Risk Metrics Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="card p-4 border-l-2 border-purple-500/30">
          <span className="block text-xs text-gray-500 mb-1">Profit Factor</span>
          <span className={`text-xl font-bold font-mono ${
            stats?.profit_factor >= 1.75 ? 'text-green-400' :
            stats?.profit_factor >= 1.0 ? 'text-yellow-400' : 'text-red-400'
          }`}>
            {stats?.profit_factor?.toFixed(2) || '--'}
          </span>
          <span className="block text-xs text-gray-600 mt-1">Target: 1.75+</span>
        </div>
        <div className="card p-4 border-l-2 border-purple-500/30">
          <span className="block text-xs text-gray-500 mb-1">Risk/Reward</span>
          <span className={`text-xl font-bold font-mono ${
            stats?.risk_reward_ratio >= 1.5 ? 'text-green-400' :
            stats?.risk_reward_ratio >= 1.0 ? 'text-yellow-400' : 'text-red-400'
          }`}>
            {stats?.risk_reward_ratio?.toFixed(2) || '--'}
          </span>
          <span className="block text-xs text-gray-600 mt-1">Avg Win / Avg Loss</span>
        </div>
        <div className="card p-4 border-l-2 border-purple-500/30">
          <span className="block text-xs text-gray-500 mb-1">Expectancy</span>
          <span className={`text-xl font-bold font-mono ${
            stats?.expectancy > 0 ? 'text-green-400' : 'text-red-400'
          }`}>
            {stats?.expectancy > 0 ? '+' : ''}${stats?.expectancy?.toFixed(2) || '0.00'}
          </span>
          <span className="block text-xs text-gray-600 mt-1">Expected per trade</span>
        </div>
        <div className="card p-4 border-l-2 border-purple-500/30">
          <span className="block text-xs text-gray-500 mb-1">Fee Drag</span>
          <span className={`text-xl font-bold font-mono ${
            stats?.fee_efficiency_pct <= 10 ? 'text-green-400' :
            stats?.fee_efficiency_pct <= 20 ? 'text-yellow-400' : 'text-red-400'
          }`}>
            {stats?.fee_efficiency_pct?.toFixed(1) || '0.0'}%
          </span>
          <span className="block text-xs text-gray-600 mt-1">Target: &lt;10%</span>
        </div>
      </div>

      {/* OctoBot Dashboard & Backtest Results Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <OctoBotDashboard />
        <BacktestResults />
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Live Positions Sidebar */}
        <div className="lg:col-span-1">
          <LivePositions />
        </div>

        {/* Trade History Table */}
        <div className="lg:col-span-2 card p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-xl font-bold text-white">Trade History</h3>

            {/* Filters */}
            <div className="flex items-center space-x-3">
              <select
                value={filters.symbol}
                onChange={(e) => handleFilterChange('symbol', e.target.value)}
                className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none"
              >
                <option value="">All Pairs</option>
                {symbols.map(s => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>

              <select
                value={filters.status}
                onChange={(e) => handleFilterChange('status', e.target.value)}
                className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none"
              >
                <option value="">All Status</option>
                <option value="open">Open</option>
                <option value="closed">Closed</option>
              </select>

              <select
                value={filters.executionType}
                onChange={(e) => handleFilterChange('executionType', e.target.value)}
                className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none"
              >
                <option value="">All Execution</option>
                <option value="auto">Auto Only</option>
                <option value="manual">Manual Only</option>
              </select>
            </div>
          </div>

          {isLoading ? (
            <div className="space-y-3">
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="skeleton h-16" />
              ))}
            </div>
          ) : error ? (
            <div className="text-center py-8 text-red-400">
              Failed to load trade history
            </div>
          ) : trades.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              <div className="text-4xl mb-2">-</div>
              <p>No trades found</p>
              <p className="text-xs mt-1">Trades will appear as OctoBot executes signals</p>
            </div>
          ) : (
            <>
              {/* Desktop Table */}
              <div className="hidden md:block overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="text-left text-xs text-gray-500 border-b border-gray-800">
                      <th className="pb-3 font-medium">Date</th>
                      <th className="pb-3 font-medium">Pair</th>
                      <th className="pb-3 font-medium">Side</th>
                      <th className="pb-3 font-medium">Entry</th>
                      <th className="pb-3 font-medium">Exit</th>
                      <th className="pb-3 font-medium">Qty</th>
                      <th className="pb-3 font-medium">Fees</th>
                      <th className="pb-3 font-medium">Net P&L</th>
                      <th className="pb-3 font-medium">Status</th>
                      <th className="pb-3 font-medium">Execution</th>
                    </tr>
                  </thead>
                  <tbody className="text-sm">
                    {filteredTrades.map((trade) => (
                      <tr key={trade.id} className="border-b border-gray-800/50 hover:bg-gray-900/30">
                        <td className="py-3 text-gray-400 text-xs">
                          {formatDate(trade.executed_at)}
                        </td>
                        <td className="py-3 text-white font-medium">{trade.symbol}</td>
                        <td className="py-3">
                          <span className={`px-2 py-1 rounded text-xs font-bold ${
                            trade.action === 'buy'
                              ? 'bg-green-500/20 text-green-400'
                              : 'bg-red-500/20 text-red-400'
                          }`}>
                            {trade.action?.toUpperCase()}
                          </span>
                        </td>
                        <td className="py-3 font-mono text-white">{formatPrice(trade.entry_price)}</td>
                        <td className="py-3 font-mono text-white">{formatPrice(trade.exit_price)}</td>
                        <td className="py-3 font-mono text-gray-400">
                          {parseFloat(trade.quantity || 0).toFixed(6)}
                        </td>
                        <td className="py-3 font-mono text-yellow-400 text-xs">
                          {trade.total_fees ? `-$${parseFloat(trade.total_fees).toFixed(2)}` : '-'}
                        </td>
                        <td className="py-3">
                          {trade.status === 'open' ? (
                            <span className="text-blue-400 font-mono font-bold">Open</span>
                          ) : (
                            <div className="flex flex-col">
                              <span className={`font-mono font-bold ${
                                (trade.net_pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'
                              }`}>
                                {formatPnL(trade.net_pnl)}
                              </span>
                              <span className="text-xs text-gray-500">
                                Gross: {formatPnL(trade.pnl)}
                              </span>
                            </div>
                          )}
                        </td>
                        <td className="py-3">
                          <span className={`px-2 py-1 rounded text-xs ${
                            trade.status === 'open'
                              ? 'bg-blue-500/20 text-blue-400'
                              : 'bg-gray-500/20 text-gray-400'
                          }`}>
                            {trade.status}
                          </span>
                        </td>
                        <td className="py-3">
                          {renderExecutionBadge(trade)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Mobile Cards */}
              <div className="md:hidden space-y-3">
                {filteredTrades.map((trade) => (
                  <div key={trade.id} className="bg-gray-900/30 rounded-lg p-4 border border-gray-800">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center space-x-2">
                        <span className={`px-2 py-1 rounded text-xs font-bold ${
                          trade.action === 'buy'
                            ? 'bg-green-500/20 text-green-400'
                            : 'bg-red-500/20 text-red-400'
                        }`}>
                          {trade.action?.toUpperCase()}
                        </span>
                        <span className="text-white font-medium">{trade.symbol}</span>
                        {renderExecutionBadge(trade)}
                      </div>
                      <span className={`px-2 py-1 rounded text-xs ${
                        trade.status === 'open'
                          ? 'bg-blue-500/20 text-blue-400'
                          : 'bg-gray-500/20 text-gray-400'
                      }`}>
                        {trade.status}
                      </span>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div>
                        <span className="text-gray-500">Entry: </span>
                        <span className="text-white font-mono">{formatPrice(trade.entry_price)}</span>
                      </div>
                      <div>
                        <span className="text-gray-500">Exit: </span>
                        <span className="text-white font-mono">{formatPrice(trade.exit_price)}</span>
                      </div>
                      <div>
                        <span className="text-gray-500">Qty: </span>
                        <span className="text-gray-400 font-mono">{parseFloat(trade.quantity || 0).toFixed(6)}</span>
                      </div>
                      <div>
                        <span className="text-gray-500">Fees: </span>
                        <span className="text-yellow-400 font-mono">
                          {trade.total_fees ? `-$${parseFloat(trade.total_fees).toFixed(2)}` : '-'}
                        </span>
                      </div>
                      <div className="col-span-2">
                        <span className="text-gray-500">Net P&L: </span>
                        <span className={`font-mono font-bold ${
                          trade.status === 'open' ? 'text-blue-400' :
                          (trade.net_pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'
                        }`}>
                          {trade.status === 'open' ? 'Open' : formatPnL(trade.net_pnl)}
                        </span>
                        {trade.status === 'closed' && (
                          <span className="text-gray-500 ml-2">(Gross: {formatPnL(trade.pnl)})</span>
                        )}
                      </div>
                    </div>
                    <div className="mt-2 text-xs text-gray-500">
                      {formatDate(trade.executed_at)}
                    </div>
                  </div>
                ))}
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between mt-4 pt-4 border-t border-gray-800">
                  <span className="text-sm text-gray-400">
                    Page {filters.page} of {totalPages}
                  </span>
                  <div className="flex items-center space-x-2">
                    <button
                      onClick={() => setFilters(prev => ({ ...prev, page: prev.page - 1 }))}
                      disabled={filters.page === 1}
                      className="px-3 py-1 rounded bg-gray-800 text-white text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-700"
                    >
                      Previous
                    </button>
                    <button
                      onClick={() => setFilters(prev => ({ ...prev, page: prev.page + 1 }))}
                      disabled={filters.page === totalPages}
                      className="px-3 py-1 rounded bg-gray-800 text-white text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-700"
                    >
                      Next
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

export default Trades
