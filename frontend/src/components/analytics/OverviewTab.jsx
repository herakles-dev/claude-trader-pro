import React, { useEffect } from 'react'
import { useQuery } from 'react-query'
import { analyticsAPI } from '../../services/api'
import { logAnalyticsData } from '../../utils/debugLogger'
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from 'recharts'

const COLORS = {
  primary: '#3b82f6',
  success: '#22c55e',
  danger: '#ef4444',
  warning: '#f59e0b',
  purple: '#a855f7',
}

const PIE_COLORS = [COLORS.success, COLORS.danger, COLORS.warning]

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload || !payload.length) return null

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-3 shadow-xl">
      <p className="text-sm text-gray-400 mb-2">{label}</p>
      {payload.map((entry, index) => (
        <p key={index} className="text-sm font-medium" style={{ color: entry.color }}>
          {entry.name}: {entry.value}
          {entry.unit || ''}
        </p>
      ))}
    </div>
  )
}

function OverviewTab({ timeRange }) {
  const days = timeRange === '7d' ? 7 : timeRange === '30d' ? 30 : timeRange === '90d' ? 90 : 365

  const { data: accuracy, isLoading: accuracyLoading } = useQuery(
    ['analytics-accuracy', timeRange],
    () => analyticsAPI.getAccuracy(timeRange),
    {
      select: (res) => {
        console.log('%c[ANALYTICS DEBUG] Accuracy raw response:', 'color: #f59e0b', res.data)
        return res.data?.data || res.data
      },
      retry: 2,
    }
  )

  const { data: costs } = useQuery(
    ['analytics-costs', timeRange],
    () => analyticsAPI.getCosts(days),
    {
      select: (res) => {
        console.log('%c[ANALYTICS DEBUG] Costs raw response:', 'color: #f59e0b', res.data)
        return res.data?.data || res.data
      }
    }
  )

  const { data: distribution } = useQuery(
    'analytics-distribution',
    () => analyticsAPI.getDistribution(),
    {
      select: (res) => {
        console.log('%c[ANALYTICS DEBUG] Distribution raw response:', 'color: #f59e0b', res.data)
        return res.data?.data || res.data
      },
      retry: 2,
    }
  )

  const { data: dailyStats } = useQuery(
    ['analytics-daily', timeRange],
    () => analyticsAPI.getDailyStats(days),
    {
      select: (res) => {
        console.log('%c[ANALYTICS DEBUG] Daily stats raw response:', 'color: #f59e0b', res.data)
        return res.data?.data || res.data
      },
      retry: 2,
    }
  )

  // Debug logging for all analytics data
  useEffect(() => {
    console.group('%c[ANALYTICS OVERVIEW] Data Summary', 'color: #8b5cf6; font-weight: bold')
    if (accuracy) {
      logAnalyticsData('OverviewTab', 'accuracy', accuracy)
      console.log('%c[ANALYTICS DEBUG] Accuracy processed:', 'color: #22c55e', accuracy)
    }
    if (costs) {
      logAnalyticsData('OverviewTab', 'costs', costs)
      console.log('%c[ANALYTICS DEBUG] Costs processed:', 'color: #22c55e', costs)
    }
    if (distribution) {
      logAnalyticsData('OverviewTab', 'distribution', distribution)
      console.log('%c[ANALYTICS DEBUG] Distribution processed:', 'color: #22c55e', distribution)
    }
    if (dailyStats) {
      logAnalyticsData('OverviewTab', 'dailyStats', dailyStats)
      console.log('%c[ANALYTICS DEBUG] Daily stats processed:', 'color: #22c55e', dailyStats)
      console.log('%c[ANALYTICS DEBUG] Daily stats count:', 'color: #3b82f6', dailyStats?.length || 0)
    }
    console.groupEnd()
  }, [accuracy, costs, distribution, dailyStats])

  // Map backend field names to what the component expects
  // Backend accuracy returns: total_evaluated, accuracy_percentage (as %)
  // Backend costs returns: total_cost_usd, total_predictions, avg_cost_per_prediction
  // Use costs.total_predictions as fallback since accuracy endpoint may show 0
  const totalPredictions = accuracy?.total_predictions ||
    accuracy?.total_evaluated ||
    costs?.total_predictions ||
    (dailyStats ? dailyStats.reduce((sum, d) => sum + (d.predictions || 0), 0) : 0)

  const overallAccuracy = accuracy?.overall_accuracy != null
    ? accuracy.overall_accuracy
    : (accuracy?.accuracy_percentage != null ? accuracy.accuracy_percentage / 100 : null)

  // Calculate predictions per day from daily stats if not provided
  const predictionsPerDay = accuracy?.predictions_per_day ||
    (dailyStats && dailyStats.length > 0
      ? dailyStats.reduce((sum, d) => sum + (d.predictions || 0), 0) / dailyStats.length
      : 0)

  // Calculate avg confidence from daily stats if not in accuracy response
  const avgConfidence = accuracy?.avg_confidence ||
    (dailyStats && dailyStats.length > 0
      ? dailyStats.reduce((sum, d) => sum + parseFloat(d.avg_confidence || 0), 0) / dailyStats.length / 100
      : null)

  // Map cost field names
  const totalCost = costs?.total_cost || costs?.total_cost_usd || 0
  const avgCostPerPrediction = costs?.avg_cost_per_prediction || 0

  if (accuracyLoading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="card p-6">
              <div className="skeleton h-4 w-24 mb-2" />
              <div className="skeleton h-8 w-32" />
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Key Metrics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="stat-card">
          <div className="stat-label">Overall Accuracy</div>
          <div className="stat-value text-green-400">
            {overallAccuracy != null
              ? `${(overallAccuracy * 100).toFixed(1)}%`
              : '--'}
          </div>
          <div className="text-xs text-gray-500 mt-2">
            {totalPredictions} predictions analyzed
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-label">Total Predictions</div>
          <div className="stat-value text-blue-400">
            {totalPredictions}
          </div>
          <div className="text-xs text-gray-500 mt-2">
            {predictionsPerDay.toFixed(1)} per day avg
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-label">Total Cost</div>
          <div className="stat-value text-purple-400">
            ${totalCost.toFixed(2)}
          </div>
          <div className="text-xs text-gray-500 mt-2">
            ${avgCostPerPrediction.toFixed(4)} per prediction
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-label">Avg Confidence</div>
          <div className="stat-value text-yellow-400">
            {avgConfidence != null
              ? `${(avgConfidence * 100).toFixed(1)}%`
              : '--'}
          </div>
          <div className="text-xs text-gray-500 mt-2">
            Across all predictions
          </div>
        </div>
      </div>

      {/* Charts Row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Accuracy Over Time */}
        <div className="card p-6">
          <h3 className="text-xl font-bold text-white mb-4">
            Accuracy Over Time
          </h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={dailyStats || []}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="date" stroke="#9ca3af" style={{ fontSize: '12px' }} />
              <YAxis stroke="#9ca3af" style={{ fontSize: '12px' }} />
              <Tooltip content={<CustomTooltip />} />
              <Legend />
              <Line
                type="monotone"
                dataKey="accuracy"
                name="Accuracy %"
                stroke={COLORS.success}
                strokeWidth={2}
                dot={{ fill: COLORS.success, r: 4 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Predictions Per Day */}
        <div className="card p-6">
          <h3 className="text-xl font-bold text-white mb-4">
            Predictions Per Day
          </h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={dailyStats || []}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="date" stroke="#9ca3af" style={{ fontSize: '12px' }} />
              <YAxis stroke="#9ca3af" style={{ fontSize: '12px' }} />
              <Tooltip content={<CustomTooltip />} />
              <Legend />
              <Bar
                dataKey="predictions"
                name="Predictions"
                fill={COLORS.primary}
                radius={[8, 8, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Charts Row 2 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Cost Per Day */}
        <div className="card p-6">
          <h3 className="text-xl font-bold text-white mb-4">
            Cost Per Day ($)
          </h3>
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={dailyStats || []}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="date" stroke="#9ca3af" style={{ fontSize: '12px' }} />
              <YAxis stroke="#9ca3af" style={{ fontSize: '12px' }} />
              <Tooltip content={<CustomTooltip />} />
              <Legend />
              <Area
                type="monotone"
                dataKey="cost"
                name="Cost"
                stroke={COLORS.purple}
                fill={COLORS.purple}
                fillOpacity={0.3}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Direction Distribution */}
        <div className="card p-6">
          <h3 className="text-xl font-bold text-white mb-4">
            Prediction Direction Distribution
          </h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={distribution?.directions || []}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ name, percent }) =>
                  `${name}: ${(percent * 100).toFixed(0)}%`
                }
                outerRadius={100}
                fill="#8884d8"
                dataKey="value"
              >
                {(distribution?.directions || []).map((entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={PIE_COLORS[index % PIE_COLORS.length]}
                  />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Strategy Performance Table */}
      {accuracy?.strategy_breakdown && (
        <div className="card overflow-hidden">
          <div className="p-6 border-b border-gray-700">
            <h3 className="text-xl font-bold text-white">
              Strategy Performance
            </h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-900">
                <tr>
                  <th className="px-6 py-4 text-left text-xs font-medium text-gray-400 uppercase">
                    Strategy
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-medium text-gray-400 uppercase">
                    Predictions
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-medium text-gray-400 uppercase">
                    Accuracy
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-medium text-gray-400 uppercase">
                    Avg Confidence
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-700">
                {Object.entries(accuracy.strategy_breakdown).map(
                  ([strategy, stats]) => (
                    <tr key={strategy} className="hover:bg-gray-800/50">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className="badge badge-info capitalize">
                          {strategy}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-300">
                        {stats.count}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className="font-semibold text-green-400">
                          {(stats.accuracy * 100).toFixed(1)}%
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-300">
                        {(stats.avg_confidence * 100).toFixed(1)}%
                      </td>
                    </tr>
                  )
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

export default OverviewTab
