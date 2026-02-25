import { useQuery, useQueryClient } from 'react-query'
import { marketAPI } from '../services/api'
import { useWebSocket } from './useWebSocket'
import { useEffect } from 'react'

/**
 * Custom hook for fetching and managing market data
 * Integrates REST API with WebSocket for real-time updates
 */
export function useMarketData(symbol = 'BTC', options = {}) {
  const {
    enableRealTime = true,
    refetchInterval = 30000, // 30 seconds
  } = options

  const queryClient = useQueryClient()
  const { lastMessage } = useWebSocket({ autoConnect: enableRealTime })

  // Fetch market data
  const {
    data: marketData,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery(
    ['market', symbol],
    () => marketAPI.getMarket(symbol),
    {
      refetchInterval: enableRealTime ? refetchInterval : false,
      staleTime: 15000, // 15 seconds
      select: (response) => {
        console.log(`%c[useMarketData] ${symbol} raw response:`, 'color: #f59e0b', response)
        return response.data
      },
    }
  )

  // Debug log when market data changes
  useEffect(() => {
    if (marketData) {
      console.log(`%c[useMarketData] ${symbol} processed data:`, 'color: #22c55e', marketData)
    }
  }, [marketData, symbol])

  // Update cache with WebSocket data
  useEffect(() => {
    if (!lastMessage || lastMessage.type !== 'market_update') return
    
    const { data } = lastMessage
    
    // Update cache if this is the symbol we're watching
    if (data.symbol === symbol) {
      queryClient.setQueryData(['market', symbol], (old) => ({
        ...old,
        data: {
          ...old?.data,
          ...data,
        },
      }))
    }
  }, [lastMessage, symbol, queryClient])

  return {
    marketData,
    isLoading,
    isError,
    error,
    refetch,
  }
}

/**
 * Hook for fetching multiple markets at once
 */
export function useMultipleMarkets(symbols = ['BTC', 'ETH', 'SOL']) {
  const queryClient = useQueryClient()
  const { lastMessage } = useWebSocket({ autoConnect: true })

  const {
    data: marketsData,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery(
    ['markets', symbols.join(',')],
    () => marketAPI.getMarkets(symbols),
    {
      refetchInterval: 30000,
      staleTime: 15000,
      select: (response) => {
        console.log('%c[useMultipleMarkets] Raw response:', 'color: #f59e0b', response)
        return response.data
      },
    }
  )

  // Debug log when data changes
  useEffect(() => {
    if (marketsData) {
      console.log('%c[useMultipleMarkets] Processed markets data:', 'color: #22c55e', marketsData)
      symbols.forEach(symbol => {
        const data = marketsData[symbol]
        if (data) {
          console.log(`%c[useMultipleMarkets] ${symbol}:`, 'color: #3b82f6', {
            current_price: data.current_price,
            change_24h: data.price_change_percentage_24h,
            notAvailable: data.notAvailable
          })
        } else {
          console.warn(`%c[useMultipleMarkets] Missing data for ${symbol}`, 'color: #ef4444')
        }
      })
    }
  }, [marketsData, symbols])

  // Update individual market caches from batch data
  useEffect(() => {
    if (!marketsData) return

    Object.entries(marketsData).forEach(([symbol, data]) => {
      queryClient.setQueryData(['market', symbol], { data })
    })
  }, [marketsData, queryClient])

  // Update cache with WebSocket data
  useEffect(() => {
    if (!lastMessage || lastMessage.type !== 'market_update') return
    
    const { data } = lastMessage
    
    if (symbols.includes(data.symbol)) {
      queryClient.setQueryData(['market', data.symbol], (old) => ({
        ...old,
        data: {
          ...old?.data,
          ...data,
        },
      }))
    }
  }, [lastMessage, symbols, queryClient])

  return {
    marketsData,
    isLoading,
    isError,
    error,
    refetch,
  }
}

/**
 * Hook for fetching historical market data
 */
export function useMarketHistory(symbol = 'BTC', interval = '1h', limit = 100) {
  const {
    data: historyData,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery(
    ['market-history', symbol, interval, limit],
    () => marketAPI.getHistory(symbol, interval, limit),
    {
      staleTime: 60000, // 1 minute
      select: (response) => response.data,
    }
  )

  return {
    historyData,
    isLoading,
    isError,
    error,
    refetch,
  }
}

export default useMarketData
