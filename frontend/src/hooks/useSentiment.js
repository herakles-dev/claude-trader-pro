import { useQuery, useQueryClient } from 'react-query'
import { sentimentAPI } from '../services/api'
import { useWebSocket } from './useWebSocket'
import { useEffect } from 'react'

/**
 * Hook for fetching Fear & Greed Index
 */
export function useFearGreed() {
  const queryClient = useQueryClient()
  const { lastMessage } = useWebSocket({ autoConnect: true })

  const {
    data: fearGreed,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery(
    'fear-greed',
    () => sentimentAPI.getFearGreed(),
    {
      refetchInterval: 300000, // 5 minutes
      staleTime: 240000, // 4 minutes
      select: (response) => response.data,
    }
  )

  // Update with WebSocket data
  useEffect(() => {
    if (!lastMessage || lastMessage.type !== 'sentiment_update') return
    
    const { data } = lastMessage
    
    if (data.fear_greed) {
      queryClient.setQueryData('fear-greed', (old) => ({
        ...old,
        data: data.fear_greed,
      }))
    }
  }, [lastMessage, queryClient])

  return {
    fearGreed,
    isLoading,
    isError,
    error,
    refetch,
  }
}

/**
 * Hook for fetching Reddit sentiment
 */
export function useRedditSentiment() {
  const queryClient = useQueryClient()
  const { lastMessage } = useWebSocket({ autoConnect: true })

  const {
    data: reddit,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery(
    'reddit-sentiment',
    () => sentimentAPI.getReddit(),
    {
      refetchInterval: 300000, // 5 minutes
      staleTime: 240000, // 4 minutes
      select: (response) => response.data,
    }
  )

  // Update with WebSocket data
  useEffect(() => {
    if (!lastMessage || lastMessage.type !== 'sentiment_update') return
    
    const { data } = lastMessage
    
    if (data.reddit) {
      queryClient.setQueryData('reddit-sentiment', (old) => ({
        ...old,
        data: data.reddit,
      }))
    }
  }, [lastMessage, queryClient])

  return {
    reddit,
    isLoading,
    isError,
    error,
    refetch,
  }
}

/**
 * Hook for fetching all sentiment data at once
 */
export function useAllSentiment() {
  const queryClient = useQueryClient()
  const { lastMessage } = useWebSocket({ autoConnect: true })

  const {
    data: sentiment,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery(
    'all-sentiment',
    () => sentimentAPI.getAll(),
    {
      refetchInterval: 300000, // 5 minutes
      staleTime: 240000, // 4 minutes
      select: (response) => response.data,
    }
  )

  // Update individual caches from combined data
  useEffect(() => {
    if (!sentiment) return

    if (sentiment.fear_greed) {
      queryClient.setQueryData('fear-greed', { data: sentiment.fear_greed })
    }
    if (sentiment.reddit) {
      queryClient.setQueryData('reddit-sentiment', { data: sentiment.reddit })
    }
  }, [sentiment, queryClient])

  // Update with WebSocket data
  useEffect(() => {
    if (!lastMessage || lastMessage.type !== 'sentiment_update') return
    
    const { data } = lastMessage
    
    queryClient.setQueryData('all-sentiment', (old) => ({
      ...old,
      data: {
        ...old?.data,
        ...data,
      },
    }))
  }, [lastMessage, queryClient])

  return {
    sentiment,
    fearGreed: sentiment?.fear_greed,
    reddit: sentiment?.reddit,
    isLoading,
    isError,
    error,
    refetch,
  }
}

export default useAllSentiment
