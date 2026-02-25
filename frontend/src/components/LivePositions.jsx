import React, { useEffect } from 'react'
import { useQuery } from 'react-query'
import { tradesAPI, marketAPI } from '../services/api'
import { logComponentData, logTradeData, logMarketData } from '../utils/debugLogger'

function LivePositions({ symbol = null }) {
  const { data: positions, isLoading, error } = useQuery(
    ['open-positions', symbol],
    () => tradesAPI.getOpenPositions({ symbol }),
    {
      refetchInterval: 10000, // 10 seconds for live updates
      select: (response) => {
        const result = response.data?.data?.trades || response.data?.trades || []
        console.log('%c[LIVE POSITIONS DEBUG] Raw API response:', 'color: #f59e0b', response.data)
        console.log('%c[LIVE POSITIONS DEBUG] Extracted positions:', 'color: #22c55e', result)
        return result
      },
    }
  )

  const { data: marketData } = useQuery(
    ['market-prices'],
    () => marketAPI.getCached(),
    {
      refetchInterval: 5000, // 5 seconds for price updates
      select: (response) => {
        const result = response.data?.data?.data || {}
        console.log('%c[LIVE POSITIONS DEBUG] Market data raw:', 'color: #f59e0b', response.data)
        console.log('%c[LIVE POSITIONS DEBUG] Market data extracted:', 'color: #22c55e', result)
        return result
      },
    }
  )

  // Debug logging when data loads
  useEffect(() => {
    if (positions !== undefined) {
      logComponentData('LivePositions', 'positions', positions, { symbol })
      logTradeData('LivePositions.jsx', positions, null)
    }
  }, [positions, symbol])

  useEffect(() => {
    if (marketData) {
      logMarketData('LivePositions.jsx', marketData)
    }
  }, [marketData])

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

  // Default fee rate for estimation (0.1% taker fee)
  const DEFAULT_FEE_RATE = 0.001

  const calculateUnrealizedPnL = (position) => {
    if (!marketData || !position.entry_price || !position.quantity) return null

    // Extract base symbol from pair (BTC/USDT -> BTC)
    const baseSymbol = position.symbol?.split('/')[0]
    const currentPrice = marketData[baseSymbol]?.current_price

    if (!currentPrice) return null

    const entryPrice = parseFloat(position.entry_price)
    const quantity = parseFloat(position.quantity)

    // Gross unrealized P&L
    if (position.action === 'buy') {
      return (currentPrice - entryPrice) * quantity
    } else {
      return (entryPrice - currentPrice) * quantity
    }
  }

  const calculateNetUnrealizedPnL = (position) => {
    if (!marketData || !position.entry_price || !position.quantity) return null

    const baseSymbol = position.symbol?.split('/')[0]
    const currentPrice = marketData[baseSymbol]?.current_price

    if (!currentPrice) return null

    const entryPrice = parseFloat(position.entry_price)
    const quantity = parseFloat(position.quantity)

    // Gross unrealized P&L
    let grossPnL
    if (position.action === 'buy') {
      grossPnL = (currentPrice - entryPrice) * quantity
    } else {
      grossPnL = (entryPrice - currentPrice) * quantity
    }

    // Entry fee (already paid, from API or estimated)
    const entryFee = position.entry_fee || (entryPrice * quantity * DEFAULT_FEE_RATE)

    // Estimated exit fee (0.1% of current value)
    const estimatedExitFee = currentPrice * quantity * DEFAULT_FEE_RATE

    // Total fees
    const totalFees = entryFee + estimatedExitFee

    // Net unrealized P&L
    return grossPnL - totalFees
  }

  const calculateFees = (position) => {
    if (!marketData || !position.entry_price || !position.quantity) return null

    const baseSymbol = position.symbol?.split('/')[0]
    const currentPrice = marketData[baseSymbol]?.current_price

    if (!currentPrice) return null

    const entryPrice = parseFloat(position.entry_price)
    const quantity = parseFloat(position.quantity)

    // Entry fee (from API or estimated)
    const entryFee = position.entry_fee || (entryPrice * quantity * DEFAULT_FEE_RATE)

    // Estimated exit fee
    const estimatedExitFee = currentPrice * quantity * DEFAULT_FEE_RATE

    return {
      entryFee,
      estimatedExitFee,
      totalFees: entryFee + estimatedExitFee
    }
  }

  const calculateUnrealizedPnLPercent = (position) => {
    if (!marketData || !position.entry_price) return null

    const baseSymbol = position.symbol?.split('/')[0]
    const currentPrice = marketData[baseSymbol]?.current_price

    if (!currentPrice) return null

    const entryPrice = parseFloat(position.entry_price)
    const pnlPercent = ((currentPrice - entryPrice) / entryPrice) * 100

    return position.action === 'buy' ? pnlPercent : -pnlPercent
  }

  const calculateNetUnrealizedPnLPercent = (position) => {
    if (!marketData || !position.entry_price || !position.quantity) return null

    const baseSymbol = position.symbol?.split('/')[0]
    const currentPrice = marketData[baseSymbol]?.current_price

    if (!currentPrice) return null

    const entryPrice = parseFloat(position.entry_price)
    const quantity = parseFloat(position.quantity)

    const netPnL = calculateNetUnrealizedPnL(position)
    if (netPnL === null) return null

    const entryValue = entryPrice * quantity
    return (netPnL / entryValue) * 100
  }

  if (isLoading) {
    return (
      <div className="card p-6">
        <div className="skeleton h-8 w-40 mb-4" />
        <div className="space-y-3">
          {[1, 2].map((i) => (
            <div key={i} className="skeleton h-20" />
          ))}
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="card p-6">
        <h3 className="text-xl font-bold text-white mb-2">Live Positions</h3>
        <p className="text-red-400 text-sm">Failed to load positions</p>
      </div>
    )
  }

  const totalGrossUnrealizedPnL = positions?.reduce((sum, pos) => {
    const pnl = calculateUnrealizedPnL(pos)
    return sum + (pnl || 0)
  }, 0) || 0

  const totalNetUnrealizedPnL = positions?.reduce((sum, pos) => {
    const pnl = calculateNetUnrealizedPnL(pos)
    return sum + (pnl || 0)
  }, 0) || 0

  const totalEstimatedFees = positions?.reduce((sum, pos) => {
    const fees = calculateFees(pos)
    return sum + (fees?.totalFees || 0)
  }, 0) || 0

  return (
    <div className="card p-6 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-xl font-bold text-white">Live Positions</h3>
        <div className="flex items-center space-x-2">
          <div className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
          <span className="text-xs text-gray-400">
            {positions?.length || 0} Open
          </span>
        </div>
      </div>

      {/* Total Unrealized P&L */}
      {positions?.length > 0 && (
        <div className="space-y-2">
          <div className="bg-gray-900/50 rounded-lg p-3">
            <span className="block text-xs text-gray-400 mb-1">Net Unrealized P&L</span>
            <span className={`text-2xl font-bold font-mono ${totalNetUnrealizedPnL >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {formatPnL(totalNetUnrealizedPnL)}
            </span>
            <span className="block text-xs text-gray-500 mt-1">After estimated fees</span>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div className="bg-gray-900/30 rounded-lg p-2">
              <span className="block text-xs text-gray-500">Gross P&L</span>
              <span className={`text-sm font-mono ${totalGrossUnrealizedPnL >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {formatPnL(totalGrossUnrealizedPnL)}
              </span>
            </div>
            <div className="bg-gray-900/30 rounded-lg p-2">
              <span className="block text-xs text-gray-500">Est. Fees</span>
              <span className="text-sm font-mono text-yellow-400">
                -${totalEstimatedFees.toFixed(2)}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Positions List */}
      {positions?.length > 0 ? (
        <div className="space-y-3">
          {positions.map((position) => {
            const grossPnL = calculateUnrealizedPnL(position)
            const netPnL = calculateNetUnrealizedPnL(position)
            const netPnLPercent = calculateNetUnrealizedPnLPercent(position)
            const fees = calculateFees(position)
            const baseSymbol = position.symbol?.split('/')[0]
            const currentPrice = marketData?.[baseSymbol]?.current_price

            return (
              <div
                key={position.id}
                className="bg-gray-900/30 rounded-lg p-4 border border-gray-800 hover:border-gray-700 transition-colors"
              >
                {/* Position Header */}
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center space-x-3">
                    <span className={`px-2 py-1 rounded text-xs font-bold ${
                      position.action === 'buy'
                        ? 'bg-green-500/20 text-green-400'
                        : 'bg-red-500/20 text-red-400'
                    }`}>
                      {position.action?.toUpperCase()}
                    </span>
                    <span className="text-white font-medium">{position.symbol}</span>
                  </div>
                  <span className="text-xs text-gray-500">
                    {position.exchange || 'binance'}
                  </span>
                </div>

                {/* Position Details */}
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="block text-xs text-gray-500">Entry Price</span>
                    <span className="text-white font-mono">{formatPrice(position.entry_price)}</span>
                  </div>
                  <div>
                    <span className="block text-xs text-gray-500">Current Price</span>
                    <span className="text-white font-mono">{currentPrice ? formatPrice(currentPrice) : '-'}</span>
                  </div>
                  <div>
                    <span className="block text-xs text-gray-500">Quantity</span>
                    <span className="text-white font-mono">{parseFloat(position.quantity || 0).toFixed(6)}</span>
                  </div>
                  <div>
                    <span className="block text-xs text-gray-500">Est. Fees</span>
                    <span className="text-yellow-400 font-mono text-sm">
                      {fees ? `-$${fees.totalFees.toFixed(2)}` : '-'}
                    </span>
                  </div>
                </div>

                {/* Net Unrealized P&L */}
                <div className="mt-3 pt-3 border-t border-gray-800">
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="block text-xs text-gray-500">Net Unrealized P&L</span>
                      <div className="flex items-center space-x-2">
                        <span className={`font-mono font-bold ${netPnL >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {netPnL !== null ? formatPnL(netPnL) : '-'}
                        </span>
                        {netPnLPercent !== null && (
                          <span className={`text-xs ${netPnLPercent >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                            ({netPnLPercent >= 0 ? '+' : ''}{netPnLPercent.toFixed(2)}%)
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="text-right">
                      <span className="block text-xs text-gray-500">Gross P&L</span>
                      <span className={`text-xs font-mono ${grossPnL >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {grossPnL !== null ? formatPnL(grossPnL) : '-'}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Time Info */}
                <div className="mt-2 text-xs text-gray-500">
                  Opened: {position.executed_at ? new Date(position.executed_at).toLocaleString() : '-'}
                </div>
              </div>
            )
          })}
        </div>
      ) : (
        <div className="text-center py-8 text-gray-500">
          <div className="text-4xl mb-2">-</div>
          <p className="text-sm">No open positions</p>
          <p className="text-xs mt-1">Positions will appear when OctoBot opens trades</p>
        </div>
      )}
    </div>
  )
}

export default LivePositions
