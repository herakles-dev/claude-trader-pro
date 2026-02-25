import { useQuery } from 'react-query'
import { analyticsAPI } from '../services/api'
import { logAnalyticsData } from '../utils/debugLogger'

/**
 * Hook for fetching pattern performance analytics
 */
export function usePatternAnalytics(options = {}) {
  const { minOccurrences = 5, enabled = true } = options

  return useQuery(
    ['analytics-patterns', minOccurrences],
    () => analyticsAPI.getPatterns(minOccurrences),
    {
      enabled,
      staleTime: 300000, // 5 minutes
      select: (res) => {
        const data = res.data?.data || res.data
        console.log('%c[usePatternAnalytics] Raw response:', 'color: #f59e0b', res.data)
        console.log('%c[usePatternAnalytics] Processed:', 'color: #22c55e', data)
        logAnalyticsData('usePatternAnalytics', 'patterns', data)
        console.log('%c[usePatternAnalytics] Key fields:', 'color: #3b82f6', {
          total_patterns: data?.total_patterns || data?.patterns?.length,
          total_predictions: data?.total_predictions,
          patterns_count: data?.patterns?.length,
        })
        return data
      },
      retry: 2,
    }
  )
}

/**
 * Hook for fetching market conditions/regime analytics
 */
export function useConditionsAnalytics(options = {}) {
  const { days = 30, enabled = true } = options

  return useQuery(
    ['analytics-conditions', days],
    () => analyticsAPI.getConditions(days),
    {
      enabled,
      staleTime: 300000, // 5 minutes
      select: (res) => {
        const data = res.data?.data || res.data
        console.log('%c[useConditionsAnalytics] Raw response:', 'color: #f59e0b', res.data)
        console.log('%c[useConditionsAnalytics] Processed:', 'color: #22c55e', data)
        logAnalyticsData('useConditionsAnalytics', 'conditions', data)
        console.log('%c[useConditionsAnalytics] Key fields:', 'color: #3b82f6', {
          current_regime: data?.current_regime,
          current_volatility: data?.current_volatility,
          market_regimes_count: data?.market_regimes?.length,
          volatility_regimes_count: data?.volatility_regimes?.length,
          total_evaluated: data?.total_evaluated,
          recommendations: data?.recommendations?.length,
        })
        return data
      },
      retry: 2,
    }
  )
}

/**
 * Hook for fetching confidence calibration analytics
 */
export function useCalibrationAnalytics(options = {}) {
  const { days = 30, enabled = true } = options

  return useQuery(
    ['analytics-calibration', days],
    () => analyticsAPI.getCalibration(days),
    {
      enabled,
      staleTime: 300000, // 5 minutes
      select: (res) => {
        const data = res.data?.data || res.data
        console.log('%c[useCalibrationAnalytics] Raw response:', 'color: #f59e0b', res.data)
        console.log('%c[useCalibrationAnalytics] Processed:', 'color: #22c55e', data)
        logAnalyticsData('useCalibrationAnalytics', 'calibration', data)
        console.log('%c[useCalibrationAnalytics] Key fields:', 'color: #3b82f6', {
          buckets_count: data?.buckets?.length,
          overall_calibration_error: data?.overall_calibration_error,
          data_available: data?.data_available,
        })
        return data
      },
      retry: 2,
    }
  )
}

/**
 * Combined hook for all advanced analytics
 */
export function useAdvancedAnalytics(options = {}) {
  const { days = 30, minOccurrences = 5, enabled = true } = options

  const patterns = usePatternAnalytics({ minOccurrences, enabled })
  const conditions = useConditionsAnalytics({ days, enabled })
  const calibration = useCalibrationAnalytics({ days, enabled })

  return {
    patterns: patterns.data,
    conditions: conditions.data,
    calibration: calibration.data,
    isLoading: patterns.isLoading || conditions.isLoading || calibration.isLoading,
    isError: patterns.isError || conditions.isError || calibration.isError,
    refetch: () => {
      patterns.refetch()
      conditions.refetch()
      calibration.refetch()
    },
  }
}

export default usePatternAnalytics
