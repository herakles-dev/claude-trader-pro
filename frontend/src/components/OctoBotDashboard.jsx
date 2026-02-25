import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from 'react-query'
import { signalsAPI } from '../services/api'

function OctoBotDashboard() {
  const [isExpanded, setIsExpanded] = useState(true)
  const queryClient = useQueryClient()

  // Fetch OctoBot health
  const { data: healthData, isLoading: healthLoading } = useQuery(
    ['octobot-health'],
    () => signalsAPI.getOctoBotHealth(),
    {
      refetchInterval: 30000, // 30 seconds
      select: (response) => response.data,
    }
  )

  // Fetch portfolio
  const { data: portfolioData, isLoading: portfolioLoading } = useQuery(
    ['octobot-portfolio'],
    () => signalsAPI.getOctoBotPortfolio(),
    {
      refetchInterval: 60000, // 60 seconds
      select: (response) => response.data,
    }
  )

  // Fetch open orders
  const { data: ordersData, isLoading: ordersLoading } = useQuery(
    ['octobot-orders'],
    () => signalsAPI.getOctoBotOrders(),
    {
      refetchInterval: 15000, // 15 seconds
      select: (response) => response.data,
    }
  )

  // Fetch sync status
  const { data: syncStatus } = useQuery(
    ['octobot-sync-status'],
    () => signalsAPI.getSyncStatus(),
    {
      refetchInterval: 60000,
      select: (response) => response.data,
    }
  )

  // Manual sync mutation
  const syncMutation = useMutation(
    () => signalsAPI.triggerSync(),
    {
      onSuccess: () => {
        queryClient.invalidateQueries(['octobot-sync-status'])
        queryClient.invalidateQueries(['trade-history'])
      },
    }
  )

  const isHealthy = healthData?.healthy ?? false
  const portfolio = portfolioData?.portfolio || {}
  const totalValue = portfolioData?.total_value_usd || 10000
  const orders = ordersData?.orders || []
  const lastSync = syncStatus?.last_sync

  // Calculate time since last sync
  const getTimeSinceSync = () => {
    if (!lastSync) return 'Never'
    const syncTime = new Date(lastSync)
    const now = new Date()
    const diffMs = now - syncTime
    const diffMins = Math.floor(diffMs / 60000)
    if (diffMins < 1) return 'Just now'
    if (diffMins < 60) return `${diffMins}m ago`
    const diffHours = Math.floor(diffMins / 60)
    return `${diffHours}h ago`
  }

  // Extract balances from portfolio
  const getBalance = (currency) => {
    const balance = portfolio[currency] || portfolio[currency.toLowerCase()]
    if (!balance) return { total: 0, available: 0 }
    if (typeof balance === 'number') return { total: balance, available: balance }
    return {
      total: balance.total || balance.amount || 0,
      available: balance.available || balance.free || balance.total || 0,
    }
  }

  const usdtBalance = getBalance('USDT')
  const btcBalance = getBalance('BTC')
  const ethBalance = getBalance('ETH')

  const formatCurrency = (value, decimals = 2) => {
    if (value === null || value === undefined) return '-'
    return `$${parseFloat(value).toLocaleString(undefined, {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    })}`
  }

  const formatCrypto = (value, decimals = 4) => {
    if (value === null || value === undefined || value === 0) return '-'
    return parseFloat(value).toFixed(decimals)
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
          <h3 className="text-lg font-bold text-white">OctoBot Paper Trading</h3>
        </div>
        <div className="flex items-center space-x-4">
          {/* Health indicator */}
          <div className="flex items-center space-x-2">
            <span
              className={`w-2.5 h-2.5 rounded-full ${
                healthLoading
                  ? 'bg-yellow-500 animate-pulse'
                  : isHealthy
                  ? 'bg-green-500'
                  : 'bg-red-500'
              }`}
            />
            <span className={`text-sm ${isHealthy ? 'text-green-400' : 'text-red-400'}`}>
              {healthLoading ? 'Checking...' : isHealthy ? 'Connected' : 'Disconnected'}
            </span>
          </div>
          {/* Sync indicator */}
          <span className="text-xs text-gray-500">
            {getTimeSinceSync()}
          </span>
        </div>
      </button>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="px-4 pb-4 space-y-4 border-t border-gray-800">
          {/* Portfolio Value Row */}
          <div className="grid grid-cols-3 gap-4 pt-4">
            <div>
              <span className="block text-xs text-gray-500 mb-1">Portfolio Value</span>
              <span className="text-xl font-bold text-white font-mono">
                {portfolioLoading ? '...' : formatCurrency(totalValue)}
              </span>
              <span className="block text-xs text-gray-600 mt-0.5">Paper Trading</span>
            </div>
            <div>
              <span className="block text-xs text-gray-500 mb-1">USDT Balance</span>
              <span className="text-xl font-bold text-white font-mono">
                {portfolioLoading ? '...' : formatCurrency(usdtBalance.available)}
              </span>
              <span className="block text-xs text-gray-600 mt-0.5">Available</span>
            </div>
            <div>
              <span className="block text-xs text-gray-500 mb-1">BTC Holdings</span>
              <span className="text-xl font-bold text-orange-400 font-mono">
                {portfolioLoading ? '...' : formatCrypto(btcBalance.total)}
              </span>
              <span className="block text-xs text-gray-600 mt-0.5">BTC</span>
            </div>
          </div>

          {/* Additional Holdings */}
          {ethBalance.total > 0 && (
            <div className="flex items-center space-x-4 text-sm text-gray-400">
              <span>ETH: {formatCrypto(ethBalance.total)} ETH</span>
            </div>
          )}

          {/* Open Orders Section */}
          <div className="border-t border-gray-800 pt-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-gray-400">
                Open Orders ({orders.length})
              </span>
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  syncMutation.mutate()
                }}
                disabled={syncMutation.isLoading}
                className="text-xs text-blue-400 hover:text-blue-300 disabled:text-gray-500 flex items-center space-x-1"
              >
                <span className={syncMutation.isLoading ? 'animate-spin' : ''}>
                  {syncMutation.isLoading ? '⟳' : '⟳'}
                </span>
                <span>{syncMutation.isLoading ? 'Syncing...' : 'Sync Now'}</span>
              </button>
            </div>

            {ordersLoading ? (
              <div className="text-sm text-gray-500">Loading orders...</div>
            ) : orders.length === 0 ? (
              <div className="text-sm text-gray-500">No open orders</div>
            ) : (
              <div className="space-y-2 max-h-32 overflow-y-auto">
                {orders.slice(0, 5).map((order, idx) => (
                  <div
                    key={order.id || idx}
                    className="flex items-center justify-between text-sm bg-gray-900/30 rounded px-3 py-2"
                  >
                    <div className="flex items-center space-x-2">
                      <span className={`px-1.5 py-0.5 rounded text-xs font-bold ${
                        order.side === 'buy'
                          ? 'bg-green-500/20 text-green-400'
                          : 'bg-red-500/20 text-red-400'
                      }`}>
                        {order.side?.toUpperCase()}
                      </span>
                      <span className="text-white font-medium">{order.symbol}</span>
                    </div>
                    <div className="text-right">
                      <span className="text-gray-400 font-mono text-xs">
                        {formatCrypto(order.amount || order.quantity, 6)} @ {formatCurrency(order.price)}
                      </span>
                    </div>
                  </div>
                ))}
                {orders.length > 5 && (
                  <div className="text-xs text-gray-500 text-center">
                    +{orders.length - 5} more orders
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Sync Status Footer */}
          <div className="flex items-center justify-between text-xs text-gray-500 pt-2 border-t border-gray-800">
            <span>
              Sync Interval: {syncStatus?.sync_interval_seconds || 300}s
            </span>
            <span>
              Status: {syncStatus?.status || 'unknown'}
            </span>
          </div>
        </div>
      )}
    </div>
  )
}

export default OctoBotDashboard
