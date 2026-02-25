import { useQuery } from 'react-query'
import { signalsAPI } from '../services/api'

/**
 * Hook for fetching signal-trade performance correlation
 */
export function useSignalPerformance(options = {}) {
  const { symbol = 'BTC/USDT', days = 30, enabled = true } = options

  return useQuery(
    ['signals-performance', symbol, days],
    () => signalsAPI.getPerformance({ symbol, days }),
    {
      enabled,
      staleTime: 60000, // 1 minute
      select: (res) => res.data?.data || res.data,
      retry: 2,
    }
  )
}

/**
 * Hook for fetching daily signal performance breakdown
 */
export function useDailySignalPerformance(options = {}) {
  const { symbol = 'BTC/USDT', days = 30, enabled = true } = options

  return useQuery(
    ['signals-performance-daily', symbol, days],
    () => signalsAPI.getDailyPerformance({ symbol, days }),
    {
      enabled,
      staleTime: 60000, // 1 minute
      select: (res) => res.data?.data || res.data,
      retry: 2,
    }
  )
}

/**
 * Combined hook for all signal performance data
 */
export function useSignalPerformanceData(options = {}) {
  const { symbol = 'BTC/USDT', days = 30, enabled = true } = options

  const performance = useSignalPerformance({ symbol, days, enabled })
  const dailyPerformance = useDailySignalPerformance({ symbol, days, enabled })

  return {
    performance: performance.data,
    dailyPerformance: dailyPerformance.data,
    isLoading: performance.isLoading || dailyPerformance.isLoading,
    isError: performance.isError || dailyPerformance.isError,
    refetch: () => {
      performance.refetch()
      dailyPerformance.refetch()
    },
  }
}

export default useSignalPerformance
