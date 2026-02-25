/**
 * WebSocket Context
 * Provides real-time WebSocket connection to the entire app
 * Features: auto-reconnect, connection status, market data, predictions
 */

import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react';
import io from 'socket.io-client';
import toast from 'react-hot-toast';

const WebSocketContext = createContext(null);

const WEBSOCKET_URL = process.env.REACT_APP_WS_URL || 'http://localhost:8100';
const RECONNECT_DELAYS = [1000, 2000, 4000, 8000, 16000, 30000]; // Exponential backoff

export function WebSocketProvider({ children }) {
  const [socket, setSocket] = useState(null);
  const [connected, setConnected] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [marketData, setMarketData] = useState({});
  const [latestPrediction, setLatestPrediction] = useState(null);
  const [availableSymbols, setAvailableSymbols] = useState([]);
  
  const reconnectAttempt = useRef(0);
  const reconnectTimer = useRef(null);
  const heartbeatTimer = useRef(null);
  const subscriptionsRef = useRef(new Set());

  /**
   * Initialize WebSocket connection
   */
  const connect = useCallback(() => {
    if (socket?.connected) {
      console.log('WebSocket already connected');
      return;
    }

    setConnecting(true);
    console.log('Connecting to WebSocket server:', WEBSOCKET_URL);

    const ws = io(WEBSOCKET_URL, {
      transports: ['websocket', 'polling'],
      reconnection: false, // We handle reconnection manually
      timeout: 10000
    });

    // Connection established
    ws.on('connect', () => {
      console.log('WebSocket connected', ws.id);
      setConnected(true);
      setConnecting(false);
      reconnectAttempt.current = 0;
      
      toast.success('Connected to real-time updates', {
        id: 'ws-context-connected',
        duration: 2000,
        icon: '🟢'
      });

      // Start heartbeat
      startHeartbeat(ws);
    });

    // Initial connection acknowledgment
    ws.on('connected', (data) => {
      console.log('Connection acknowledged:', data);
      setAvailableSymbols(data.availableSymbols || []);

      // Resubscribe to previous subscriptions
      subscriptionsRef.current.forEach(symbol => {
        ws.emit('subscribe', { symbol });
      });
    });

    // Market data updates
    ws.on('market_update', (data) => {
      console.log('Market update received:', data.symbol, data.price);
      setMarketData(prev => ({
        ...prev,
        [data.symbol]: data
      }));
    });

    // Prediction updates
    ws.on('prediction', (prediction) => {
      console.log('Prediction received:', prediction.symbol, prediction.direction);
      setLatestPrediction(prediction);
      
      toast.success(`New prediction for ${prediction.symbol}: ${prediction.direction}`, {
        duration: 4000,
        icon: '🔮'
      });
    });

    // Subscription confirmed
    ws.on('subscribed', (data) => {
      console.log('Subscribed to:', data.symbol);
      subscriptionsRef.current.add(data.symbol);
    });

    // Unsubscription confirmed
    ws.on('unsubscribed', (data) => {
      console.log('Unsubscribed from:', data.symbol);
      subscriptionsRef.current.delete(data.symbol);
    });

    // Heartbeat from server
    ws.on('heartbeat', (data) => {
      console.log('Heartbeat received:', data);
    });

    // Pong response
    ws.on('pong', (data) => {
      // Heartbeat acknowledged
      console.log('Pong received');
    });

    // Errors
    ws.on('error', (error) => {
      console.error('WebSocket error:', error);
      toast.error('Connection error: ' + error.message, {
        duration: 3000,
        icon: '⚠️'
      });
    });

    // Disconnection
    ws.on('disconnect', (reason) => {
      console.log('WebSocket disconnected:', reason);
      setConnected(false);
      stopHeartbeat();
      
      if (reason !== 'io client disconnect') {
        toast.error('Disconnected from server', {
          duration: 3000,
          icon: '🔴'
        });
        scheduleReconnect();
      }
    });

    // Connection error
    ws.on('connect_error', (error) => {
      console.error('Connection error:', error);
      setConnecting(false);
      scheduleReconnect();
    });

    setSocket(ws);

    return ws;
  }, []);

  /**
   * Schedule reconnection with exponential backoff
   */
  const scheduleReconnect = useCallback(() => {
    if (reconnectTimer.current) {
      return; // Already scheduled
    }

    const delay = RECONNECT_DELAYS[Math.min(reconnectAttempt.current, RECONNECT_DELAYS.length - 1)];
    console.log(`Reconnecting in ${delay}ms (attempt ${reconnectAttempt.current + 1})`);

    reconnectTimer.current = setTimeout(() => {
      reconnectAttempt.current++;
      reconnectTimer.current = null;
      connect();
    }, delay);
  }, [connect]);

  /**
   * Start heartbeat (ping every 30s)
   */
  const startHeartbeat = (ws) => {
    stopHeartbeat();
    
    heartbeatTimer.current = setInterval(() => {
      if (ws.connected) {
        ws.emit('ping');
      }
    }, 30000);
  };

  /**
   * Stop heartbeat
   */
  const stopHeartbeat = () => {
    if (heartbeatTimer.current) {
      clearInterval(heartbeatTimer.current);
      heartbeatTimer.current = null;
    }
  };

  /**
   * Subscribe to symbol updates
   */
  const subscribe = useCallback((symbol) => {
    if (!socket || !connected) {
      console.warn('Cannot subscribe: not connected');
      return;
    }

    console.log('Subscribing to:', symbol);
    socket.emit('subscribe', { symbol });
  }, [socket, connected]);

  /**
   * Unsubscribe from symbol updates
   */
  const unsubscribe = useCallback((symbol) => {
    if (!socket || !connected) {
      console.warn('Cannot unsubscribe: not connected');
      return;
    }

    console.log('Unsubscribing from:', symbol);
    socket.emit('unsubscribe', { symbol });
  }, [socket, connected]);

  /**
   * Request prediction for symbol
   */
  const requestPrediction = useCallback((symbol, strategy = 'balanced') => {
    if (!socket || !connected) {
      toast.error('Cannot request prediction: not connected', {
        duration: 3000
      });
      return;
    }

    console.log('Requesting prediction for:', symbol, 'Strategy:', strategy);
    socket.emit('request_prediction', { symbol, strategy });
    
    toast.loading('Generating prediction...', {
      duration: 2000,
      icon: '⏳'
    });
  }, [socket, connected]);

  /**
   * Disconnect manually
   */
  const disconnect = useCallback(() => {
    if (socket) {
      console.log('Disconnecting WebSocket');
      socket.disconnect();
      stopHeartbeat();
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current);
        reconnectTimer.current = null;
      }
    }
  }, [socket]);

  // Initialize connection on mount
  useEffect(() => {
    connect();

    return () => {
      disconnect();
    };
  }, []);

  const value = {
    socket,
    connected,
    connecting,
    marketData,
    latestPrediction,
    availableSymbols,
    subscribe,
    unsubscribe,
    requestPrediction,
    disconnect,
    reconnect: connect
  };

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  );
}

/**
 * Hook to access WebSocket context
 */
export function useWebSocket() {
  const context = useContext(WebSocketContext);
  
  if (!context) {
    throw new Error('useWebSocket must be used within a WebSocketProvider');
  }
  
  return context;
}

export default WebSocketContext;
