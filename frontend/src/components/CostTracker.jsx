import React, { useEffect } from 'react'
import { useQuery } from 'react-query'
import { analyticsAPI } from '../services/api'
import { logComponentData, logAnalyticsData } from '../utils/debugLogger'

function CostTracker({ timeRange = '30d' }) {
  const { data: costs, isLoading, isError } = useQuery(
    ['cost-tracker', timeRange],
    () => {
      const days = timeRange === '7d' ? 7 : timeRange === '30d' ? 30 : timeRange === '90d' ? 90 : 365
      return analyticsAPI.getCosts(days)
    },
    {
      select: (res) => {
        console.log('%c[COST TRACKER DEBUG] Raw response:', 'color: #f59e0b', res.data)
        return res.data?.data || res.data
      },
      retry: 2,
      refetchInterval: 60000, // Refresh every minute
    }
  )

  // Debug logging when data loads
  useEffect(() => {
    if (costs) {
      logComponentData('CostTracker', 'costs', costs, { timeRange })
      logAnalyticsData('CostTracker.jsx', 'costs', costs)
      console.log('%c[COST TRACKER DEBUG] Processed costs:', 'color: #22c55e', costs)
      console.log('%c[COST TRACKER DEBUG] Field mapping:', 'color: #3b82f6', {
        raw_total_cost: costs.total_cost,
        raw_total_cost_usd: costs.total_cost_usd,
        raw_avg_cost_per_prediction: costs.avg_cost_per_prediction,
        raw_avg_cost_per_day: costs.avg_cost_per_day,
        raw_total_predictions: costs.total_predictions,
        raw_cost_efficiency: costs.cost_efficiency,
      })
    }
  }, [costs, timeRange])

  if (isLoading) {
    return (
      <div className="card p-6">
        <div className="skeleton h-8 w-32 mb-4" />
        <div className="skeleton h-24" />
      </div>
    )
  }

  if (isError) {
    return (
      <div className="card p-6">
        <h3 className="text-lg font-bold text-white mb-4">Cost Tracking</h3>
        <div className="text-center py-4 text-gray-400">
          Unable to load cost data
        </div>
      </div>
    )
  }

  if (!costs) return null

  // Map backend field names to what the component expects
  // Backend returns: total_cost_usd
  // Frontend expects: total_cost
  const totalCost = costs.total_cost || costs.total_cost_usd || 0

  return (
    <div className="card p-6 space-y-4">
      <h3 className="text-lg font-bold text-white">Cost Tracking</h3>

      {/* Total Cost */}
      <div className="text-center py-6 bg-gray-900/50 rounded-lg">
        <div className="text-5xl font-bold text-purple-400">
          ${totalCost.toFixed(2)}
        </div>
        <div className="text-sm text-gray-400 mt-2">Total API Cost</div>
      </div>

      {/* Cost Breakdown */}
      <div className="space-y-3">
        <div className="flex items-center justify-between p-3 bg-gray-900/50 rounded">
          <span className="text-sm text-gray-400">Cost per Prediction</span>
          <span className="text-sm font-semibold text-white font-mono">
            ${costs.avg_cost_per_prediction?.toFixed(4) || '0.00'}
          </span>
        </div>

        <div className="flex items-center justify-between p-3 bg-gray-900/50 rounded">
          <span className="text-sm text-gray-400">Cost per Day</span>
          <span className="text-sm font-semibold text-white font-mono">
            ${costs.avg_cost_per_day?.toFixed(2) || '0.00'}
          </span>
        </div>

        <div className="flex items-center justify-between p-3 bg-gray-900/50 rounded">
          <span className="text-sm text-gray-400">Total Predictions</span>
          <span className="text-sm font-semibold text-white font-mono">
            {costs.total_predictions || 0}
          </span>
        </div>
      </div>

      {/* Cost Efficiency */}
      {costs.cost_efficiency && (
        <div className="pt-3 border-t border-gray-700">
          <div className="text-xs text-gray-500 mb-2">Cost Efficiency</div>
          <div className="w-full bg-gray-700 rounded-full h-2">
            <div
              className="bg-purple-500 h-2 rounded-full"
              style={{ width: `${Math.min(costs.cost_efficiency * 100, 100)}%` }}
            />
          </div>
          <div className="text-xs text-gray-400 mt-1 text-right">
            {(costs.cost_efficiency * 100).toFixed(0)}% efficient
          </div>
        </div>
      )}
    </div>
  )
}

export default CostTracker
