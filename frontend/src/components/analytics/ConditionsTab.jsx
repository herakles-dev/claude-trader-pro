import React from 'react'
import { useConditionsAnalytics } from '../../hooks/useAnalytics'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts'

const COLORS = {
  primary: '#3b82f6',
  success: '#22c55e',
  danger: '#ef4444',
  warning: '#f59e0b',
  purple: '#a855f7',
  cyan: '#06b6d4',
}

const getAccuracyColor = (accuracy) => {
  if (accuracy >= 0.7) return COLORS.success
  if (accuracy >= 0.5) return COLORS.warning
  return COLORS.danger
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload || !payload.length) return null
  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-3 shadow-xl">
      <p className="text-sm text-white font-medium mb-1">{label}</p>
      <p className="text-sm text-gray-400">
        Accuracy: <span className="text-green-400">{(payload[0].value * 100).toFixed(1)}%</span>
      </p>
      {payload[0].payload.predictions && (
        <p className="text-xs text-gray-500 mt-1">
          {payload[0].payload.predictions} predictions
        </p>
      )}
    </div>
  )
}

function ConditionsTab({ timeRange }) {
  const days = timeRange === '7d' ? 7 : timeRange === '30d' ? 30 : timeRange === '90d' ? 90 : 365
  const { data, isLoading, isError } = useConditionsAnalytics({ days })

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {[1, 2].map((i) => (
            <div key={i} className="card p-6">
              <div className="skeleton h-6 w-48 mb-4" />
              <div className="skeleton h-64" />
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (isError) {
    return (
      <div className="card p-6 text-center">
        <div className="text-red-400 mb-2">Failed to load conditions analytics</div>
        <p className="text-gray-500 text-sm">Please try again later</p>
      </div>
    )
  }

  // Transform market regimes data for chart (API returns array, not object)
  const regimeData = Array.isArray(data?.market_regimes)
    ? data.market_regimes.map((item) => ({
        name: (item.regime || '').replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
        accuracy: (item.accuracy_pct || 0) / 100,  // Convert percentage to decimal
        predictions: item.count || 0,
      }))
    : []

  // Transform volatility data for chart (API returns volatility_regimes as array)
  const volatilityData = Array.isArray(data?.volatility_regimes)
    ? data.volatility_regimes.map((item) => ({
        name: (item.regime || '').replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
        accuracy: (item.accuracy_pct || 0) / 100,  // Convert percentage to decimal
        predictions: item.count || 0,
      }))
    : []

  // Compute best and worst conditions from regimeData
  const sortedRegimes = [...regimeData].sort((a, b) => b.accuracy - a.accuracy)
  const bestCondition = sortedRegimes[0] || null
  const worstCondition = sortedRegimes[sortedRegimes.length - 1] || null

  return (
    <div className="space-y-6">
      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Market Regime Accuracy */}
        <div className="card p-6">
          <h3 className="text-xl font-bold text-white mb-4">Market Regime Accuracy</h3>
          {regimeData.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={regimeData} layout="vertical" margin={{ left: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis
                  type="number"
                  domain={[0, 1]}
                  tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                  stroke="#9ca3af"
                />
                <YAxis
                  dataKey="name"
                  type="category"
                  width={100}
                  stroke="#9ca3af"
                  tick={{ fontSize: 12 }}
                />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="accuracy" radius={[0, 4, 4, 0]}>
                  {regimeData.map((entry, index) => (
                    <Cell key={index} fill={getAccuracyColor(entry.accuracy)} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-64 flex items-center justify-center text-gray-500">
              No regime data available
            </div>
          )}
        </div>

        {/* Volatility Impact */}
        <div className="card p-6">
          <h3 className="text-xl font-bold text-white mb-4">Volatility Impact</h3>
          {volatilityData.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={volatilityData} layout="vertical" margin={{ left: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis
                  type="number"
                  domain={[0, 1]}
                  tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                  stroke="#9ca3af"
                />
                <YAxis
                  dataKey="name"
                  type="category"
                  width={80}
                  stroke="#9ca3af"
                  tick={{ fontSize: 12 }}
                />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="accuracy" radius={[0, 4, 4, 0]}>
                  {volatilityData.map((entry, index) => (
                    <Cell key={index} fill={getAccuracyColor(entry.accuracy)} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-64 flex items-center justify-center text-gray-500">
              No volatility data available
            </div>
          )}
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="stat-card">
          <div className="stat-label">Best Condition</div>
          <div className="stat-value text-green-400 text-lg">
            {bestCondition?.name || '--'}
          </div>
          <div className="text-xs text-gray-500">
            {bestCondition?.accuracy
              ? `${(bestCondition.accuracy * 100).toFixed(1)}% accuracy`
              : 'No data'}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Worst Condition</div>
          <div className="stat-value text-red-400 text-lg">
            {worstCondition?.name || '--'}
          </div>
          <div className="text-xs text-gray-500">
            {worstCondition?.accuracy
              ? `${(worstCondition.accuracy * 100).toFixed(1)}% accuracy`
              : 'No data'}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Total Evaluated</div>
          <div className="stat-value text-blue-400 text-lg">
            {data?.total_evaluated || 0}
          </div>
          <div className="text-xs text-gray-500">
            Predictions analyzed
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Days Analyzed</div>
          <div className="stat-value text-purple-400 text-lg">
            {data?.days_analyzed || 0}
          </div>
          <div className="text-xs text-gray-500">
            Time range covered
          </div>
        </div>
      </div>

      {/* AI Recommendations */}
      {data?.recommendations && data.recommendations.length > 0 && (
        <div className="card p-6">
          <h3 className="text-lg font-bold text-white mb-4 flex items-center">
            <span className="mr-2">🤖</span>
            AI Recommendations
          </h3>
          <ul className="space-y-2">
            {data.recommendations.map((rec, index) => (
              <li key={index} className="flex items-start space-x-2 text-gray-300">
                <span className="text-blue-400 mt-0.5">•</span>
                <span>{rec}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Data Status */}
      {data?.data_available === false && (
        <div className="card p-6 bg-yellow-900/20 border border-yellow-700/30">
          <p className="text-yellow-400 text-sm">
            Market context data is still being collected. More detailed analytics will appear as predictions accumulate.
          </p>
        </div>
      )}
    </div>
  )
}

export default ConditionsTab
