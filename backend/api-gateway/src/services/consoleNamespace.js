/**
 * Console Namespace Handler
 * Browser developer console interface via WebSocket
 *
 * Enables real-time interaction with ClaudeTrader Pro from any browser console
 */

const jwt = require('jsonwebtoken');
const config = require('../config');
const logger = require('../config/logger');
const claudeEngineClient = require('./claudeEngineClient');
const connectionManager = require('./connectionManager');
const marketDataFetcher = require('./marketDataFetcher');

// Token configuration
const TOKEN_EXPIRY = '1h';
const TOKEN_ISSUER = 'claude-trader-console';

// Rate limit configuration per command (requests per minute)
const RATE_LIMITS = {
  help: null,           // No limit
  ping: null,           // No limit
  status: 10,
  market: 30,
  predict: 5,
  history: 10,
  trades: 10,
  sentiment: 30,
  analytics: 10,
  subscribe: 10,
  unsubscribe: 10,
  connections: 10
};

// Command handlers registry
const COMMAND_HANDLERS = {};

class ConsoleNamespace {
  constructor() {
    this.io = null;
    this.namespace = null;
    this.connectedSockets = new Map(); // socketId -> { token, ip, connectedAt, rateLimits }
  }

  /**
   * Initialize console namespace on Socket.IO server
   */
  initialize(io) {
    this.io = io;
    this.namespace = io.of('/console');

    // Apply authentication middleware
    this.namespace.use((socket, next) => {
      this.authenticateSocket(socket, next);
    });

    // Setup connection handler
    this.namespace.on('connection', (socket) => {
      this.handleConnection(socket);
    });

    logger.info('Console namespace initialized on /console');
  }

  /**
   * Generate console access token
   */
  generateToken(metadata = {}) {
    if (!config.security.jwtSecret) {
      throw new Error('JWT_SECRET not configured - cannot generate console token');
    }

    const payload = {
      type: 'console',
      iss: TOKEN_ISSUER,
      ...metadata
    };

    const token = jwt.sign(payload, config.security.jwtSecret, {
      expiresIn: TOKEN_EXPIRY
    });

    logger.info('Console token generated', {
      ip: metadata.ip,
      expiresIn: TOKEN_EXPIRY
    });

    return token;
  }

  /**
   * Authenticate socket connection
   */
  authenticateSocket(socket, next) {
    const token = socket.handshake.auth?.token || socket.handshake.query?.token;

    if (!token) {
      logger.warn('Console connection rejected: no token', {
        ip: socket.handshake.address
      });
      return next(new Error('Authentication required. Provide token via auth.token'));
    }

    if (!config.security.jwtSecret) {
      logger.error('Console connection rejected: JWT_SECRET not configured');
      return next(new Error('Authentication service unavailable'));
    }

    try {
      const decoded = jwt.verify(token, config.security.jwtSecret);

      if (decoded.type !== 'console' || decoded.iss !== TOKEN_ISSUER) {
        logger.warn('Console connection rejected: invalid token type', {
          ip: socket.handshake.address
        });
        return next(new Error('Invalid console token'));
      }

      // Attach token data to socket
      socket.tokenData = decoded;
      next();

    } catch (err) {
      logger.warn('Console connection rejected: invalid token', {
        ip: socket.handshake.address,
        error: err.message
      });
      return next(new Error(err.name === 'TokenExpiredError' ? 'Token expired' : 'Invalid token'));
    }
  }

  /**
   * Handle new console connection
   */
  handleConnection(socket) {
    const ip = socket.handshake.address;
    const connectedAt = Date.now();

    // Store connection metadata
    this.connectedSockets.set(socket.id, {
      token: socket.tokenData,
      ip,
      connectedAt,
      rateLimits: new Map()
    });

    logger.info('Console client connected', {
      socketId: socket.id,
      ip
    });

    // Send connection acknowledgment
    socket.emit('connected', {
      socketId: socket.id,
      serverTime: Date.now(),
      availableCommands: Object.keys(COMMAND_HANDLERS),
      message: 'Connected to ClaudeTrader Console. Type trader.help() for available commands.'
    });

    // Handle command execution
    socket.on('command', async (data) => {
      await this.handleCommand(socket, data);
    });

    // Handle disconnection
    socket.on('disconnect', (reason) => {
      this.connectedSockets.delete(socket.id);
      logger.info('Console client disconnected', {
        socketId: socket.id,
        ip,
        reason,
        sessionDuration: `${((Date.now() - connectedAt) / 1000).toFixed(1)}s`
      });
    });
  }

