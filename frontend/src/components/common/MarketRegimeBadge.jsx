import React from 'react'

const regimeConfig = {
  trending_up: { icon: '📈', color: 'text-green-400', bg: 'bg-green-900/30 border-green-700' },
  trending_down: { icon: '📉', color: 'text-red-400', bg: 'bg-red-900/30 border-red-700' },
  ranging: { icon: '➡️', color: 'text-yellow-400', bg: 'bg-yellow-900/30 border-yellow-700' },
  volatile: { icon: '⚡', color: 'text-purple-400', bg: 'bg-purple-900/30 border-purple-700' },
  consolidating: { icon: '🔄', color: 'text-blue-400', bg: 'bg-blue-900/30 border-blue-700' },
  default: { icon: '📊', color: 'text-gray-400', bg: 'bg-gray-700/30 border-gray-600' },
}

function MarketRegimeBadge({ regime, accuracy, showAccuracy = true }) {
  if (!regime) return null

  const normalizedRegime = regime.toLowerCase().replace(/\s+/g, '_')
  const config = regimeConfig[normalizedRegime] || regimeConfig.default
  const displayName = regime.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())

  return (
    <div className={`inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-lg border ${config.bg}`}>
      <span>{config.icon}</span>
      <span className={`font-medium ${config.color}`}>{displayName}</span>
      {showAccuracy && accuracy !== undefined && (
        <span className="text-xs text-gray-400">
          ({(accuracy * 100).toFixed(0)}%)
        </span>
      )}
    </div>
  )
}

export default MarketRegimeBadge
