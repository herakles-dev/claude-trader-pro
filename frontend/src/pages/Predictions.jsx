import React, { useState, useEffect } from 'react'
import { usePredictions } from '../hooks/usePredictions'
import {
  formatDate,
  formatConfidence,
  formatRelativeTime,
  getDirectionColor,
  getConfidenceColor,
} from '../utils/formatters'
import { logComponentData, logPredictionData } from '../utils/debugLogger'

function Predictions() {
  const [page, setPage] = useState(1)
  const [filters, setFilters] = useState({
    symbol: '',
    strategy: '',
  })

  const limit = 20
  const { predictions, pagination, isLoading, isFetching } = usePredictions({
    page,
    limit,
    ...filters,
  })

  // Debug logging when data loads
  useEffect(() => {
    if (predictions) {
      logComponentData('Predictions', 'predictions', predictions, { page, filters })
      logPredictionData('Predictions.jsx', predictions, pagination)
      console.log('%c[PREDICTIONS DEBUG] Predictions array:', 'color: #22c55e', predictions)
      console.log('%c[PREDICTIONS DEBUG] Pagination:', 'color: #3b82f6', pagination)
      console.log('%c[PREDICTIONS DEBUG] Count:', 'color: #a855f7', predictions.length)

      // Check each prediction structure
      if (predictions.length > 0) {
        const sample = predictions[0]
        console.log('%c[PREDICTIONS DEBUG] Sample prediction structure:', 'color: #f59e0b', {
          hasId: sample.id !== undefined,
          hasSymbol: sample.symbol !== undefined,
          hasDirection: sample.direction !== undefined,
          hasConfidence: sample.confidence !== undefined,
          hasReasoning: sample.reasoning !== undefined,
          hasCreatedAt: sample.created_at !== undefined,
          sample,
        })
      }
    }
  }, [predictions, pagination, page, filters])

  const handleFilterChange = (key, value) => {
    setFilters((prev) => ({ ...prev, [key]: value }))
    setPage(1) // Reset to first page when filtering
  }

  const exportToCSV = () => {
    if (!predictions.length) return

    const headers = [
      'Timestamp',
      'Symbol',
      'Direction',
      'Confidence',
      'Strategy',
      'Target Price',
      'Stop Loss',
      'Reasoning',
    ]

    const rows = predictions.map((p) => [
      formatDate(p.created_at, 'yyyy-MM-dd HH:mm:ss'),
      p.symbol,
      p.direction,
      p.confidence,
      p.strategy,
      p.target_price || '',
      p.stop_loss || '',
      p.reasoning?.replace(/,/g, ';') || '', // Escape commas
    ])

    const csv = [
      headers.join(','),
      ...rows.map((row) => row.join(',')),
    ].join('\n')

    const blob = new Blob([csv], { type: 'text/csv' })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `predictions-${Date.now()}.csv`
    a.click()
    window.URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between space-y-4 sm:space-y-0">
        <div>
          <h1 className="text-3xl font-bold text-white">Prediction History</h1>
          <p className="text-gray-400 mt-1">
            Browse and analyze all AI-generated predictions
          </p>
        </div>
        <button onClick={exportToCSV} className="btn-primary">
          📊 Export to CSV
        </button>
      </div>

      {/* Filters */}
      <div className="card p-6">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-400 mb-2">
              Symbol
            </label>
            <select
              value={filters.symbol}
              onChange={(e) => handleFilterChange('symbol', e.target.value)}
              className="select-field"
            >
              <option value="">All Symbols</option>
              <option value="BTC">BTC</option>
              <option value="ETH">ETH</option>
              <option value="SOL">SOL</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-400 mb-2">
              Strategy
            </label>
            <select
              value={filters.strategy}
              onChange={(e) => handleFilterChange('strategy', e.target.value)}
              className="select-field"
            >
              <option value="">All Strategies</option>
              <option value="conservative">Conservative</option>
              <option value="aggressive">Aggressive</option>
            </select>
          </div>

          <div className="flex items-end">
            <button
              onClick={() => {
                setFilters({ symbol: '', strategy: '' })
                setPage(1)
              }}
              className="btn-secondary w-full"
            >
              Clear Filters
            </button>
          </div>
        </div>
      </div>

      {/* Predictions Table */}
      <div className="card overflow-hidden">
        {isLoading ? (
          <div className="p-12 text-center">
            <div className="inline-block w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
            <p className="text-gray-400 mt-4">Loading predictions...</p>
          </div>
        ) : predictions.length === 0 ? (
          <div className="p-12 text-center">
            <p className="text-2xl mb-2">📭</p>
            <p className="text-gray-400">No predictions found</p>
          </div>
        ) : (
          <>
            {/* Desktop Table */}
            <div className="hidden md:block overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-900 border-b border-gray-700">
                  <tr>
                    <th className="px-6 py-4 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                      Timestamp
                    </th>
                    <th className="px-6 py-4 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                      Symbol
                    </th>
                    <th className="px-6 py-4 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                      Direction
                    </th>
                    <th className="px-6 py-4 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                      Confidence
                    </th>
                    <th className="px-6 py-4 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                      Strategy
                    </th>
                    <th className="px-6 py-4 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                      Reasoning
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-700">
                  {predictions.map((prediction, index) => (
                    <tr
                      key={prediction.id || index}
                      className="hover:bg-gray-800/50 transition-colors"
                    >
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-300">
                        <div>{formatDate(prediction.created_at, 'MMM dd, yyyy')}</div>
                        <div className="text-xs text-gray-500">
                          {formatDate(prediction.created_at, 'HH:mm:ss')}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className="badge badge-info">
                          {prediction.symbol}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span
                          className={`font-bold ${getDirectionColor(
                            prediction.direction
                          )}`}
                        >
                          {prediction.direction === 'up' ? '🔼' : '🔽'}{' '}
                          {prediction.direction?.toUpperCase()}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span
                          className={`font-semibold ${getConfidenceColor(
                            prediction.confidence
                          )}`}
                        >
                          {formatConfidence(prediction.confidence)}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-300">
                        <span className="capitalize">{prediction.strategy}</span>
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-400 max-w-md">
                        <div className="truncate" title={prediction.reasoning}>
                          {prediction.reasoning}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Mobile Cards */}
            <div className="md:hidden divide-y divide-gray-700">
              {predictions.map((prediction, index) => (
                <div key={prediction.id || index} className="p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="badge badge-info">{prediction.symbol}</span>
                    <span className="text-xs text-gray-500">
                      {formatRelativeTime(prediction.created_at)}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <div className="text-xs text-gray-500 mb-1">Direction</div>
                      <div
                        className={`font-bold ${getDirectionColor(
                          prediction.direction
                        )}`}
                      >
                        {prediction.direction === 'up' ? '🔼' : '🔽'}{' '}
                        {prediction.direction?.toUpperCase()}
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-gray-500 mb-1">Confidence</div>
                      <div
                        className={`font-semibold ${getConfidenceColor(
                          prediction.confidence
                        )}`}
                      >
                        {formatConfidence(prediction.confidence)}
                      </div>
                    </div>
                  </div>

                  <div>
                    <div className="text-xs text-gray-500 mb-1">Reasoning</div>
                    <div className="text-sm text-gray-300 line-clamp-2">
                      {prediction.reasoning}
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Pagination */}
            {pagination.total_pages > 1 && (
              <div className="bg-gray-900 border-t border-gray-700 px-6 py-4">
                <div className="flex items-center justify-between">
                  <div className="text-sm text-gray-400">
                    Showing {(page - 1) * limit + 1} to{' '}
                    {Math.min(page * limit, pagination.total)} of{' '}
                    {pagination.total} predictions
                  </div>

                  <div className="flex items-center space-x-2">
                    <button
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                      disabled={page === 1 || isFetching}
                      className="btn-secondary text-sm disabled:opacity-50"
                    >
                      Previous
                    </button>

                    <div className="flex items-center space-x-1">
                      {[...Array(pagination.total_pages)].map((_, i) => {
                        const pageNum = i + 1
                        // Show first, last, current, and adjacent pages
                        if (
                          pageNum === 1 ||
                          pageNum === pagination.total_pages ||
                          Math.abs(pageNum - page) <= 1
                        ) {
                          return (
                            <button
                              key={pageNum}
                              onClick={() => setPage(pageNum)}
                              disabled={isFetching}
                              className={`px-3 py-1 rounded text-sm ${
                                page === pageNum
                                  ? 'bg-blue-600 text-white'
                                  : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                              }`}
                            >
                              {pageNum}
                            </button>
                          )
                        } else if (pageNum === page - 2 || pageNum === page + 2) {
                          return (
                            <span key={pageNum} className="text-gray-500">
                              ...
                            </span>
                          )
                        }
                        return null
                      })}
                    </div>

                    <button
                      onClick={() =>
                        setPage((p) => Math.min(pagination.total_pages, p + 1))
                      }
                      disabled={page === pagination.total_pages || isFetching}
                      className="btn-secondary text-sm disabled:opacity-50"
                    >
                      Next
                    </button>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

export default Predictions
