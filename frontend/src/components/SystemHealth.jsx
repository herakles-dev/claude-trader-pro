import React from 'react'
import { useQuery } from 'react-query'
import { systemAPI } from '../services/api'
import { useWebSocket } from '../hooks/useWebSocket'

function SystemHealth() {
  const { connected: wsConnected } = useWebSocket({ autoConnect: true })
  
  const { data: health, isLoading } = useQuery(
    'system-health',
    () => systemAPI.getHealth(),
    {
      refetchInterval: 30000, // 30 seconds
      select: (response) => response.data.data,
    }
  )

  const services = [
    {
      name: 'API Gateway',
      status: health?.status === 'healthy' || health?.status === 'degraded' ? 'online' : 'offline',
      icon: '🌐',
    },
    {
      name: 'WebSocket',
      status: wsConnected ? 'online' : 'offline',
      icon: '⚡',
    },
    {
      name: 'Market Data',
      status: health?.claudeEngine === 'available' ? 'online' : 'offline',
      icon: '📊',
    },
    {
      name: 'AI Engine',
      status: health?.claudeEngine === 'available' ? 'online' : 'offline',
      icon: '🤖',
    },
  ]

  const getStatusColor = (status) => {
    switch (status) {
      case 'online':
        return 'bg-green-400'
      case 'degraded':
        return 'bg-yellow-400'
      case 'offline':
        return 'bg-red-400'
      default:
        return 'bg-gray-400'
    }
  }

  const getStatusText = (status) => {
    switch (status) {
      case 'online':
        return 'text-green-400'
      case 'degraded':
        return 'text-yellow-400'
      case 'offline':
        return 'text-red-400'
      default:
        return 'text-gray-400'
    }
  }

  if (isLoading) {
    return (
      <div className="card p-6">
        <div className="skeleton h-8 w-32 mb-4" />
        <div className="space-y-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="skeleton h-12" />
          ))}
        </div>
      </div>
    )
  }

  const overallStatus = services.every((s) => s.status === 'online')
    ? 'online'
    : services.some((s) => s.status === 'offline')
    ? 'degraded'
    : 'offline'

  return (
    <div className="card p-6 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-xl font-bold text-white">System Status</h3>
        <div className="flex items-center space-x-2">
          <div className={`w-2 h-2 rounded-full ${getStatusColor(overallStatus)} animate-pulse`} />
          <span className={`text-sm font-medium ${getStatusText(overallStatus)}`}>
            {overallStatus === 'online' ? 'All Systems Operational' : 'Issues Detected'}
          </span>
        </div>
      </div>

      {/* Services List */}
      <div className="space-y-2">
        {services.map((service) => (
          <div
            key={service.name}
            className="flex items-center justify-between p-3 bg-gray-900/50 rounded-lg hover:bg-gray-900/70 transition-colors"
          >
            <div className="flex items-center space-x-3">
              <span className="text-2xl">{service.icon}</span>
              <span className="text-sm font-medium text-gray-200">
                {service.name}
              </span>
            </div>
            <div className="flex items-center space-x-2">
              <div className={`w-2 h-2 rounded-full ${getStatusColor(service.status)}`} />
              <span className={`text-sm font-medium ${getStatusText(service.status)}`}>
                {service.status}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* System Info */}
      {health?.uptime && (
        <div className="pt-4 border-t border-gray-700">
          <div className="grid grid-cols-2 gap-4 text-xs text-gray-400">
            <div>
              <span className="block text-gray-500">Uptime</span>
              <span className="font-mono text-gray-300">
                {Math.floor(health.uptime / 3600)}h {Math.floor((health.uptime % 3600) / 60)}m
              </span>
            </div>
            <div>
              <span className="block text-gray-500">Version</span>
              <span className="font-mono text-gray-300">
                {health.version || 'v1.0.0'}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default SystemHealth
