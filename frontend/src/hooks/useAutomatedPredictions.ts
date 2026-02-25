import { useState, useEffect, useCallback, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from 'react-query'
import toast from 'react-hot-toast'
import api from '../services/api'

/**
 * API Base URL
 */
const API_BASE_URL = import.meta.env.VITE_API_URL || '/api'

/**
 * Type Definitions
 */
export interface Cycle {
  cycle_id: string
  cycle_number: number
  start_time: string
  end_time: string
  status: 'active' | 'completed' | 'pending'
  predictions_count: number
  predictions?: Prediction[]
}

export interface Decision {
  decision_id: string
  cycle_id: string
  timestamp: string
  final_signal: 'BUY' | 'SELL' | 'HOLD'
  confidence: number
  symbol: string
  analysis_summary: string
  recommendations: string[]
}

export interface Prediction {
  prediction_id: string
  cycle_id: string
  symbol: string
  timestamp: string
  direction: 'UP' | 'DOWN' | 'NEUTRAL'
  confidence: number
  price_at_prediction: number
  target_price?: number
  market_data: Record<string, any>
}

export interface SchedulerStatus {
  scheduler_active: boolean
  next_prediction_time: string | null
  predictions_today: number
  current_cycle: string | null
  uptime: number
  last_error?: string
}

export interface HistoryParams {
  limit?: number
  offset?: number
  symbol?: string
  cycle_id?: string
}

export interface WebSocketEvent {
  type: string
  data: any
  timestamp: number
}

/**
 * Custom hook for automated predictions management
 * 
 * Features:
 * - Fetch current 4-hour cycle
 * - Fetch latest 4H decision
 * - Fetch prediction history with pagination
 * - Fetch scheduler status
 * - Trigger manual predictions
 * - WebSocket subscription for real-time updates
 * - Auto-refresh active cycle
 */
export function useAutomatedPredictions() {
  const queryClient = useQueryClient()
  const [error, setError] = useState<string | null>(null)
  const socketRef = useRef<any>(null)
  const lastMessageRef = useRef<WebSocketEvent | null>(null)

  /**
   * Fetch Current Cycle
   */
  const {
    data: currentCycle,
    isLoading: cycleLoading,
    error: cycleError,
    refetch: refetchCycle,
  } = useQuery<Cycle | null>(
    ['automated-cycle-current'],
    async () => {
      const response = await api.get(`${API_BASE_URL}/v1/automated/cycle/current`)
      return response.data?.data || null
    },
    {
      staleTime: 30000, // 30 seconds
      refetchInterval: (data) => {
        // Auto-refresh every 60s if cycle is active
        return data?.status === 'active' ? 60000 : false
      },
      onError: (err: any) => {
        const errorMessage = err.response?.data?.error || err.message || 'Failed to fetch current cycle'
        setError(errorMessage)
        console.error('Cycle fetch error:', err)
      },
    }
  )

  /**
   * Fetch Latest Decision
   */
  const {
    data: latestDecision,
    isLoading: decisionLoading,
    error: decisionError,
    refetch: refetchDecision,
  } = useQuery<Decision | null>(
    ['automated-decision-latest'],
    async () => {
      const response = await api.get(`${API_BASE_URL}/v1/automated/decision/latest`)
      return response.data?.data || null
    },
    {
      staleTime: 60000, // 1 minute
      onError: (err: any) => {
        const errorMessage = err.response?.data?.error || err.message || 'Failed to fetch latest decision'
        setError(errorMessage)
        console.error('Decision fetch error:', err)
      },
    }
  )

  /**
   * Fetch Prediction History
   */
  const {
    data: historyData,
    isLoading: historyLoading,
    error: historyError,
    refetch: refetchHistory,
  } = useQuery<{ predictions: Prediction[]; total: number }>(
    ['automated-predictions-history'],
    async () => {
      const response = await api.get(`${API_BASE_URL}/v1/automated/predictions/history`, {
        params: { limit: 20, offset: 0 },
      })
      return response.data?.data || { predictions: [], total: 0 }
    },
    {
      staleTime: 30000, // 30 seconds
      onError: (err: any) => {
        const errorMessage = err.response?.data?.error || err.message || 'Failed to fetch prediction history'
        setError(errorMessage)
        console.error('History fetch error:', err)
      },
    }
  )

  /**
   * Fetch Scheduler Status
   */
  const {
    data: schedulerStatus,
    isLoading: statusLoading,
    error: statusError,
    refetch: refetchStatus,
  } = useQuery<SchedulerStatus | null>(
    ['automated-scheduler-status'],
    async () => {
      const response = await api.get(`${API_BASE_URL}/v1/automated/status`)
      return response.data?.data || null
    },
    {
      staleTime: 60000, // 1 minute
      refetchInterval: 60000, // Refresh every minute
      onError: (err: any) => {
        const errorMessage = err.response?.data?.error || err.message || 'Failed to fetch scheduler status'
        setError(errorMessage)
        console.error('Status fetch error:', err)
      },
    }
  )

  /**
   * Trigger Manual Prediction
   */
  const triggerMutation = useMutation(
    async () => {
      const response = await api.post(`${API_BASE_URL}/v1/automated/predict/now`)
      return response.data
    },
    {
      onSuccess: (response) => {
        toast.success('Manual prediction triggered successfully')
        
        // Invalidate related queries to trigger refetch
        queryClient.invalidateQueries(['automated-cycle-current'])
        queryClient.invalidateQueries(['automated-predictions-history'])
        queryClient.invalidateQueries(['automated-scheduler-status'])
      },
      onError: (err: any) => {
        const errorMessage = err.response?.data?.error || err.message || 'Failed to trigger prediction'
        toast.error(`Prediction failed: ${errorMessage}`)
        setError(errorMessage)
        console.error('Trigger prediction error:', err)
      },
    }
  )

  /**
   * WebSocket Subscription Setup
   */
  useEffect(() => {
    // Import socket.io-client dynamically
    import('socket.io-client').then(({ io }) => {
      const WS_URL = import.meta.env.VITE_WS_URL || window.location.origin
      
      // Create socket connection
      const socket = io(WS_URL, {
        transports: ['websocket', 'polling'],
        reconnection: true,
        reconnectionAttempts: 5,
        reconnectionDelay: 1000,
      })

      socketRef.current = socket

      // Connection handlers
      socket.on('connect', () => {
        console.log('WebSocket connected for automated predictions')
      })

      socket.on('disconnect', (reason) => {
        console.log('WebSocket disconnected:', reason)
      })

      socket.on('connect_error', (err) => {
        console.error('WebSocket connection error:', err)
      })

      // Subscribe to automated prediction events
      socket.on('automated_prediction_created', (data: Prediction) => {
        console.log('Automated prediction created:', data)
        
        lastMessageRef.current = {
          type: 'automated_prediction_created',
          data,
          timestamp: Date.now(),
        }

        // Invalidate queries to refetch data
        queryClient.invalidateQueries(['automated-cycle-current'])
        queryClient.invalidateQueries(['automated-predictions-history'])
        
        toast.success(`New automated prediction: ${data.symbol} ${data.direction}`, {
          duration: 4000,
          icon: '🤖',
        })
      })

      // Subscribe to 4-hour decision events
      socket.on('four_hour_decision_created', (data: Decision) => {
        console.log('4-hour decision created:', data)
        
        lastMessageRef.current = {
          type: 'four_hour_decision_created',
          data,
          timestamp: Date.now(),
        }

        // Invalidate queries to refetch data
        queryClient.invalidateQueries(['automated-decision-latest'])
        queryClient.invalidateQueries(['automated-cycle-current'])
        
        toast.success(`New 4H decision: ${data.final_signal} (${Math.round(data.confidence * 100)}%)`, {
          duration: 5000,
          icon: '📊',
        })
      })

      // Cleanup on unmount
      return () => {
        socket.off('automated_prediction_created')
        socket.off('four_hour_decision_created')
        socket.disconnect()
        socketRef.current = null
      }
    }).catch((err) => {
      console.error('Failed to load socket.io-client:', err)
    })

    // Cleanup function
    return () => {
      if (socketRef.current) {
        socketRef.current.disconnect()
      }
    }
  }, [queryClient])

  /**
   * Fetch history with custom parameters
   */
  const fetchHistoryWithParams = useCallback(
    async (params?: HistoryParams) => {
      try {
        const response = await api.get(`${API_BASE_URL}/v1/automated/predictions/history`, {
          params: {
            limit: params?.limit || 20,
            offset: params?.offset || 0,
            ...(params?.symbol && { symbol: params.symbol }),
            ...(params?.cycle_id && { cycle_id: params.cycle_id }),
          },
        })
        
        // Update query cache
        queryClient.setQueryData(['automated-predictions-history'], response.data?.data || { predictions: [], total: 0 })
        
        return response.data?.data
      } catch (err: any) {
        const errorMessage = err.response?.data?.error || err.message || 'Failed to fetch history'
        setError(errorMessage)
        console.error('Fetch history error:', err)
        throw err
      }
    },
    [queryClient]
  )

  /**
   * Computed loading state
   */
  const loading = cycleLoading || decisionLoading || historyLoading || statusLoading

  /**
   * Combined error state
   */
  const combinedError = error || 
    (cycleError as any)?.message || 
    (decisionError as any)?.message || 
    (historyError as any)?.message || 
    (statusError as any)?.message || 
    null

  return {
    // State
    currentCycle: currentCycle || null,
    latestDecision: latestDecision || null,
    predictionHistory: historyData?.predictions || [],
    schedulerStatus: schedulerStatus || null,
    loading,
    error: combinedError,

    // Methods
    refetchCycle: refetchCycle as () => Promise<void>,
    refetchDecision: refetchDecision as () => Promise<void>,
    refetchHistory: fetchHistoryWithParams,
    triggerPrediction: triggerMutation.mutate as () => Promise<void>,
    
    // Additional state
    isTriggering: triggerMutation.isLoading,
    lastMessage: lastMessageRef.current,
  }
}

export default useAutomatedPredictions
