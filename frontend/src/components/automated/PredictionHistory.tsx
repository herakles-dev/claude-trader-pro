import React, { useState } from 'react'
import { formatRelativeTime } from '../../utils/formatters'

interface Prediction {
  id: string
  createdAt: string
  predictionType: 'up' | 'down'
  confidence: number
  cycleHour: number
  actualOutcome: 'up' | 'down' | null
  wasCorrect: boolean | null
  totalCost: number
  symbol?: string
}

interface PredictionHistoryProps {
  predictions: Prediction[]
  totalCount: number
  page: number
  limit: number
  onPageChange: (page: number) => void
  onLimitChange: (limit: number) => void
  onFilterChange: (filters: any) => void
  loading?: boolean
}

interface Filters {
  symbol: string
  dateRange: { start: string; end: string }
  accuracy: 'all' | 'correct' | 'incorrect' | 'pending'
}

const PredictionHistory: React.FC<PredictionHistoryProps> = ({
  predictions,
  totalCount,
  page,
  limit,
  onPageChange,
  onLimitChange,
  onFilterChange,
  loading = false,
}) => {
  const [filters, setFilters] = useState<Filters>({
    symbol: 'all',
    dateRange: { start: '', end: '' },
    accuracy: 'all',
  })

  const [sortColumn, setSortColumn] = useState<'createdAt' | 'confidence'>('createdAt')
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc')

  // Calculate summary stats
  const summaryStats = React.useMemo(() => {
    const total = predictions.length
    const correct = predictions.filter((p) => p.wasCorrect === true).length
    const accuracy = total > 0 ? (correct / total) * 100 : 0
    const totalCost = predictions.reduce((sum, p) => sum + p.totalCost, 0)
    const avgConfidence =
      total > 0
        ? predictions.reduce((sum, p) => sum + p.confidence, 0) / total
        : 0

    return {
      total,
      accuracy: accuracy.toFixed(1),
      totalCost: totalCost.toFixed(4),
      avgConfidence: avgConfidence.toFixed(1),
    }
  }, [predictions])

  const handleFilterChange = (key: keyof Filters, value: any) => {
    const newFilters = { ...filters, [key]: value }
    setFilters(newFilters)
    onFilterChange(newFilters)
  }

  const handleSort = (column: 'createdAt' | 'confidence') => {
    if (sortColumn === column) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc')
    } else {
      setSortColumn(column)
      setSortDirection('desc')
    }
  }

  const sortedPredictions = React.useMemo(() => {
    return [...predictions].sort((a, b) => {
      const aValue = sortColumn === 'createdAt' ? new Date(a.createdAt).getTime() : a.confidence
      const bValue = sortColumn === 'createdAt' ? new Date(b.createdAt).getTime() : b.confidence
      return sortDirection === 'asc' ? aValue - bValue : bValue - aValue
    })
  }, [predictions, sortColumn, sortDirection])

  const totalPages = Math.ceil(totalCount / limit)

  const getDirectionIcon = (type: 'up' | 'down') => {
    return type === 'up' ? '↑' : '↓'
  }

  const getDirectionColor = (type: 'up' | 'down') => {
    return type === 'up' ? 'text-green-400' : 'text-red-400'
  }

  const getAccuracyBadge = (wasCorrect: boolean | null) => {
    if (wasCorrect === null) {
      return <span className="badge badge-warning">Pending</span>
    }
    return wasCorrect ? (
      <span className="badge bg-green-600 text-white">✓ Correct</span>
    ) : (
      <span className="badge bg-red-600 text-white">✗ Incorrect</span>
    )
  }

  const getCycleHourBadge = (hour: number) => {
    const colors = [
      'bg-blue-600',
      'bg-purple-600',
      'bg-indigo-600',
      'bg-violet-600',
    ]
    return (
      <span className={`badge ${colors[hour - 1] || 'bg-gray-600'} text-white`}>
        H{hour}
      </span>
    )
  }

  if (loading) {
    return (
      <div className="card p-6 space-y-4">
        <div className="skeleton h-8 w-64 mb-4" />
        <div className="skeleton h-20 mb-4" />
        <div className="skeleton h-12 mb-4" />
        <div className="skeleton h-96" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="card p-4">
          <div className="text-sm text-gray-400 mb-1">Total Predictions</div>
          <div className="text-2xl font-bold text-white">{summaryStats.total}</div>
        </div>
        <div className="card p-4">
          <div className="text-sm text-gray-400 mb-1">Accuracy</div>
          <div className="text-2xl font-bold text-green-400">
            {summaryStats.accuracy}%
          </div>
        </div>
        <div className="card p-4">
          <div className="text-sm text-gray-400 mb-1">Total Cost</div>
          <div className="text-2xl font-bold text-blue-400">
            ${summaryStats.totalCost}
          </div>
        </div>
        <div className="card p-4">
          <div className="text-sm text-gray-400 mb-1">Avg Confidence</div>
          <div className="text-2xl font-bold text-purple-400">
            {summaryStats.avgConfidence}%
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="card p-6">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-400 mb-2">
              Symbol
            </label>
            <select
              value={filters.symbol}
              onChange={(e) => handleFilterChange('symbol', e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="all">All Symbols</option>
              <option value="BTC/USDT">BTC/USDT</option>
              <option value="ETH/USDT">ETH/USDT</option>
              <option value="SOL/USDT">SOL/USDT</option>
              <option value="XRP/USDT">XRP/USDT</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-400 mb-2">
              Start Date
            </label>
            <input
              type="date"
              value={filters.dateRange.start}
              onChange={(e) =>
                handleFilterChange('dateRange', {
                  ...filters.dateRange,
                  start: e.target.value,
                })
              }
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-400 mb-2">
              End Date
            </label>
            <input
              type="date"
              value={filters.dateRange.end}
              onChange={(e) =>
                handleFilterChange('dateRange', {
                  ...filters.dateRange,
                  end: e.target.value,
                })
              }
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-400 mb-2">
              Accuracy
            </label>
            <select
              value={filters.accuracy}
              onChange={(e) => handleFilterChange('accuracy', e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="all">All</option>
              <option value="correct">Correct Only</option>
              <option value="incorrect">Incorrect Only</option>
              <option value="pending">Pending Only</option>
            </select>
          </div>
        </div>
      </div>

      {/* Table - Desktop View */}
      <div className="card overflow-hidden hidden md:block">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-800/50 border-b border-gray-700">
              <tr>
                <th
                  className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider cursor-pointer hover:text-white"
                  onClick={() => handleSort('createdAt')}
                >
                  Timestamp{' '}
                  {sortColumn === 'createdAt' && (
                    <span>{sortDirection === 'asc' ? '↑' : '↓'}</span>
                  )}
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                  Prediction
                </th>
                <th
                  className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider cursor-pointer hover:text-white"
                  onClick={() => handleSort('confidence')}
                >
                  Confidence{' '}
                  {sortColumn === 'confidence' && (
                    <span>{sortDirection === 'asc' ? '↑' : '↓'}</span>
                  )}
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                  Cycle
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                  Actual
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                  Result
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                  Cost
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-700">
              {sortedPredictions.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-gray-400">
                    No predictions found
                  </td>
                </tr>
              ) : (
                sortedPredictions.map((prediction) => (
                  <tr
                    key={prediction.id}
                    className="hover:bg-gray-800/30 transition-colors"
                  >
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-300">
                      {formatRelativeTime(prediction.createdAt)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span
                        className={`text-2xl font-bold ${getDirectionColor(
                          prediction.predictionType
                        )}`}
                      >
                        {getDirectionIcon(prediction.predictionType)}{' '}
                        {prediction.predictionType.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="w-full bg-gray-700 rounded-full h-2.5 mb-1">
                        <div
                          className="bg-blue-500 h-2.5 rounded-full"
                          style={{ width: `${prediction.confidence}%` }}
                        />
                      </div>
                      <span className="text-xs text-gray-400">
                        {prediction.confidence.toFixed(1)}%
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {getCycleHourBadge(prediction.cycleHour)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {prediction.actualOutcome ? (
                        <span
                          className={`text-xl font-bold ${getDirectionColor(
                            prediction.actualOutcome
                          )}`}
                        >
                          {getDirectionIcon(prediction.actualOutcome)}
                        </span>
                      ) : (
                        <span className="text-gray-500">-</span>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {getAccuracyBadge(prediction.wasCorrect)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-300 font-mono">
                      ${prediction.totalCost.toFixed(4)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Card View - Mobile */}
      <div className="md:hidden space-y-4">
        {sortedPredictions.length === 0 ? (
          <div className="card p-8 text-center text-gray-400">
            No predictions found
          </div>
        ) : (
          sortedPredictions.map((prediction) => (
            <div key={prediction.id} className="card p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-400">
                  {formatRelativeTime(prediction.createdAt)}
                </span>
                {getCycleHourBadge(prediction.cycleHour)}
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <span
                    className={`text-2xl font-bold ${getDirectionColor(
                      prediction.predictionType
                    )}`}
                  >
                    {getDirectionIcon(prediction.predictionType)}{' '}
                    {prediction.predictionType.toUpperCase()}
                  </span>
                </div>
                <div className="text-right">
                  <div className="text-xs text-gray-400 mb-1">Confidence</div>
                  <div className="text-lg font-bold text-white">
                    {prediction.confidence.toFixed(1)}%
                  </div>
                </div>
              </div>

              <div className="w-full bg-gray-700 rounded-full h-2">
                <div
                  className="bg-blue-500 h-2 rounded-full"
                  style={{ width: `${prediction.confidence}%` }}
                />
              </div>

              <div className="flex items-center justify-between pt-2 border-t border-gray-700">
                <div className="flex items-center space-x-2">
                  <span className="text-sm text-gray-400">Actual:</span>
                  {prediction.actualOutcome ? (
                    <span
                      className={`text-xl font-bold ${getDirectionColor(
                        prediction.actualOutcome
                      )}`}
                    >
                      {getDirectionIcon(prediction.actualOutcome)}
                    </span>
                  ) : (
                    <span className="text-gray-500">Pending</span>
                  )}
                </div>
                {getAccuracyBadge(prediction.wasCorrect)}
              </div>

              <div className="text-xs text-gray-500 font-mono">
                Cost: ${prediction.totalCost.toFixed(4)}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Pagination */}
      <div className="card p-4">
        <div className="flex flex-col md:flex-row items-center justify-between space-y-4 md:space-y-0">
          <div className="flex items-center space-x-2">
            <span className="text-sm text-gray-400">Show:</span>
            <select
              value={limit}
              onChange={(e) => onLimitChange(Number(e.target.value))}
              className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1 text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value={20}>20</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
            </select>
            <span className="text-sm text-gray-400">
              of {totalCount} predictions
            </span>
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={() => onPageChange(page - 1)}
              disabled={page === 1}
              className="px-3 py-1 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-700 transition-colors"
            >
              Previous
            </button>

            <div className="flex items-center space-x-1">
              {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                let pageNum
                if (totalPages <= 5) {
                  pageNum = i + 1
                } else if (page <= 3) {
                  pageNum = i + 1
                } else if (page >= totalPages - 2) {
                  pageNum = totalPages - 4 + i
                } else {
                  pageNum = page - 2 + i
                }

                return (
                  <button
                    key={pageNum}
                    onClick={() => onPageChange(pageNum)}
                    className={`px-3 py-1 rounded-lg text-sm transition-colors ${
                      page === pageNum
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-800 border border-gray-700 text-white hover:bg-gray-700'
                    }`}
                  >
                    {pageNum}
                  </button>
                )
              })}
            </div>

            <button
              onClick={() => onPageChange(page + 1)}
              disabled={page === totalPages}
              className="px-3 py-1 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-700 transition-colors"
            >
              Next
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default PredictionHistory