  /**
   * Handle command execution
   */
  async handleCommand(socket, data) {
    const startTime = Date.now();
    const { command, args = [] } = data;
    const socketData = this.connectedSockets.get(socket.id);

    // Log command
    logger.info('Console command', {
      socketId: socket.id,
      command,
      args,
      ip: socketData?.ip
    });

    // Validate command exists
    if (!COMMAND_HANDLERS[command]) {
      socket.emit('command_result', {
        command,
        success: false,
        error: `Unknown command: ${command}. Use 'help' for available commands.`,
        latency_ms: Date.now() - startTime
      });
      return;
    }

    // Check rate limit
    const limit = RATE_LIMITS[command];
    if (limit && !this.checkRateLimit(socket.id, command, limit)) {
      socket.emit('command_result', {
        command,
        success: false,
        error: `Rate limit exceeded for '${command}'. Max ${limit} requests per minute.`,
        code: 'RATE_LIMIT_EXCEEDED',
        latency_ms: Date.now() - startTime
      });

      logger.warn('Console rate limit exceeded', {
        socketId: socket.id,
        command,
        limit,
        ip: socketData?.ip
      });
      return;
    }

    try {
      // Execute command handler
      const result = await COMMAND_HANDLERS[command](args, socket, this);

      socket.emit('command_result', {
        command,
        success: true,
        data: result,
        latency_ms: Date.now() - startTime
      });

      logger.debug('Console command completed', {
        socketId: socket.id,
        command,
        latency_ms: Date.now() - startTime
      });

    } catch (error) {
      socket.emit('command_result', {
        command,
        success: false,
        error: error.message || 'Command execution failed',
        latency_ms: Date.now() - startTime
      });

      logger.error('Console command failed', {
        socketId: socket.id,
        command,
        error: error.message,
        latency_ms: Date.now() - startTime
      });
    }
  }

  /**
   * Check rate limit for command
   */
  checkRateLimit(socketId, command, maxRequests) {
    const socketData = this.connectedSockets.get(socketId);
    if (!socketData) return false;

    const now = Date.now();
    const windowMs = 60000; // 1 minute window
    const key = command;

    const limitData = socketData.rateLimits.get(key) || { count: 0, resetTime: now + windowMs };

    // Reset if window expired
    if (now > limitData.resetTime) {
      limitData.count = 1;
      limitData.resetTime = now + windowMs;
      socketData.rateLimits.set(key, limitData);
      return true;
    }

    // Check limit
    if (limitData.count >= maxRequests) {
      return false;
    }

    // Increment counter
    limitData.count++;
    socketData.rateLimits.set(key, limitData);
    return true;
  }

  /**
   * Get connection statistics
   */
  getStats() {
    return {
      connectedClients: this.connectedSockets.size,
      connections: Array.from(this.connectedSockets.entries()).map(([id, data]) => ({
        socketId: id,
        ip: data.ip,
        connectedAt: new Date(data.connectedAt).toISOString(),
        sessionDuration: `${((Date.now() - data.connectedAt) / 1000).toFixed(1)}s`
      }))
    };
  }
}

// Create singleton instance
const consoleNamespace = new ConsoleNamespace();

// =============================================================================
// COMMAND HANDLERS
// =============================================================================

/**
 * help - Show available commands
 */
COMMAND_HANDLERS.help = async () => {
  return {
    commands: [
      { name: 'help', description: 'Show this help message', usage: 'trader.help()' },
      { name: 'ping', description: 'Check connection latency', usage: 'trader.ping()' },
      { name: 'status', description: 'Get system health status', usage: 'trader.status()' },
      { name: 'market', description: 'Get market data', usage: 'trader.market([symbol])' },
      { name: 'predict', description: 'Generate prediction', usage: 'trader.predict(symbol)' },
      { name: 'history', description: 'Get prediction history', usage: 'trader.history([limit])' },
      { name: 'trades', description: 'Get recent trades', usage: 'trader.trades([limit])' },
      { name: 'sentiment', description: 'Get market sentiment', usage: 'trader.sentiment()' },
      { name: 'analytics', description: 'Get analytics', usage: 'trader.analytics([type])' },
      { name: 'subscribe', description: 'Subscribe to events', usage: 'trader.subscribe(event)' },
      { name: 'unsubscribe', description: 'Unsubscribe from events', usage: 'trader.unsubscribe(event)' },
      { name: 'connections', description: 'Get WebSocket stats', usage: 'trader.connections()' }
    ],
    events: ['market', 'predictions', 'trades', 'market:BTC/USDT'],
    rateLimits: Object.entries(RATE_LIMITS)
      .filter(([, v]) => v !== null)
      .map(([cmd, limit]) => `${cmd}: ${limit}/min`)
  };
};

