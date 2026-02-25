/**
 * WebSocket Server
 * Real-time communication for market updates and predictions
 */

const socketIo = require('socket.io');
const logger = require('../config/logger');
const config = require('../config');
const {
  trackWebSocketConnection,
  trackWebSocketMessage
} = require('../middleware/metrics');
const connectionManager = require('./connectionManager');
const marketDataFetcher = require('./marketDataFetcher');
const claudeEngineClient = require('./claudeEngineClient');
const consoleNamespace = require('./consoleNamespace');

class WebSocketServer {
  constructor() {
    this.io = null;
    this.broadcastInterval = null;
    this.connectedClients = new Set();
    this.subscriptions = new Map(); // symbol -> Set of socket IDs
    this.clientRequestCounts = new Map(); // socketId -> {count, resetTime} for rate limiting
  }

  /**
   * Initialize WebSocket server
   */
  initialize(httpServer) {
    this.io = socketIo(httpServer, {
      cors: {
        origin: config.cors.origin,
        methods: ['GET', 'POST'],
        credentials: true
      },
      pingInterval: config.websocket.pingInterval,
      pingTimeout: config.websocket.pingTimeout
    });

    this.setupEventHandlers();
    this.startBroadcasting();
    this.startMarketDataFetcher();
    this.initializeConsoleNamespace();

    logger.info('WebSocket server initialized', {
      pingInterval: config.websocket.pingInterval,
      pingTimeout: config.websocket.pingTimeout
    });
  }

  /**
   * Setup socket event handlers
   */
  setupEventHandlers() {
    this.io.on('connection', (socket) => {
      logger.info('Client connected', { socketId: socket.id });
      
      // Register connection
      this.connectedClients.add(socket.id);
      connectionManager.addConnection(socket.id, {
        userAgent: socket.handshake.headers['user-agent'],
        ip: socket.handshake.address
      });
      trackWebSocketConnection(true);

      // Handle subscription to specific symbols
      socket.on('subscribe', (data) => {
        this.handleSubscribe(socket, data);
      });

      // Handle unsubscribe from symbols
      socket.on('unsubscribe', (data) => {
        this.handleUnsubscribe(socket, data);
      });

      // Handle prediction request
      socket.on('request_prediction', async (data) => {
        await this.handlePredictionRequest(socket, data);
      });

      // Handle ping (heartbeat from client)
      socket.on('ping', () => {
        connectionManager.updateActivity(socket.id);
        socket.emit('pong', { timestamp: Date.now() });
      });

      // Handle disconnection
      socket.on('disconnect', (reason) => {
        logger.info('Client disconnected', { 
          socketId: socket.id, 
          reason 
        });
        
        this.connectedClients.delete(socket.id);
        this.cleanupSubscriptions(socket.id);
        connectionManager.removeConnection(socket.id);
        this.clientRequestCounts.delete(socket.id);
        trackWebSocketConnection(false);
      });

      // Handle errors
      socket.on('error', (error) => {
        logger.error('Socket error', { 
          socketId: socket.id, 
          error: error.message 
        });
        connectionManager.trackError(socket.id, error);
      });

      // Send initial connection acknowledgment with available symbols
      socket.emit('connected', {
        clientId: socket.id,
        timestamp: new Date().toISOString(),
        serverTime: Date.now(),
        availableSymbols: marketDataFetcher.activeSymbols 
          ? Array.from(marketDataFetcher.activeSymbols) 
          : ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT']
      });
    });
  }

  /**
   * Handle subscription to symbol updates
   */
  handleSubscribe(socket, data) {
    trackWebSocketMessage('inbound', 'subscribe');
    connectionManager.trackMessageIn(socket.id, JSON.stringify(data).length);

    const { symbol } = data;
    
    if (!symbol) {
      socket.emit('error', { message: 'Symbol is required for subscription' });
      return;
    }

    // Join room for this symbol
    socket.join(`symbol:${symbol}`);

    // Track subscription in both maps
    if (!this.subscriptions.has(symbol)) {
      this.subscriptions.set(symbol, new Set());
    }
    this.subscriptions.get(symbol).add(socket.id);
    connectionManager.subscribe(socket.id, symbol);

    // Add symbol to market data fetcher if not already present
    marketDataFetcher.addSymbol(symbol);

    logger.info('Client subscribed', { 
      socketId: socket.id, 
      symbol,
      totalSubscribers: this.subscriptions.get(symbol).size
    });

    // Send cached market data immediately if available
    const cachedData = marketDataFetcher.getCachedData(symbol);
    if (cachedData) {
      socket.emit('market_update', cachedData);
    }

    socket.emit('subscribed', { 
      symbol, 
      timestamp: new Date().toISOString() 
    });
  }

