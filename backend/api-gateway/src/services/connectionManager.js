/**
 * Connection Manager
 * Tracks WebSocket connections, subscriptions, and metrics
 */

const logger = require('../config/logger');

class ConnectionManager {
  constructor() {
    // Connection tracking
    this.connections = new Map(); // socketId -> connection info
    this.subscriptions = new Map(); // symbol -> Set of socketIds
    
    // Performance metrics
    this.metrics = {
      totalConnections: 0,
      currentConnections: 0,
      peakConnections: 0,
      totalMessages: 0,
      messagesIn: 0,
      messagesOut: 0,
      bytesIn: 0,
      bytesOut: 0,
      totalDataSent: 0,
      averageLatency: 0,
      errors: 0
    };

    // Connection history (last 100)
    this.connectionHistory = [];
    this.maxHistorySize = 100;
  }

  /**
   * Register new connection
   */
  addConnection(socketId, metadata = {}) {
    const connectionInfo = {
      socketId,
      connectedAt: Date.now(),
      lastActivity: Date.now(),
      metadata: {
        userAgent: metadata.userAgent || 'unknown',
        ip: metadata.ip || 'unknown',
        ...metadata
      },
      subscriptions: new Set(),
      messageCount: 0,
      bytesSent: 0,
      bytesReceived: 0
    };

    this.connections.set(socketId, connectionInfo);
    this.metrics.totalConnections++;
    this.metrics.currentConnections++;

    // Track peak connections
    if (this.metrics.currentConnections > this.metrics.peakConnections) {
      this.metrics.peakConnections = this.metrics.currentConnections;
    }

    // Add to history
    this.addToHistory({
      type: 'connect',
      socketId,
      timestamp: Date.now()
    });

    logger.info('Connection registered', {
      socketId,
      currentConnections: this.metrics.currentConnections,
      metadata: connectionInfo.metadata
    });

    return connectionInfo;
  }

  /**
   * Remove connection
   */
  removeConnection(socketId) {
    const connection = this.connections.get(socketId);
    
    if (!connection) {
      logger.warn('Attempted to remove non-existent connection', { socketId });
      return;
    }

    // Calculate session duration
    const sessionDuration = Date.now() - connection.connectedAt;

    // Remove from all subscriptions
    connection.subscriptions.forEach(symbol => {
      this.unsubscribe(socketId, symbol);
    });

    this.connections.delete(socketId);
    this.metrics.currentConnections--;

    // Add to history
    this.addToHistory({
      type: 'disconnect',
      socketId,
      timestamp: Date.now(),
      sessionDuration,
      messageCount: connection.messageCount
    });

    logger.info('Connection removed', {
      socketId,
      sessionDuration: `${(sessionDuration / 1000).toFixed(2)}s`,
      messageCount: connection.messageCount,
      currentConnections: this.metrics.currentConnections
    });
  }

  /**
   * Subscribe connection to symbol
   */
  subscribe(socketId, symbol) {
    const connection = this.connections.get(socketId);
    
    if (!connection) {
      logger.warn('Cannot subscribe non-existent connection', { socketId, symbol });
      return false;
    }

    // Add to connection's subscriptions
    connection.subscriptions.add(symbol);

    // Add to symbol's subscribers
    if (!this.subscriptions.has(symbol)) {
      this.subscriptions.set(symbol, new Set());
    }
    this.subscriptions.get(symbol).add(socketId);

    logger.debug('Subscription added', {
      socketId,
      symbol,
      totalSubscribers: this.subscriptions.get(symbol).size
    });

    return true;
  }

  /**
   * Unsubscribe connection from symbol
   */
  unsubscribe(socketId, symbol) {
    const connection = this.connections.get(socketId);
    
    if (connection) {
      connection.subscriptions.delete(symbol);
    }

    const subscribers = this.subscriptions.get(symbol);
    if (subscribers) {
      subscribers.delete(socketId);
      
      // Remove symbol if no subscribers
      if (subscribers.size === 0) {
        this.subscriptions.delete(symbol);
        logger.debug('Symbol removed (no subscribers)', { symbol });
      }
    }

    logger.debug('Subscription removed', {
      socketId,
      symbol,
      remainingSubscribers: subscribers?.size || 0
    });

    return true;
  }

  /**
   * Update connection activity
   */
  updateActivity(socketId) {
    const connection = this.connections.get(socketId);
    if (connection) {
      connection.lastActivity = Date.now();
    }
  }

  /**
   * Track incoming message
   */
  trackMessageIn(socketId, messageSize = 0) {
    const connection = this.connections.get(socketId);
    
    if (connection) {
      connection.messageCount++;
      connection.bytesReceived += messageSize;
      connection.lastActivity = Date.now();
    }

    this.metrics.totalMessages++;
    this.metrics.messagesIn++;
    this.metrics.bytesIn += messageSize;
  }

