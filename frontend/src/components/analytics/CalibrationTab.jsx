import React from 'react'
import { useCalibrationAnalytics } from '../../hooks/useAnalytics'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'

const COLORS = {
  primary: '#3b82f6',
  success: '#22c55e',
  danger: '#ef4444',
  warning: '#f59e0b',
  purple: '#a855f7',
  gray: '#6b7280',
}

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload || !payload.length) return null
  const data = payload[0].payload
  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-3 shadow-xl">
      <p className="text-sm text-white font-medium mb-1">
        Stated: {(data.stated_confidence * 100).toFixed(0)}%
      </p>
      <p className="text-sm text-gray-400">
        Actual: <span className="text-green-400">{(data.actual_accuracy * 100).toFixed(1)}%</span>
      </p>
      <p className="text-xs text-gray-500 mt-1">
        {data.sample_count || 0} samples
      </p>
      {data.calibration_error !== undefined && (
        <p className="text-xs mt-1">
          Error: <span className={data.calibration_error > 0 ? 'text-yellow-400' : 'text-blue-400'}>
            {data.calibration_error > 0 ? '+' : ''}{(data.calibration_error * 100).toFixed(1)}%
          </span>
        </p>
      )}
    </div>
  )
}

function CalibrationTab({ timeRange }) {
  const days = timeRange === '7d' ? 7 : timeRange === '30d' ? 30 : timeRange === '90d' ? 90 : 365
  const { data, isLoading, isError } = useCalibrationAnalytics({ days })

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="card p-6">
          <div className="skeleton h-6 w-64 mb-4" />
          <div className="skeleton h-80" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="card p-6">
              <div className="skeleton h-4 w-24 mb-2" />
              <div className="skeleton h-8 w-32" />
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (isError) {
    return (
      <div className="card p-6 text-center">
        <div className="text-red-400 mb-2">Failed to load calibration analytics</div>
        <p className="text-gray-500 text-sm">Please try again later</p>
      </div>
    )
  }

  // Transform buckets for chart - add perfect calibration line
  // API returns confidence_range as string "0.40-0.50" and stated_confidence as number
  const chartData = data?.buckets
    ? data.buckets.map(bucket => ({
        stated_confidence: bucket.stated_confidence || 0,
        actual_accuracy: bucket.actual_accuracy || 0,
        sample_count: bucket.count || bucket.sample_count || 0,
        calibration_error: bucket.calibration_error || ((bucket.actual_accuracy || 0) - (bucket.stated_confidence || 0)),
        confidence_range: bucket.confidence_range || '',
      }))
    : []

  // Compute summary stats
  const totalSamples = chartData.reduce((sum, b) => sum + b.sample_count, 0)
  const bestBucket = [...chartData].sort((a, b) => Math.abs(a.calibration_error) - Math.abs(b.calibration_error))[0]
  const worstBucket = [...chartData].sort((a, b) => Math.abs(b.calibration_error) - Math.abs(a.calibration_error))[0]

  // Create reference line data for perfect calibration
  const perfectCalibration = [
    { stated_confidence: 0, actual_accuracy: 0 },
    { stated_confidence: 1, actual_accuracy: 1 },
  ]

  const getCalibrationStatus = (error) => {
    if (Math.abs(error) <= 0.05) return { text: 'Well Calibrated', color: 'text-green-400' }
    if (error > 0.05) return { text: 'Underconfident', color: 'text-blue-400' }
    return { text: 'Overconfident', color: 'text-yellow-400' }
  }

  const overallStatus = getCalibrationStatus(data?.overall_calibration_error || 0)

  return (
    <div className="space-y-6">
      {/* Calibration Curve */}
      <div className="card p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-xl font-bold text-white">Confidence Calibration Curve</h3>
          <div className="flex items-center space-x-4 text-sm">
            <div className="flex items-center space-x-2">
              <div className="w-3 h-0.5 bg-gray-500"></div>
              <span className="text-gray-400">Perfect</span>
            </div>
            <div className="flex items-center space-x-2">
              <div className="w-3 h-0.5 bg-blue-500"></div>
              <span className="text-gray-400">Actual</span>
            </div>
          </div>
        </div>

        {chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height={350}>
            <LineChart margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis
                dataKey="stated_confidence"
                type="number"
                domain={[0, 1]}
                tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                stroke="#9ca3af"
                label={{ value: 'Stated Confidence', position: 'bottom', fill: '#9ca3af', fontSize: 12 }}
              />
              <YAxis
                domain={[0, 1]}
                tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                stroke="#9ca3af"
                label={{ value: 'Actual Accuracy', angle: -90, position: 'insideLeft', fill: '#9ca3af', fontSize: 12 }}
              />
              <Tooltip content={<CustomTooltip />} />
              {/* Perfect calibration reference line */}
              <Line
                data={perfectCalibration}
                dataKey="actual_accuracy"
                stroke={COLORS.gray}
                strokeWidth={2}
                strokeDasharray="5 5"
                dot={false}
                isAnimationActive={false}
              />
              {/* Actual calibration */}
              <Line
                data={chartData}
                dataKey="actual_accuracy"
                stroke={COLORS.primary}
                strokeWidth={3}
                dot={{ fill: COLORS.primary, r: 6 }}
                activeDot={{ r: 8, fill: COLORS.primary }}
              />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-80 flex items-center justify-center text-gray-500">
            No calibration data available
          </div>
        )}
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="stat-card">
          <div className="stat-label">Overall Calibration</div>
          <div className={`stat-value text-lg ${overallStatus.color}`}>
            {overallStatus.text}
          </div>
          <div className="text-xs text-gray-500">
            {data?.overall_calibration_error !== undefined
              ? `${Math.abs(data.overall_calibration_error * 100).toFixed(1)}% error`
              : 'No data'}
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-label">Best Calibrated Range</div>
          <div className="stat-value text-green-400 text-lg">
            {bestBucket?.confidence_range || '--'}
          </div>
          <div className="text-xs text-gray-500">
            {bestBucket ? `${Math.abs(bestBucket.calibration_error * 100).toFixed(1)}% error` : 'Lowest calibration error'}
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-label">Worst Calibrated Range</div>
          <div className="stat-value text-red-400 text-lg">
            {worstBucket?.confidence_range || '--'}
          </div>
          <div className="text-xs text-gray-500">
            {worstBucket ? `${Math.abs(worstBucket.calibration_error * 100).toFixed(1)}% error` : 'Highest calibration error'}
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-label">Total Samples</div>
          <div className="stat-value text-blue-400 text-lg">
            {totalSamples}
          </div>
          <div className="text-xs text-gray-500">
            Evaluated predictions
          </div>
        </div>
      </div>

      {/* Bucket Details Table */}
      {chartData.length > 0 && (
        <div className="card overflow-hidden">
          <div className="p-6 border-b border-gray-700">
            <h3 className="text-lg font-bold text-white">Calibration by Confidence Range</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-900">
                <tr>
                  <th className="px-6 py-4 text-left text-xs font-medium text-gray-400 uppercase">
                    Confidence Range
                  </th>
                  <th className="px-6 py-4 text-center text-xs font-medium text-gray-400 uppercase">
                    Samples
                  </th>
                  <th className="px-6 py-4 text-center text-xs font-medium text-gray-400 uppercase">
                    Actual Accuracy
                  </th>
                  <th className="px-6 py-4 text-center text-xs font-medium text-gray-400 uppercase">
                    Error
                  </th>
                  <th className="px-6 py-4 text-center text-xs font-medium text-gray-400 uppercase">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-700">
                {chartData.map((bucket, index) => {
                  const status = getCalibrationStatus(bucket.calibration_error)
                  return (
                    <tr key={index} className="hover:bg-gray-800/50">
                      <td className="px-6 py-4 whitespace-nowrap font-medium text-white">
                        {bucket.confidence_range || `${(bucket.stated_confidence * 100).toFixed(0)}%`}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-center text-gray-300">
                        {bucket.sample_count}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-center">
                        <span className={`font-semibold ${
                          bucket.actual_accuracy >= 0.6 ? 'text-green-400' :
                          bucket.actual_accuracy >= 0.4 ? 'text-yellow-400' : 'text-red-400'
                        }`}>
                          {(bucket.actual_accuracy * 100).toFixed(1)}%
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-center">
                        <span className={bucket.calibration_error > 0 ? 'text-blue-400' : 'text-yellow-400'}>
                          {bucket.calibration_error > 0 ? '+' : ''}
                          {(bucket.calibration_error * 100).toFixed(1)}%
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-center">
                        <span className={`text-sm ${status.color}`}>
                          {status.text}
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Interpretation Guide */}
      <div className="card p-6 bg-gray-800/50">
        <h4 className="text-sm font-medium text-gray-400 mb-3">Understanding Calibration</h4>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
          <div className="flex items-start space-x-2">
            <span className="text-green-400">●</span>
            <div>
              <span className="text-gray-300 font-medium">Well Calibrated</span>
              <p className="text-gray-500 text-xs mt-0.5">Stated confidence matches actual accuracy (&lt;5% error)</p>
            </div>
          </div>
          <div className="flex items-start space-x-2">
            <span className="text-blue-400">●</span>
            <div>
              <span className="text-gray-300 font-medium">Underconfident</span>
              <p className="text-gray-500 text-xs mt-0.5">Actual accuracy higher than stated (conservative)</p>
            </div>
          </div>
          <div className="flex items-start space-x-2">
            <span className="text-yellow-400">●</span>
            <div>
              <span className="text-gray-300 font-medium">Overconfident</span>
              <p className="text-gray-500 text-xs mt-0.5">Actual accuracy lower than stated (optimistic)</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default CalibrationTab
