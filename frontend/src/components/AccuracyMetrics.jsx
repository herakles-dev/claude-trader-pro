import React, { useEffect } from 'react'
import { useQuery } from 'react-query'
import { analyticsAPI } from '../services/api'
import { logComponentData, logAnalyticsData } from '../utils/debugLogger'

function AccuracyMetrics({ timeRange = '30d' }) {
  const { data: accuracy, isLoading } = useQuery(
    ['accuracy-metrics', timeRange],
    () => analyticsAPI.getAccuracy(timeRange),
    {
      select: (res) => {
        console.log('%c[ACCURACY METRICS DEBUG] Raw response:', 'color: #f59e0b', res.data)
        return res.data?.data || res.data
      },
    }
  )

  // Debug logging when data loads
  useEffect(() => {
    if (accuracy) {
      logComponentData('AccuracyMetrics', 'accuracy', accuracy, { timeRange })
      logAnalyticsData('AccuracyMetrics.jsx', 'accuracy', accuracy)
      console.log('%c[ACCURACY METRICS DEBUG] Processed accuracy:', 'color: #22c55e', accuracy)
      console.log('%c[ACCURACY METRICS DEBUG] Field mapping:', 'color: #3b82f6', {
        raw_overall_accuracy: accuracy.overall_accuracy,
        raw_accuracy_percentage: accuracy.accuracy_percentage,
        raw_total_predictions: accuracy.total_predictions,
        raw_total_evaluated: accuracy.total_evaluated,
        raw_correct_predictions: accuracy.correct_predictions,
        raw_incorrect_predictions: accuracy.incorrect_predictions,
      })
    }
  }, [accuracy, timeRange])

  if (isLoading) {
    return (
      <div className="card p-6">
        <div className="skeleton h-8 w-32 mb-4" />
        <div className="skeleton h-24" />
      </div>
    )
  }

  if (!accuracy) return null

  // Map backend field names to what the component expects
  // Backend returns: accuracy_percentage (as %), total_evaluated
  // Frontend expects: overall_accuracy (as decimal), total_predictions
  const overallAccuracy = accuracy.overall_accuracy != null
    ? accuracy.overall_accuracy
    : (accuracy.accuracy_percentage != null ? accuracy.accuracy_percentage / 100 : 0)
  const totalPredictions = accuracy.total_predictions || accuracy.total_evaluated || 0
  const correctPredictions = accuracy.correct_predictions ||
    Math.round(totalPredictions * overallAccuracy) || 0
  const incorrectPredictions = accuracy.incorrect_predictions ||
    (totalPredictions - correctPredictions) || 0

  const winRate = (overallAccuracy * 100).toFixed(1)
  const isGoodRate = overallAccuracy >= 0.6

  return (
    <div className="card p-6 space-y-4">
      <h3 className="text-lg font-bold text-white">Accuracy Metrics</h3>

      {/* Overall Accuracy */}
      <div className="text-center py-6 bg-gray-900/50 rounded-lg">
        <div
          className={`text-5xl font-bold ${
            isGoodRate ? 'text-green-400' : 'text-yellow-400'
          }`}
        >
          {winRate}%
        </div>
        <div className="text-sm text-gray-400 mt-2">Overall Win Rate</div>
      </div>

      {/* Breakdown */}
      <div className="grid grid-cols-3 gap-3 text-center text-sm">
        <div className="bg-green-900/20 border border-green-700 rounded p-3">
          <div className="text-green-400 font-bold text-xl">
            {correctPredictions}
          </div>
          <div className="text-gray-400 text-xs mt-1">Correct</div>
        </div>

        <div className="bg-red-900/20 border border-red-700 rounded p-3">
          <div className="text-red-400 font-bold text-xl">
            {incorrectPredictions}
          </div>
          <div className="text-gray-400 text-xs mt-1">Incorrect</div>
        </div>

        <div className="bg-gray-800 border border-gray-700 rounded p-3">
          <div className="text-gray-300 font-bold text-xl">
            {totalPredictions}
          </div>
          <div className="text-gray-400 text-xs mt-1">Total</div>
        </div>
      </div>
    </div>
  )
}

export default AccuracyMetrics