  /**
   * Track outgoing message
   */
  trackMessageOut(socketId, messageSize = 0) {
    const connection = this.connections.get(socketId);
    
    if (connection) {
      connection.bytesSent += messageSize;
    }

    this.metrics.messagesOut++;
    this.metrics.bytesOut += messageSize;
    this.metrics.totalDataSent += messageSize;
  }

  /**
   * Track error
   */
  trackError(socketId, error) {
    this.metrics.errors++;
    
    logger.error('Connection error tracked', {
      socketId,
      error: error.message,
      totalErrors: this.metrics.errors
    });
  }

  /**
   * Get subscribers for symbol
   */
  getSubscribers(symbol) {
    return Array.from(this.subscriptions.get(symbol) || []);
  }

  /**
   * Get all symbols with subscribers
   */
  getActiveSymbols() {
    return Array.from(this.subscriptions.keys());
  }

  /**
   * Get connection info
   */
  getConnection(socketId) {
    return this.connections.get(socketId);
  }

  /**
   * Get all connections
   */
  getAllConnections() {
    return Array.from(this.connections.values());
  }

  /**
   * Get stale connections (no activity in last N minutes)
   */
  getStaleConnections(inactiveMinutes = 10) {
    const staleThreshold = Date.now() - (inactiveMinutes * 60 * 1000);
    const staleConnections = [];

    this.connections.forEach((connection, socketId) => {
      if (connection.lastActivity < staleThreshold) {
        staleConnections.push({
          socketId,
          lastActivity: connection.lastActivity,
          inactiveDuration: Date.now() - connection.lastActivity
        });
      }
    });

    return staleConnections;
  }

  /**
   * Add event to history
   */
  addToHistory(event) {
    this.connectionHistory.push(event);

    // Keep only last N events
    if (this.connectionHistory.length > this.maxHistorySize) {
      this.connectionHistory.shift();
    }
  }

  /**
   * Get connection statistics
   */
  getStats() {
    const connections = Array.from(this.connections.values());
    
    return {
      metrics: { ...this.metrics },
      connections: {
        current: this.metrics.currentConnections,
        total: this.metrics.totalConnections,
        peak: this.metrics.peakConnections,
        active: connections.length,
        stale: this.getStaleConnections(5).length
      },
      subscriptions: {
        activeSymbols: this.subscriptions.size,
        totalSubscriptions: Array.from(this.subscriptions.values())
          .reduce((sum, set) => sum + set.size, 0),
        bySymbol: Array.from(this.subscriptions.entries()).map(([symbol, subscribers]) => ({
          symbol,
          subscriberCount: subscribers.size
        }))
      },
      performance: {
        avgMessagesPerConnection: connections.length > 0 
          ? (this.metrics.totalMessages / connections.length).toFixed(2)
          : 0,
        avgBytesPerConnection: connections.length > 0
          ? (this.metrics.totalDataSent / connections.length).toFixed(2)
          : 0,
        errorRate: this.metrics.totalMessages > 0
          ? ((this.metrics.errors / this.metrics.totalMessages) * 100).toFixed(2)
          : 0
      }
    };
  }

  /**
   * Get detailed stats for specific connection
   */
  getConnectionStats(socketId) {
    const connection = this.connections.get(socketId);
    
    if (!connection) {
      return null;
    }

    const sessionDuration = Date.now() - connection.connectedAt;
    const inactiveDuration = Date.now() - connection.lastActivity;

    return {
      socketId,
      connectedAt: new Date(connection.connectedAt).toISOString(),
      sessionDuration: `${(sessionDuration / 1000).toFixed(2)}s`,
      lastActivity: new Date(connection.lastActivity).toISOString(),
      inactiveDuration: `${(inactiveDuration / 1000).toFixed(2)}s`,
      subscriptions: Array.from(connection.subscriptions),
      messageCount: connection.messageCount,
      bytesSent: connection.bytesSent,
      bytesReceived: connection.bytesReceived,
      metadata: connection.metadata
    };
  }

  /**
   * Reset metrics (for testing)
   */
  resetMetrics() {
    this.metrics = {
      totalConnections: 0,
      currentConnections: this.connections.size,
      peakConnections: this.connections.size,
      totalMessages: 0,
      messagesIn: 0,
      messagesOut: 0,
      bytesIn: 0,
      bytesOut: 0,
      totalDataSent: 0,
      averageLatency: 0,
      errors: 0
    };

    logger.info('Connection metrics reset');
  }
}

// Export singleton instance
module.exports = new ConnectionManager();
