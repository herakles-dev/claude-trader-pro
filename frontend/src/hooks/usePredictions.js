import { useQuery, useMutation, useQueryClient } from 'react-query'
import { predictionAPI } from '../services/api'
import { useWebSocket } from './useWebSocket'
import { useEffect } from 'react'
import toast from 'react-hot-toast'

/**
 * Hook for fetching latest prediction
 */
export function useLatestPrediction(symbol = 'BTC') {
  const queryClient = useQueryClient()
  const { lastMessage } = useWebSocket({ autoConnect: true })

  const {
    data: prediction,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery(
    ['prediction-latest', symbol],
    () => predictionAPI.getLatest(symbol),
    {
      staleTime: 60000, // 1 minute
      select: (response) => {
        console.log('%c[usePredictions] Latest prediction raw response:', 'color: #f59e0b', response)
        return response.data
      },
    }
  )

  // Update when new prediction arrives via WebSocket
  useEffect(() => {
    if (!lastMessage || lastMessage.type !== 'prediction_update') return
    
    const { data } = lastMessage
    
    if (data.symbol === symbol) {
      queryClient.invalidateQueries(['prediction-latest', symbol])
      queryClient.invalidateQueries(['predictions']) // Also refresh history
    }
  }, [lastMessage, symbol, queryClient])

  return {
    prediction,
    isLoading,
    isError,
    error,
    refetch,
  }
}

/**
 * Hook for fetching prediction history with pagination
 */
export function usePredictions(params = {}) {
  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useQuery(
    ['predictions', params],
    () => predictionAPI.getPredictions(params),
    {
      keepPreviousData: true, // For smooth pagination
      staleTime: 30000, // 30 seconds
      select: (response) => {
        console.log('%c[usePredictions] Raw API response:', 'color: #f59e0b', response)
        console.log('%c[usePredictions] response.data:', 'color: #3b82f6', response.data)
        console.log('%c[usePredictions] response.data.data:', 'color: #22c55e', response.data?.data)
        return response.data.data
      },
    }
  )

  // Debug log the extracted data
  useEffect(() => {
    if (data) {
      console.log('%c[usePredictions] Extracted data:', 'color: #a855f7', {
        predictions: data?.predictions,
        predictionsCount: data?.predictions?.length,
        pagination: data?.pagination,
        rawData: data,
      })
    }
  }, [data])

  return {
    predictions: data?.predictions || [],
    pagination: data?.pagination || {},
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  }
}

/**
 * Hook for triggering new predictions
 */
export function useTriggerPrediction() {
  const queryClient = useQueryClient()

  const mutation = useMutation(
    ({ symbol, strategy }) => predictionAPI.triggerPrediction(symbol, strategy),
    {
      onSuccess: (response, variables) => {
        toast.success(`Prediction generated for ${variables.symbol}`)
        
        // Invalidate related queries to trigger refetch
        queryClient.invalidateQueries(['prediction-latest', variables.symbol])
        queryClient.invalidateQueries(['predictions'])
        queryClient.invalidateQueries(['analytics'])
      },
      onError: (error, variables) => {
        const errorMessage = error.response?.data?.error || error.response?.data?.message || error.message || 'Unknown error'
        toast.error(`Failed to generate prediction: ${errorMessage}`)
        console.error('Prediction error:', error)
      },
    }
  )

  return {
    triggerPrediction: mutation.mutate,
    isTriggering: mutation.isLoading,
    isSuccess: mutation.isSuccess,
    isError: mutation.isError,
    error: mutation.error,
    data: mutation.data?.data,
  }
}

/**
 * Hook for fetching single prediction by ID
 */
export function usePrediction(id) {
  const {
    data: prediction,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery(
    ['prediction', id],
    () => predictionAPI.getById(id),
    {
      enabled: !!id, // Only fetch if ID is provided
      staleTime: 300000, // 5 minutes (predictions don't change)
      select: (response) => response.data,
    }
  )

  return {
    prediction,
    isLoading,
    isError,
    error,
    refetch,
  }
}

/**
 * Hook for fetching prediction evaluation
 */
export function usePredictionEvaluation(id) {
  const {
    data: evaluation,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery(
    ['prediction-evaluation', id],
    () => predictionAPI.getEvaluation(id),
    {
      enabled: !!id,
      staleTime: 60000, // 1 minute
      select: (response) => response.data,
    }
  )

  return {
    evaluation,
    isLoading,
    isError,
    error,
    refetch,
  }
}

export default usePredictions