  /**
   * Handle unsubscribe from symbol updates
   */
  handleUnsubscribe(socket, data) {
    trackWebSocketMessage('inbound', 'unsubscribe');
    connectionManager.trackMessageIn(socket.id, JSON.stringify(data).length);

    const { symbol } = data;
    
    if (!symbol) {
      socket.emit('error', { message: 'Symbol is required for unsubscription' });
      return;
    }

    // Leave room
    socket.leave(`symbol:${symbol}`);

    // Remove from subscriptions
    if (this.subscriptions.has(symbol)) {
      this.subscriptions.get(symbol).delete(socket.id);
      
      if (this.subscriptions.get(symbol).size === 0) {
        this.subscriptions.delete(symbol);
      }
    }
    connectionManager.unsubscribe(socket.id, symbol);

    logger.info('Client unsubscribed', { 
      socketId: socket.id, 
      symbol 
    });

    socket.emit('unsubscribed', { 
      symbol, 
      timestamp: new Date().toISOString() 
    });
  }

  /**
   * Handle prediction request
   */
  async handlePredictionRequest(socket, data) {
    trackWebSocketMessage('inbound', 'request_prediction');
    connectionManager.trackMessageIn(socket.id, JSON.stringify(data).length);

    // Rate limiting: max 10 requests per minute
    if (!this.checkRateLimit(socket.id, 10, 60000)) {
      socket.emit('error', { 
        message: 'Rate limit exceeded. Maximum 10 prediction requests per minute.',
        code: 'RATE_LIMIT_EXCEEDED'
      });
      return;
    }

    const { symbol, strategy } = data;
    
    if (!symbol) {
      socket.emit('error', { message: 'Symbol is required for prediction request' });
      return;
    }

    logger.info('Prediction requested via WebSocket', { 
      socketId: socket.id, 
      symbol,
      strategy 
    });

    // Acknowledge request
    socket.emit('prediction_requested', { 
      symbol, 
      timestamp: new Date().toISOString(),
      message: 'Prediction request received and processing'
    });

    try {
      // Trigger prediction via Claude Engine
      const prediction = await claudeEngineClient.triggerPrediction(symbol, { strategy });

      // Broadcast prediction to all subscribers of this symbol
      this.broadcastToSymbol(symbol, 'prediction', prediction);

    } catch (error) {
      logger.error('Prediction request failed', {
        socketId: socket.id,
        symbol,
        error: error.message
      });

      socket.emit('prediction_error', {
        symbol,
        message: 'Failed to generate prediction',
        error: error.message,
        timestamp: new Date().toISOString()
      });
    }
  }

  /**
   * Cleanup subscriptions when client disconnects
   */
  cleanupSubscriptions(socketId) {
    for (const [symbol, subscribers] of this.subscriptions.entries()) {
      subscribers.delete(socketId);
      
      if (subscribers.size === 0) {
        this.subscriptions.delete(symbol);
      }
    }
  }

  /**
   * Broadcast message to all connected clients
   */
  broadcast(event, data) {
    trackWebSocketMessage('outbound', event);
    
    this.io.emit(event, {
      ...data,
      timestamp: new Date().toISOString()
    });

    logger.debug('Broadcast message', { 
      event, 
      recipients: this.connectedClients.size 
    });
  }

  /**
   * Broadcast to specific symbol subscribers
   */
  broadcastToSymbol(symbol, event, data) {
    trackWebSocketMessage('outbound', event);
    
    this.io.to(`symbol:${symbol}`).emit(event, {
      ...data,
      symbol,
      timestamp: new Date().toISOString()
    });

    const subscriberCount = this.subscriptions.get(symbol)?.size || 0;
    
    logger.debug('Broadcast to symbol', { 
      symbol, 
      event, 
      recipients: subscriberCount 
    });
  }

