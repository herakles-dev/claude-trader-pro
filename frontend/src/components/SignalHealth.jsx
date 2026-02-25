import React, { useEffect } from 'react'
import { useQuery } from 'react-query'
import { signalsAPI } from '../services/api'
import { logComponentData } from '../utils/debugLogger'

function SignalHealth() {
  const { data: health, isLoading, error } = useQuery(
    'signal-health',
    () => signalsAPI.getHealth(),
    {
      refetchInterval: 30000, // 30 seconds
      // API returns: { success: true, data: {...health} }
      // Axios wraps this in response.data
      // So actual health is at response.data.data
      select: (response) => {
        console.log('%c[SIGNAL HEALTH DEBUG] Raw response:', 'color: #f59e0b', response.data)
        return response.data?.data || response.data
      },
    }
  )

  // Debug logging when data loads
  useEffect(() => {
    if (health) {
      logComponentData('SignalHealth', 'health', health)
      console.log('%c[SIGNAL HEALTH DEBUG] Health data:', 'color: #22c55e', health)
      console.log('%c[SIGNAL HEALTH DEBUG] Key fields:', 'color: #3b82f6', {
        status: health.status,
        signals_24h: health.signals_24h,
        last_signal_time: health.last_signal_time,
        database: health.database,
      })
    }
  }, [health])

  const formatTime = (timestamp) => {
    if (!timestamp) return 'Never'
    const date = new Date(timestamp)
    const now = new Date()
    const diffMs = now - date
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMs / 3600000)

    if (diffMins < 1) return 'Just now'
    if (diffMins < 60) return `${diffMins}m ago`
    if (diffHours < 24) return `${diffHours}h ago`
    return date.toLocaleDateString()
  }

  const getStatusColor = (status) => {
    switch (status) {
      case 'healthy':
        return { bg: 'bg-green-400', text: 'text-green-400', label: 'Connected' }
      case 'degraded':
        return { bg: 'bg-yellow-400', text: 'text-yellow-400', label: 'Degraded' }
      case 'unhealthy':
        return { bg: 'bg-red-400', text: 'text-red-400', label: 'Disconnected' }
      default:
        return { bg: 'bg-gray-400', text: 'text-gray-400', label: 'Unknown' }
    }
  }

  if (isLoading) {
    return (
      <div className="card p-4">
        <div className="flex items-center space-x-3">
          <div className="skeleton w-10 h-10 rounded-lg" />
          <div className="flex-1">
            <div className="skeleton h-4 w-24 mb-1" />
            <div className="skeleton h-3 w-16" />
          </div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="card p-4">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-lg bg-red-900/50 flex items-center justify-center">
            <span className="text-xl">!</span>
          </div>
          <div>
            <span className="text-sm font-medium text-white block">OctoBot Signal</span>
            <span className="text-xs text-red-400">Connection Error</span>
          </div>
        </div>
      </div>
    )
  }

  const statusInfo = getStatusColor(health?.status)

  return (
    <div className="card p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          {/* Status Icon */}
          <div className={`w-10 h-10 rounded-lg ${health?.status === 'healthy' ? 'bg-green-900/50' : 'bg-gray-900/50'} flex items-center justify-center`}>
            <span className="text-xl">{health?.status === 'healthy' ? '📡' : '📴'}</span>
          </div>

          {/* Status Text */}
          <div>
            <span className="text-sm font-medium text-white block">OctoBot Signal</span>
            <div className="flex items-center space-x-2">
              <div className={`w-2 h-2 rounded-full ${statusInfo.bg} ${health?.status === 'healthy' ? 'animate-pulse' : ''}`} />
              <span className={`text-xs ${statusInfo.text}`}>{statusInfo.label}</span>
            </div>
          </div>
        </div>

        {/* Stats */}
        <div className="text-right">
          <div className="flex items-center space-x-3">
            <div>
              <span className="text-xs text-gray-500 block">24h Signals</span>
              <span className="text-sm font-bold text-white">{health?.signals_24h || 0}</span>
            </div>
            <div className="w-px h-8 bg-gray-700" />
            <div>
              <span className="text-xs text-gray-500 block">Last Signal</span>
              <span className="text-sm font-mono text-gray-300">
                {formatTime(health?.last_signal_time)}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Database Status */}
      {health?.database && health.database !== 'connected' && (
        <div className="mt-3 pt-3 border-t border-gray-700">
          <div className="flex items-center space-x-2 text-xs">
            <span className="text-red-400">Database: {health.database}</span>
          </div>
        </div>
      )}
    </div>
  )
}

export default SignalHealth
