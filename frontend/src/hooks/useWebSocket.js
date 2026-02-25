import { useState, useEffect, useCallback, useRef } from 'react'
import { io } from 'socket.io-client'
import toast from 'react-hot-toast'

const WS_URL = import.meta.env.VITE_WS_URL || window.location.origin

/**
 * Custom hook for WebSocket connection
 * Manages connection, reconnection, and real-time updates
 */
export function useWebSocket(options = {}) {
  const {
    autoConnect = true,
    reconnection = true,
    reconnectionAttempts = 5,
    reconnectionDelay = 1000,
  } = options

  const [socket, setSocket] = useState(null)
  const [connected, setConnected] = useState(false)
  const [lastMessage, setLastMessage] = useState(null)
  const [error, setError] = useState(null)
  
  const socketRef = useRef(null)
  const reconnectCountRef = useRef(0)

  useEffect(() => {
    if (!autoConnect) return

    // Create socket connection
    const newSocket = io(WS_URL, {
      reconnection,
      reconnectionAttempts,
      reconnectionDelay,
      transports: ['websocket', 'polling'],
    })

    socketRef.current = newSocket

    // Connection event handlers
    newSocket.on('connect', () => {
      console.log('WebSocket connected')
      setConnected(true)
      setError(null)
      reconnectCountRef.current = 0
      // Use toast ID to prevent duplicate notifications
      toast.success('Connected to market data stream', { id: 'ws-connected' })
    })

    newSocket.on('disconnect', (reason) => {
      console.log('WebSocket disconnected:', reason)
      setConnected(false)
      
      if (reason === 'io server disconnect') {
        // Server initiated disconnect, reconnect manually
        newSocket.connect()
      }
    })

    newSocket.on('connect_error', (err) => {
      console.error('WebSocket connection error:', err)
      setError(err.message)
      reconnectCountRef.current++
      
      if (reconnectCountRef.current === 1) {
        toast.error('Lost connection to market data', { id: 'ws-disconnected' })
      }
    })

    newSocket.on('reconnect', (attemptNumber) => {
      console.log('WebSocket reconnected after', attemptNumber, 'attempts')
      toast.success('Reconnected to market data', { id: 'ws-reconnected' })
    })

    newSocket.on('reconnect_failed', () => {
      console.error('WebSocket reconnection failed')
      setError('Failed to reconnect')
      toast.error('Unable to connect to market data. Please refresh.', { id: 'ws-failed' })
    })

    // Market data event handlers
    newSocket.on('market_update', (data) => {
      setLastMessage({ type: 'market_update', data, timestamp: Date.now() })
    })

    newSocket.on('prediction_update', (data) => {
      setLastMessage({ type: 'prediction_update', data, timestamp: Date.now() })
      toast.success(`New prediction available for ${data.symbol}`)
    })

    newSocket.on('sentiment_update', (data) => {
      setLastMessage({ type: 'sentiment_update', data, timestamp: Date.now() })
    })

    newSocket.on('system_alert', (data) => {
      setLastMessage({ type: 'system_alert', data, timestamp: Date.now() })
      
      if (data.level === 'error') {
        toast.error(data.message)
      } else if (data.level === 'warning') {
        toast(data.message, { icon: '⚠️' })
      }
    })

    setSocket(newSocket)

    // Cleanup on unmount
    return () => {
      newSocket.disconnect()
    }
  }, [autoConnect, reconnection, reconnectionAttempts, reconnectionDelay])

  // Subscribe to specific events
  const subscribe = useCallback((event, callback) => {
    if (!socketRef.current) return

    socketRef.current.on(event, callback)

    // Return unsubscribe function
    return () => {
      if (socketRef.current) {
        socketRef.current.off(event, callback)
      }
    }
  }, [])

  // Emit events
  const emit = useCallback((event, data) => {
    if (!socketRef.current || !connected) {
      console.warn('Cannot emit: socket not connected')
      return false
    }

    socketRef.current.emit(event, data)
    return true
  }, [connected])

  // Manual connect
  const connect = useCallback(() => {
    if (socketRef.current && !connected) {
      socketRef.current.connect()
    }
  }, [connected])

  // Manual disconnect
  const disconnect = useCallback(() => {
    if (socketRef.current && connected) {
      socketRef.current.disconnect()
    }
  }, [connected])

  return {
    socket,
    connected,
    lastMessage,
    error,
    subscribe,
    emit,
    connect,
    disconnect,
  }
}

export default useWebSocket