  /**
   * Broadcast market update
   */
  broadcastMarketUpdate(marketData) {
    const { symbol } = marketData;
    
    if (symbol) {
      this.broadcastToSymbol(symbol, 'market_update', marketData);
    } else {
      this.broadcast('market_update', marketData);
    }
  }

  /**
   * Broadcast prediction result
   */
  broadcastPrediction(prediction) {
    const { symbol } = prediction;
    
    if (symbol) {
      this.broadcastToSymbol(symbol, 'prediction', prediction);
    } else {
      this.broadcast('prediction', prediction);
    }
  }

  /**
   * Broadcast automated prediction created event
   */
  broadcastAutomatedPrediction(prediction) {
    const { symbol } = prediction;
    
    trackWebSocketMessage('outbound', 'automated_prediction_created');
    
    this.broadcast('automated_prediction_created', {
      ...prediction,
      timestamp: new Date().toISOString()
    });
    
    logger.info('Broadcasted automated prediction', { 
      predictionId: prediction.id,
      symbol,
      cycleHour: prediction.cycle_hour,
      recipients: this.connectedClients.size 
    });
  }

  /**
   * Broadcast 4-hour decision created event
   */
  broadcastFourHourDecision(decision) {
    const { symbol } = decision;
    
    trackWebSocketMessage('outbound', 'four_hour_decision_created');
    
    this.broadcast('four_hour_decision_created', {
      ...decision,
      timestamp: new Date().toISOString()
    });
    
    logger.info('Broadcasted 4-hour decision', { 
      decisionId: decision.id,
      symbol,
      finalDecision: decision.final_decision,
      recipients: this.connectedClients.size 
    });
  }

  /**
   * Start periodic broadcasting
   */
  startBroadcasting() {
    const interval = config.websocket.broadcastInterval;

    this.broadcastInterval = setInterval(() => {
      if (this.connectedClients.size > 0) {
        this.broadcast('heartbeat', {
          connectedClients: this.connectedClients.size,
          subscriptions: Array.from(this.subscriptions.keys())
        });
      }
    }, interval);

    logger.info('WebSocket broadcasting started', { 
      interval: `${interval}ms` 
    });
  }

  /**
   * Stop broadcasting
   */
  stopBroadcasting() {
    if (this.broadcastInterval) {
      clearInterval(this.broadcastInterval);
      this.broadcastInterval = null;
      logger.info('WebSocket broadcasting stopped');
    }
  }

  /**
   * Get current statistics
   */
  getStats() {
    return {
      connectedClients: this.connectedClients.size,
      subscriptions: Array.from(this.subscriptions.entries()).map(([symbol, subscribers]) => ({
        symbol,
        subscriberCount: subscribers.size
      })),
      totalSubscriptions: this.subscriptions.size
    };
  }

  /**
   * Start market data fetcher
   */
  startMarketDataFetcher() {
    // Callback to broadcast market updates
    const broadcastCallback = (event, data) => {
      if (data.symbol) {
        this.broadcastToSymbol(data.symbol, event, data);
      } else {
        this.broadcast(event, data);
      }
    };

    marketDataFetcher.start(broadcastCallback);
    logger.info('Market data fetcher started');
  }

  /**
   * Initialize console namespace for browser developer console access
   */
  initializeConsoleNamespace() {
    consoleNamespace.initialize(this.io);
    logger.info('Console namespace initialized');
  }

  /**
   * Check rate limit for client
   */
  checkRateLimit(socketId, maxRequests, windowMs) {
    const now = Date.now();
    const clientData = this.clientRequestCounts.get(socketId);

    if (!clientData || now > clientData.resetTime) {
      // New window
      this.clientRequestCounts.set(socketId, {
        count: 1,
        resetTime: now + windowMs
      });
      return true;
    }

    if (clientData.count >= maxRequests) {
      return false;
    }

    clientData.count++;
    return true;
  }

  /**
   * Shutdown WebSocket server
   */
  shutdown() {
    logger.info('Shutting down WebSocket server');
    
    this.stopBroadcasting();
    marketDataFetcher.stop();
    
    if (this.io) {
      this.io.close(() => {
        logger.info('WebSocket server closed');
      });
    }
  }
}

// Export singleton instance
module.exports = new WebSocketServer();