/**
 * ping - Check latency
 */
COMMAND_HANDLERS.ping = async () => {
  return {
    pong: true,
    serverTime: Date.now(),
    timestamp: new Date().toISOString()
  };
};

/**
 * status - Get system health
 */
COMMAND_HANDLERS.status = async () => {
  let claudeEngineHealth;
  try {
    claudeEngineHealth = await claudeEngineClient.healthCheck();
  } catch (error) {
    claudeEngineHealth = { status: 'error', error: error.message };
  }

  return {
    gateway: {
      status: 'healthy',
      uptime: process.uptime(),
      memory: process.memoryUsage()
    },
    claudeEngine: claudeEngineHealth,
    websocket: connectionManager.getStats(),
    marketData: marketDataFetcher.getStats()
  };
};

/**
 * market - Get market data
 */
COMMAND_HANDLERS.market = async (args) => {
  const symbol = args[0];

  if (symbol) {
    const data = marketDataFetcher.getCachedData(symbol);
    if (!data) {
      throw new Error(`No cached data for ${symbol}. Try: BTC/USDT, ETH/USDT`);
    }
    return data;
  }

  // Return all cached data
  const allData = marketDataFetcher.getAllCachedData();
  return {
    symbols: Object.keys(allData),
    count: Object.keys(allData).length,
    data: allData
  };
};

/**
 * predict - Generate prediction
 */
COMMAND_HANDLERS.predict = async (args) => {
  const symbol = args[0];

  if (!symbol) {
    throw new Error('Symbol required. Usage: trader.predict("BTC/USDT")');
  }

  const prediction = await claudeEngineClient.triggerPrediction(symbol.toUpperCase());
  return prediction;
};

/**
 * history - Get prediction history
 */
COMMAND_HANDLERS.history = async (args) => {
  const limit = parseInt(args[0]) || 10;
  const predictions = await claudeEngineClient.getPredictions({ limit });
  return predictions;
};

/**
 * trades - Get recent trades
 */
COMMAND_HANDLERS.trades = async (args) => {
  const limit = parseInt(args[0]) || 20;
  const trades = await claudeEngineClient.request('GET', `/api/v1/trades/recent?limit=${limit}`);
  return trades;
};

/**
 * sentiment - Get market sentiment
 */
COMMAND_HANDLERS.sentiment = async () => {
  const sentiment = await claudeEngineClient.request('GET', '/api/v1/sentiment/market');
  return sentiment;
};

/**
 * analytics - Get analytics
 */
COMMAND_HANDLERS.analytics = async (args) => {
  const type = args[0] || 'accuracy';

  const endpoints = {
    accuracy: '/api/v1/accuracy',
    costs: '/api/v1/costs',
    patterns: '/api/v1/automated/analytics/patterns',
    calibration: '/api/v1/automated/analytics/calibration'
  };

  if (!endpoints[type]) {
    throw new Error(`Unknown analytics type: ${type}. Options: ${Object.keys(endpoints).join(', ')}`);
  }

  const data = await claudeEngineClient.request('GET', endpoints[type]);
  return data;
};

/**
 * subscribe - Subscribe to events
 */
COMMAND_HANDLERS.subscribe = async (args, socket) => {
  const event = args[0];

  if (!event) {
    throw new Error('Event name required. Options: market, predictions, trades, market:SYMBOL');
  }

  // Join the room for this event
  socket.join(event);

  return {
    subscribed: event,
    message: `Now receiving ${event} events`
  };
};

/**
 * unsubscribe - Unsubscribe from events
 */
COMMAND_HANDLERS.unsubscribe = async (args, socket) => {
  const event = args[0];

  if (!event) {
    throw new Error('Event name required');
  }

  socket.leave(event);

  return {
    unsubscribed: event,
    message: `Stopped receiving ${event} events`
  };
};

/**
 * connections - Get WebSocket statistics
 */
COMMAND_HANDLERS.connections = async (args, socket, namespace) => {
  const wsStats = connectionManager.getStats();
  const consoleStats = namespace.getStats();

  return {
    websocket: wsStats,
    console: consoleStats
  };
};

module.exports = consoleNamespace;
