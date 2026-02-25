import React, { useState, useMemo } from 'react'
import { usePatternAnalytics } from '../../hooks/useAnalytics'

const getGradeColor = (grade) => {
  if (!grade) return 'bg-gray-700 text-gray-300'
  const letter = grade.charAt(0).toUpperCase()
  switch (letter) {
    case 'A':
      return 'bg-green-900/50 text-green-400 border border-green-700'
    case 'B':
      return 'bg-blue-900/50 text-blue-400 border border-blue-700'
    case 'C':
      return 'bg-yellow-900/50 text-yellow-400 border border-yellow-700'
    case 'D':
    case 'F':
      return 'bg-red-900/50 text-red-400 border border-red-700'
    default:
      return 'bg-gray-700 text-gray-300'
  }
}

const getPatternTypeColor = (type) => {
  switch (type?.toLowerCase()) {
    case 'technical':
      return 'text-blue-400'
    case 'sentiment':
      return 'text-purple-400'
    case 'composite':
      return 'text-cyan-400'
    case 'price':
      return 'text-green-400'
    default:
      return 'text-gray-400'
  }
}

function PatternsTab() {
  const [sortField, setSortField] = useState('accuracy')
  const [sortDirection, setSortDirection] = useState('desc')
  const [minOccurrences, setMinOccurrences] = useState(5)

  const { data, isLoading, isError } = usePatternAnalytics({ minOccurrences })

  // Transform patterns to normalize field names
  // Backend returns: occurrences, successful, accuracy_pct (percentage)
  // Frontend expects: total_occurrences, successful_predictions, accuracy_rate (decimal)
  const normalizedPatterns = useMemo(() => {
    if (!data?.patterns) return []
    return data.patterns.map(p => ({
      ...p,
      total_occurrences: p.occurrences || p.total_occurrences || 0,
      successful_predictions: p.successful || p.successful_predictions || 0,
      accuracy_rate: p.accuracy_pct != null
        ? p.accuracy_pct / 100
        : (p.accuracy_rate || 0),
    }))
  }, [data?.patterns])

  const sortedPatterns = useMemo(() => {
    if (!normalizedPatterns.length) return []

    return [...normalizedPatterns].sort((a, b) => {
      let aVal, bVal
      switch (sortField) {
        case 'name':
          aVal = a.pattern_name || ''
          bVal = b.pattern_name || ''
          return sortDirection === 'asc'
            ? aVal.localeCompare(bVal)
            : bVal.localeCompare(aVal)
        case 'type':
          aVal = a.pattern_type || ''
          bVal = b.pattern_type || ''
          return sortDirection === 'asc'
            ? aVal.localeCompare(bVal)
            : bVal.localeCompare(aVal)
        case 'occurrences':
          aVal = a.total_occurrences || 0
          bVal = b.total_occurrences || 0
          break
        case 'success':
          aVal = a.successful_predictions || 0
          bVal = b.successful_predictions || 0
          break
        case 'accuracy':
        default:
          aVal = a.accuracy_rate || 0
          bVal = b.accuracy_rate || 0
          break
      }
      return sortDirection === 'asc' ? aVal - bVal : bVal - aVal
    })
  }, [normalizedPatterns, sortField, sortDirection])

  // Compute summary stats from normalized patterns since backend doesn't provide them
  const computedSummary = useMemo(() => {
    if (!normalizedPatterns.length) return null

    // Best performing pattern (highest accuracy)
    const sortedByAccuracy = [...normalizedPatterns].sort(
      (a, b) => (b.accuracy_rate || 0) - (a.accuracy_rate || 0)
    )
    const bestPattern = sortedByAccuracy[0]

    // Most common pattern (highest occurrences)
    const sortedByOccurrences = [...normalizedPatterns].sort(
      (a, b) => (b.total_occurrences || 0) - (a.total_occurrences || 0)
    )
    const mostCommon = sortedByOccurrences[0]

    // Average accuracy across all patterns
    const avgAccuracy = normalizedPatterns.reduce((sum, p) => sum + (p.accuracy_rate || 0), 0) /
      normalizedPatterns.length

    return {
      best_pattern: bestPattern
        ? { name: bestPattern.pattern_name, accuracy: bestPattern.accuracy_rate }
        : null,
      most_common: mostCommon
        ? { name: mostCommon.pattern_name, count: mostCommon.total_occurrences }
        : null,
      avg_accuracy: avgAccuracy || null,
    }
  }, [normalizedPatterns])

  const handleSort = (field) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortDirection('desc')
    }
  }

  const SortIcon = ({ field }) => {
    if (sortField !== field) return <span className="text-gray-600">↕</span>
    return sortDirection === 'asc' ? '↑' : '↓'
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="card p-6">
          <div className="skeleton h-8 w-64 mb-6" />
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="skeleton h-12 mb-2" />
          ))}
        </div>
      </div>
    )
  }

  if (isError) {
    return (
      <div className="card p-6 text-center">
        <div className="text-red-400 mb-2">Failed to load pattern analytics</div>
        <p className="text-gray-500 text-sm">Please try again later</p>
      </div>
    )
  }

  const hasPatterns = sortedPatterns.length > 0

  return (
    <div className="space-y-6">
      {/* Header with filter */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h3 className="text-xl font-bold text-white">Pattern Performance Leaderboard</h3>
          <p className="text-sm text-gray-400 mt-1">
            {data?.total_patterns || 0} patterns analyzed across {data?.total_predictions || 0} predictions
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <label className="text-sm text-gray-400">Min occurrences:</label>
          <select
            value={minOccurrences}
            onChange={(e) => setMinOccurrences(Number(e.target.value))}
            className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-white"
          >
            <option value={3}>3+</option>
            <option value={5}>5+</option>
            <option value={10}>10+</option>
            <option value={20}>20+</option>
          </select>
        </div>
      </div>

      {/* Patterns Table */}
      {hasPatterns ? (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-900">
                <tr>
                  <th
                    onClick={() => handleSort('name')}
                    className="px-6 py-4 text-left text-xs font-medium text-gray-400 uppercase cursor-pointer hover:text-white"
                  >
                    Pattern Name <SortIcon field="name" />
                  </th>
                  <th
                    onClick={() => handleSort('type')}
                    className="px-6 py-4 text-left text-xs font-medium text-gray-400 uppercase cursor-pointer hover:text-white"
                  >
                    Type <SortIcon field="type" />
                  </th>
                  <th
                    onClick={() => handleSort('occurrences')}
                    className="px-6 py-4 text-center text-xs font-medium text-gray-400 uppercase cursor-pointer hover:text-white"
                  >
                    Count <SortIcon field="occurrences" />
                  </th>
                  <th
                    onClick={() => handleSort('success')}
                    className="px-6 py-4 text-center text-xs font-medium text-gray-400 uppercase cursor-pointer hover:text-white"
                  >
                    Success <SortIcon field="success" />
                  </th>
                  <th
                    onClick={() => handleSort('accuracy')}
                    className="px-6 py-4 text-center text-xs font-medium text-gray-400 uppercase cursor-pointer hover:text-white"
                  >
                    Accuracy <SortIcon field="accuracy" />
                  </th>
                  <th className="px-6 py-4 text-center text-xs font-medium text-gray-400 uppercase">
                    Grade
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-700">
                {sortedPatterns.map((pattern, index) => (
                  <tr key={pattern.pattern_name || index} className="hover:bg-gray-800/50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="font-medium text-white">
                        {pattern.pattern_name || 'Unknown'}
                      </span>
                      {pattern.description && (
                        <p className="text-xs text-gray-500 mt-0.5">{pattern.description}</p>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`text-sm capitalize ${getPatternTypeColor(pattern.pattern_type)}`}>
                        {pattern.pattern_type || 'Unknown'}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-center text-gray-300">
                      {pattern.total_occurrences || 0}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-center text-green-400">
                      {pattern.successful_predictions || 0}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-center">
                      <span className={`font-semibold ${
                        (pattern.accuracy_rate || 0) >= 0.7 ? 'text-green-400' :
                        (pattern.accuracy_rate || 0) >= 0.5 ? 'text-yellow-400' : 'text-red-400'
                      }`}>
                        {((pattern.accuracy_rate || 0) * 100).toFixed(1)}%
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-center">
                      <span className={`px-2 py-1 rounded text-xs font-bold ${getGradeColor(pattern.grade)}`}>
                        {pattern.grade || 'N/A'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="card p-12 text-center">
          <div className="text-4xl mb-4">📊</div>
          <h4 className="text-lg font-medium text-white mb-2">No Patterns Found</h4>
          <p className="text-gray-400">
            Pattern data will appear here once enough predictions have been made.
          </p>
        </div>
      )}

      {/* Summary Stats */}
      {computedSummary && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="stat-card">
            <div className="stat-label">Best Performing</div>
            <div className="stat-value text-green-400 text-lg">
              {computedSummary.best_pattern?.name || '--'}
            </div>
            <div className="text-xs text-gray-500">
              {computedSummary.best_pattern?.accuracy
                ? `${(computedSummary.best_pattern.accuracy * 100).toFixed(1)}% accuracy`
                : 'No data'}
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Most Common</div>
            <div className="stat-value text-blue-400 text-lg">
              {computedSummary.most_common?.name || '--'}
            </div>
            <div className="text-xs text-gray-500">
              {computedSummary.most_common?.count
                ? `${computedSummary.most_common.count} occurrences`
                : 'No data'}
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Average Accuracy</div>
            <div className="stat-value text-yellow-400 text-lg">
              {computedSummary.avg_accuracy
                ? `${(computedSummary.avg_accuracy * 100).toFixed(1)}%`
                : '--'}
            </div>
            <div className="text-xs text-gray-500">Across all patterns</div>
          </div>
        </div>
      )}
    </div>
  )
}

export default PatternsTab
