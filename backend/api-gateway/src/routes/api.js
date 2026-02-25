/**
 * API Routes
 * All application routes with validation and error handling
 */

const express = require('express');
const router = express.Router();
const { Pool } = require('pg');
const config = require('../config');
const logger = require('../config/logger');
const claudeEngineClient = require('../services/claudeEngineClient');
const websocketServer = require('../services/websocketServer');
const connectionManager = require('../services/connectionManager');
const marketDataFetcher = require('../services/marketDataFetcher');
const consoleNamespace = require('../services/consoleNamespace');
const { asyncHandler, errors } = require('../middleware/errorHandler');
const { trackDatabaseQuery } = require('../middleware/metrics');
const {
  predictionLimiter,
  marketDataLimiter
} = require('../middleware/rateLimiter');

// Initialize PostgreSQL connection pool
const dbPool = new Pool({
  host: config.database.host,
  port: config.database.port,
  database: config.database.name,
  user: config.database.user,
  password: config.database.password,
  max: config.database.maxConnections
});

// Test database connection
dbPool.on('connect', () => {
  logger.info('Database connected');
});

dbPool.on('error', (err) => {
  logger.error('Database error', { error: err.message });
});

/**
 * Standard response format helper
 */
function successResponse(data, message = null) {
  return {
    success: true,
    data,
    error: null,
    timestamp: new Date().toISOString(),
    ...(message && { message })
  };
}

/**
 * GET /api/health - System health check
 */
router.get('/health', asyncHandler(async (req, res) => {
  const health = {
    status: 'healthy',
    service: 'claude-trader-api-gateway',
    version: config.app.version,
    environment: config.app.env,
    uptime: process.uptime(),
    timestamp: new Date().toISOString()
  };

  // Check database connection
  try {
    await dbPool.query('SELECT 1');
    health.database = 'connected';
  } catch (error) {
    health.database = 'disconnected';
    health.status = 'degraded';
  }

  // Check Claude Engine
  try {
    await claudeEngineClient.healthCheck();
    health.claudeEngine = 'available';
  } catch (error) {
    health.claudeEngine = 'unavailable';
    health.status = 'degraded';
  }

  // WebSocket stats
  health.websocket = websocketServer.getStats();

  res.json(successResponse(health));
}));

/**
 * GET /api/status - Detailed system status
 */
router.get('/status', asyncHandler(async (req, res) => {
  const status = {
    gateway: {
      version: config.app.version,
      uptime: process.uptime(),
      memory: process.memoryUsage(),
      environment: config.app.env
    },
    claudeEngine: claudeEngineClient.getStatus(),
    websocket: websocketServer.getStats(),
    database: {
      host: config.database.host,
      port: config.database.port,
      maxConnections: config.database.maxConnections
    }
  };

  res.json(successResponse(status));
}));

/**
 * GET /api/market/cached - Get all cached market data (must be before :symbol route)
 */
router.get('/market/cached', asyncHandler(async (req, res) => {
  const cachedData = marketDataFetcher.getAllCachedData();

  res.json(successResponse({
    symbols: Object.keys(cachedData),
    count: Object.keys(cachedData).length,
    data: cachedData
  }, 'Cached market data retrieved'));
}));

/**
 * GET /api/market/:symbol - Market data endpoint (not implemented yet)
 * TODO: Integrate real market data API
 */
router.get('/market/:symbol', marketDataLimiter, asyncHandler(async (req, res) => {
  const { symbol } = req.params;
  
  if (!symbol || symbol.length === 0) {
    throw errors.badRequest('Symbol is required');
  }

  logger.warn('Market data endpoint called but not implemented', { symbol });

  throw errors.notImplemented('Market data endpoint is not yet implemented. Please use prediction endpoints instead.');
}));

/**
 * POST /api/predict/:symbol - Trigger prediction for symbol
 */
router.post('/predict/:symbol', predictionLimiter, asyncHandler(async (req, res) => {
  const { symbol } = req.params;
  const options = req.body || {};

  if (!symbol || symbol.length === 0) {
    throw errors.badRequest('Symbol is required');
  }

  logger.info('Triggering prediction', { symbol, options });

  const prediction = await claudeEngineClient.triggerPrediction(symbol.toUpperCase(), options);

  // Broadcast prediction via WebSocket
  websocketServer.broadcastPrediction(prediction);

  res.json(successResponse(prediction, `Prediction generated for ${symbol}`));
}));

/**
 * GET /api/predictions - List all predictions (proxied to Claude Engine)
 */
router.get('/predictions', asyncHandler(async (req, res) => {
  const { limit, offset, symbol } = req.query;

  logger.info('Fetching predictions from Claude Engine', { limit, offset, symbol });

  const predictions = await claudeEngineClient.getPredictions({ limit, offset, symbol });

  res.json(successResponse(predictions, 'Predictions retrieved successfully'));
}));

/**
 * GET /api/predictions/latest - Get most recent prediction (must be before :id route)
 */
router.get('/predictions/latest', asyncHandler(async (req, res) => {
  const { symbol } = req.query;

  logger.info('Fetching latest prediction from Claude Engine', { symbol });

  // Get most recent prediction by fetching list with limit=1
  const predictions = await claudeEngineClient.getPredictions({
    limit: 1,
    ...(symbol && { symbol: symbol.toUpperCase() })
  });

  if (!predictions || !predictions.predictions || predictions.predictions.length === 0) {
    throw errors.notFound('No predictions found');
  }

  res.json(successResponse(predictions.predictions[0], 'Latest prediction retrieved successfully'));
}));

/**
 * GET /api/predictions/:id - Get single prediction by ID (proxied to Claude Engine)
 */
router.get('/predictions/:id', asyncHandler(async (req, res) => {
  const { id } = req.params;

  if (!id) {
    throw errors.badRequest('Prediction ID is required');
  }

  logger.info('Fetching prediction from Claude Engine', { id });

  const prediction = await claudeEngineClient.getPrediction(id);

  res.json(successResponse(prediction, 'Prediction retrieved successfully'));
}));

/**
 * GET /api/analytics/accuracy - Get prediction accuracy metrics (proxied to Claude Engine)
 */
router.get('/analytics/accuracy', asyncHandler(async (req, res) => {
  const { symbol, time_horizon_hours } = req.query;

  logger.info('Fetching accuracy analytics from Claude Engine', { symbol, time_horizon_hours });

  const metrics = await claudeEngineClient.getAccuracyAnalytics({ symbol, time_horizon_hours });

  res.json(successResponse(metrics, 'Accuracy metrics retrieved successfully'));
}));

/**
 * GET /api/analytics/costs - Get cost tracking metrics (proxied to Claude Engine)
 */
router.get('/analytics/costs', asyncHandler(async (req, res) => {
  const { days = 7 } = req.query;

  logger.info('Fetching cost analytics from Claude Engine', { days });

  const costs = await claudeEngineClient.getCostAnalytics({ days });

  res.json(successResponse(costs, 'Cost analytics retrieved successfully'));
}));

/**
 * GET /api/analytics/distribution - Get prediction direction distribution
 */
router.get('/analytics/distribution', asyncHandler(async (req, res) => {
  logger.info('Fetching prediction distribution');

  const result = await trackDatabaseQuery('select', 'automated_predictions', async () => {
    return await dbPool.query(`
      SELECT
        prediction_type as name,
        COUNT(*) as value
      FROM trading_predictions.automated_predictions
      WHERE prediction_type IN ('up', 'down')
      GROUP BY prediction_type
      ORDER BY value DESC
    `);
  });

  const directions = result.rows.map(row => ({
    name: row.name === 'up' ? 'Up' : 'Down',
    value: parseInt(row.value)
  }));

  res.json(successResponse({ directions }, 'Distribution retrieved successfully'));
}));

/**
 * GET /api/analytics/daily-stats - Get daily prediction statistics
 */
router.get('/analytics/daily-stats', asyncHandler(async (req, res) => {
  const { days = 30 } = req.query;

  logger.info('Fetching daily statistics', { days });

  // Validate days parameter (prevent injection, ensure reasonable range)
  const daysInt = Math.min(Math.max(parseInt(days) || 30, 1), 365);

  const result = await trackDatabaseQuery('select', 'automated_predictions', async () => {
    return await dbPool.query(`
      SELECT
        DATE(created_at) as date,
        COUNT(*) as predictions,
        COUNT(was_correct) as evaluated,
        SUM(CASE WHEN was_correct = true THEN 1 ELSE 0 END) as correct,
        AVG(confidence) * 100 as avg_confidence,
        SUM(CASE WHEN prediction_type = 'up' THEN 1 ELSE 0 END) as up_count,
        SUM(CASE WHEN prediction_type = 'down' THEN 1 ELSE 0 END) as down_count,
        SUM(total_cost_usd) as cost
      FROM trading_predictions.automated_predictions
      WHERE created_at >= NOW() - make_interval(days => $1)
      GROUP BY DATE(created_at)
      ORDER BY date ASC
    `, [daysInt]);
  });

  const dailyStats = result.rows.map(row => {
    const evaluated = parseInt(row.evaluated || 0);
    const correct = parseInt(row.correct || 0);
    const accuracy = evaluated > 0 ? (correct / evaluated * 100) : null;
    return {
      date: row.date.toISOString().split('T')[0],
      predictions: parseInt(row.predictions),
      evaluated: evaluated,
      correct: correct,
      accuracy: accuracy !== null ? parseFloat(accuracy.toFixed(1)) : null,
      avg_confidence: parseFloat(row.avg_confidence || 0).toFixed(1),
      up_count: parseInt(row.up_count),
      down_count: parseInt(row.down_count),
      cost: parseFloat(row.cost || 0).toFixed(4)
    };
  });

  res.json(successResponse(dailyStats, 'Daily statistics retrieved successfully'));
}));

/**
 * GET /api/symbols - Get list of available symbols
 */
router.get('/symbols', asyncHandler(async (req, res) => {
  const result = await trackDatabaseQuery('select', 'automated_predictions', async () => {
    return await dbPool.query(`
      SELECT DISTINCT symbol, COUNT(*) as prediction_count
      FROM trading_predictions.automated_predictions
      GROUP BY symbol
      ORDER BY prediction_count DESC
    `);
  });

  res.json(successResponse(result.rows));
}));


/**
 * GET /api/websocket/stats - Get WebSocket connection statistics
 */
router.get('/websocket/stats', asyncHandler(async (req, res) => {
  const wsStats = websocketServer.getStats();
  const connStats = connectionManager.getStats();
  const marketStats = marketDataFetcher.getStats();

  const stats = {
    websocket: wsStats,
    connections: connStats,
    marketData: marketStats,
    timestamp: new Date().toISOString()
  };

  res.json(successResponse(stats, 'WebSocket statistics retrieved'));
}));

/**
 * GET /api/websocket/connections - Get active connections details
 */
router.get('/websocket/connections', asyncHandler(async (req, res) => {
  const connections = connectionManager.getAllConnections();

  const formattedConnections = connections.map(conn => ({
    socketId: conn.socketId,
    connectedAt: new Date(conn.connectedAt).toISOString(),
    lastActivity: new Date(conn.lastActivity).toISOString(),
    sessionDuration: `${((Date.now() - conn.connectedAt) / 1000).toFixed(2)}s`,
    subscriptions: Array.from(conn.subscriptions),
    messageCount: conn.messageCount,
    bytesSent: conn.bytesSent,
    bytesReceived: conn.bytesReceived,
    metadata: conn.metadata
  }));

  res.json(successResponse({
    count: formattedConnections.length,
    connections: formattedConnections
  }, 'Active connections retrieved'));
}));

/**
 * ============================================
 * CONSOLE LOOPBACK ROUTES
 * Browser developer console WebSocket access
 * ============================================
 */

/**
 * GET /api/console/token - Generate console access token
 * Protected by Authelia at proxy layer
 */
router.get('/console/token', asyncHandler(async (req, res) => {
  logger.info('Console token requested', {
    ip: req.ip,
    userAgent: req.headers['user-agent']
  });

  try {
    const token = consoleNamespace.generateToken({
      ip: req.ip,
      userAgent: req.headers['user-agent'],
      timestamp: Date.now()
    });

    res.json(successResponse({
      token,
      expiresIn: 3600,
      usage: 'trader.connect(token)',
      endpoint: 'wss://trade.herakles.dev/console'
    }, 'Console token generated'));

  } catch (error) {
    logger.error('Console token generation failed', { error: error.message });
    throw errors.internal('Failed to generate console token');
  }
}));

/**
 * GET /api/console/stats - Get console namespace statistics
 */
router.get('/console/stats', asyncHandler(async (req, res) => {
  const stats = consoleNamespace.getStats();
  res.json(successResponse(stats, 'Console statistics retrieved'));
}));

/**
 * ============================================
 * AUTOMATED PREDICTIONS ROUTES
 * Proxy to Claude Engine automated endpoints
 * ============================================
 */

/**
 * GET /api/automated/cycle/current - Get current active prediction cycle
 */
router.get('/automated/cycle/current', asyncHandler(async (req, res) => {
  logger.info('Fetching current prediction cycle from Claude Engine');

  const cycle = await claudeEngineClient.request('GET', '/api/v1/automated/cycle/current');

  res.json(successResponse(cycle, 'Current cycle retrieved successfully'));
}));

/**
 * GET /api/automated/decision/latest - Get latest 4-hour decision
 */
router.get('/automated/decision/latest', asyncHandler(async (req, res) => {
  logger.info('Fetching latest 4-hour decision from Claude Engine');

  const decision = await claudeEngineClient.request('GET', '/api/v1/automated/decision/latest');

  res.json(successResponse(decision, 'Latest decision retrieved successfully'));
}));

/**
 * GET /api/automated/predictions/history - Get prediction history
 */
router.get('/automated/predictions/history', asyncHandler(async (req, res) => {
  const { limit, offset, symbol } = req.query;

  logger.info('Fetching automated prediction history from Claude Engine', { limit, offset, symbol });

  const queryParams = new URLSearchParams();
  if (limit) queryParams.append('limit', limit);
  if (offset) queryParams.append('offset', offset);
  if (symbol) queryParams.append('symbol', symbol);

  const history = await claudeEngineClient.request('GET', `/api/v1/automated/predictions/history?${queryParams}`);

  res.json(successResponse(history, 'Prediction history retrieved successfully'));
}));

/**
 * GET /api/automated/predictions/:id/prompt - Get the exact prompts used for a prediction
 */
router.get('/automated/predictions/:id/prompt', asyncHandler(async (req, res) => {
  const { id } = req.params;

  logger.info('Fetching prediction prompt from Claude Engine', { predictionId: id });

  const promptData = await claudeEngineClient.request('GET', `/api/v1/automated/predictions/${id}/prompt`);

  res.json(successResponse(promptData, 'Prediction prompt retrieved successfully'));
}));

/**
 * GET /api/automated/status - Get scheduler status and metrics
 */
router.get('/automated/status', asyncHandler(async (req, res) => {
  logger.info('Fetching automated prediction status from Claude Engine');

  const status = await claudeEngineClient.request('GET', '/api/v1/automated/status');

  res.json(successResponse(status, 'Scheduler status retrieved successfully'));
}));

/**
 * POST /api/automated/predict/now - Trigger manual prediction
 */
router.post('/automated/predict/now', predictionLimiter, asyncHandler(async (req, res) => {
  logger.info('Triggering manual automated prediction');

  const result = await claudeEngineClient.request('POST', '/api/v1/automated/predict/now');

  // Broadcast new prediction via WebSocket
  websocketServer.broadcastAutomatedPrediction(result);

  res.json(successResponse(result, 'Manual prediction triggered successfully'));
}));

/**
 * ============================================
 * SIGNALS PERFORMANCE ROUTES
 * ============================================
 */

/**
 * GET /api/v1/signals/performance - Get signal-to-trade performance
 */
router.get('/v1/signals/performance', asyncHandler(async (req, res) => {
  const { symbol = 'BTC/USDT', days = 30 } = req.query;
  logger.info('Fetching signal performance', { symbol, days });

  const queryParams = new URLSearchParams();
  queryParams.append('symbol', symbol);
  queryParams.append('days', days);

  const data = await claudeEngineClient.request('GET', `/api/v1/signals/performance?${queryParams}`);
  res.json(successResponse(data, 'Signal performance retrieved'));
}));

/**
 * GET /api/v1/signals/performance/daily - Get daily signal performance
 */
router.get('/v1/signals/performance/daily', asyncHandler(async (req, res) => {
  const { symbol = 'BTC/USDT', days = 30 } = req.query;
  logger.info('Fetching daily signal performance', { symbol, days });

  const queryParams = new URLSearchParams();
  queryParams.append('symbol', symbol);
  queryParams.append('days', days);

  const data = await claudeEngineClient.request('GET', `/api/v1/signals/performance/daily?${queryParams}`);
  res.json(successResponse(data, 'Daily signal performance retrieved'));
}));

/**
 * ============================================
 * AUTOMATED ANALYTICS ROUTES
 * ============================================
 */

/**
 * GET /api/v1/automated/analytics/patterns - Get pattern performance analytics
 */
router.get('/v1/automated/analytics/patterns', asyncHandler(async (req, res) => {
  const { min_occurrences = 5 } = req.query;
  logger.info('Fetching pattern analytics', { min_occurrences });

  const data = await claudeEngineClient.request('GET', `/api/v1/automated/analytics/patterns?min_occurrences=${min_occurrences}`);
  res.json(successResponse(data, 'Pattern analytics retrieved'));
}));

/**
 * GET /api/v1/automated/analytics/conditions - Get conditions analytics
 */
router.get('/v1/automated/analytics/conditions', asyncHandler(async (req, res) => {
  const { days = 30 } = req.query;
  logger.info('Fetching conditions analytics', { days });

  const data = await claudeEngineClient.request('GET', `/api/v1/automated/analytics/conditions?days=${days}`);
  res.json(successResponse(data, 'Conditions analytics retrieved'));
}));

/**
 * GET /api/v1/automated/analytics/calibration - Get calibration analytics
 */
router.get('/v1/automated/analytics/calibration', asyncHandler(async (req, res) => {
  const { days = 30 } = req.query;
  logger.info('Fetching calibration analytics', { days });

  const data = await claudeEngineClient.request('GET', `/api/v1/automated/analytics/calibration?days=${days}`);
  res.json(successResponse(data, 'Calibration analytics retrieved'));
}));

/**
 * ============================================
 * TRADES ROUTES - Paper Trading Performance
 * ============================================
 */

/**
 * GET /api/trades/statistics - Get trade statistics (P&L, win rate)
 */
router.get('/trades/statistics', asyncHandler(async (req, res) => {
  const { symbol, days = 30 } = req.query;
  logger.info('Fetching trade statistics', { symbol, days });

  const queryParams = new URLSearchParams();
  queryParams.append('days', days);
  if (symbol) queryParams.append('symbol', symbol);

  const stats = await claudeEngineClient.request('GET', `/api/v1/trades/statistics?${queryParams}`);
  res.json(successResponse(stats, 'Trade statistics retrieved'));
}));

/**
 * GET /api/trades/recent - Get recent trades
 */
router.get('/trades/recent', asyncHandler(async (req, res) => {
  const { symbol, limit = 20, status } = req.query;
  logger.info('Fetching recent trades', { symbol, limit, status });

  const queryParams = new URLSearchParams();
  queryParams.append('limit', limit);
  if (symbol) queryParams.append('symbol', symbol);
  if (status) queryParams.append('status', status);

  const trades = await claudeEngineClient.request('GET', `/api/v1/trades/recent?${queryParams}`);
  res.json(successResponse(trades, 'Recent trades retrieved'));
}));

/**
 * POST /api/trades/risk/ruin-calculator - Calculate Risk of Ruin via Monte Carlo
 */
router.post('/trades/risk/ruin-calculator', asyncHandler(async (req, res) => {
  logger.info('Calculating risk of ruin', { body: req.body });
  const result = await claudeEngineClient.request('POST', '/api/v1/trades/risk/ruin-calculator', req.body);
  res.json(successResponse(result, 'Risk of ruin calculated'));
}));

/**
 * GET /api/trades/risk/ruin - Get Risk of Ruin from trading history
 */
router.get('/trades/risk/ruin', asyncHandler(async (req, res) => {
  const { days = 30, risk_per_trade_pct = 2.0 } = req.query;
  logger.info('Fetching risk of ruin from history', { days, risk_per_trade_pct });
  const queryParams = new URLSearchParams({ days, risk_per_trade_pct });
  const result = await claudeEngineClient.request('GET', `/api/v1/trades/risk/ruin?${queryParams}`);
  res.json(successResponse(result, 'Risk of ruin from history retrieved'));
}));

/**
 * GET /api/trades/risk/concentration - Get portfolio concentration risk
 */
router.get('/trades/risk/concentration', asyncHandler(async (req, res) => {
  logger.info('Fetching concentration risk');
  const result = await claudeEngineClient.request('GET', '/api/v1/trades/risk/concentration');
  res.json(successResponse(result, 'Concentration risk retrieved'));
}));

/**
 * ============================================
 * SIGNALS ROUTES - OctoBot Integration
 * ============================================
 */

/**
 * GET /api/signals/health - Get signal service health
 */
router.get('/signals/health', asyncHandler(async (req, res) => {
  logger.info('Fetching signal health');
  const health = await claudeEngineClient.request('GET', '/api/v1/signals/health');
  res.json(successResponse(health, 'Signal health retrieved'));
}));

/**
 * GET /api/signals/latest - Get latest trading signal
 */
router.get('/signals/latest', asyncHandler(async (req, res) => {
  const { symbol = 'BTC/USDT' } = req.query;
  logger.info('Fetching latest signal', { symbol });
  const signal = await claudeEngineClient.request('GET', `/api/v1/signals/latest?symbol=${encodeURIComponent(symbol)}`);
  res.json(successResponse(signal, 'Latest signal retrieved'));
}));

/**
 * ============================================
 * OCTOBOT INTEGRATION ROUTES
 * Paper Trading via OctoBot
 * ============================================
 */

/**
 * GET /api/v1/signals/octobot/health - Get OctoBot container health
 */
router.get('/v1/signals/octobot/health', asyncHandler(async (req, res) => {
  logger.info('Fetching OctoBot health');
  const health = await claudeEngineClient.request('GET', '/api/v1/signals/octobot/health');
  res.json(successResponse(health, 'OctoBot health retrieved'));
}));

/**
 * GET /api/v1/signals/octobot/portfolio - Get paper trading portfolio
 */
router.get('/v1/signals/octobot/portfolio', asyncHandler(async (req, res) => {
  logger.info('Fetching OctoBot portfolio');
  const portfolio = await claudeEngineClient.request('GET', '/api/v1/signals/octobot/portfolio');
  res.json(successResponse(portfolio, 'OctoBot portfolio retrieved'));
}));

/**
 * GET /api/v1/signals/octobot/orders - Get open orders
 */
router.get('/v1/signals/octobot/orders', asyncHandler(async (req, res) => {
  logger.info('Fetching OctoBot open orders');
  const orders = await claudeEngineClient.request('GET', '/api/v1/signals/octobot/orders');
  res.json(successResponse(orders, 'OctoBot orders retrieved'));
}));

/**
 * GET /api/v1/signals/octobot/orders/closed - Get closed orders
 */
router.get('/v1/signals/octobot/orders/closed', asyncHandler(async (req, res) => {
  const { limit = 50 } = req.query;
  logger.info('Fetching OctoBot closed orders', { limit });
  const orders = await claudeEngineClient.request('GET', `/api/v1/signals/octobot/orders/closed?limit=${limit}`);
  res.json(successResponse(orders, 'OctoBot closed orders retrieved'));
}));

/**
 * POST /api/v1/signals/octobot/sync - Trigger manual sync from OctoBot
 */
router.post('/v1/signals/octobot/sync', asyncHandler(async (req, res) => {
  logger.info('Triggering OctoBot sync');
  const result = await claudeEngineClient.request('POST', '/api/v1/signals/octobot/sync');
  res.json(successResponse(result, 'OctoBot sync triggered'));
}));

/**
 * GET /api/v1/signals/octobot/sync/status - Get sync status
 */
router.get('/v1/signals/octobot/sync/status', asyncHandler(async (req, res) => {
  logger.info('Fetching OctoBot sync status');
  const status = await claudeEngineClient.request('GET', '/api/v1/signals/octobot/sync/status');
  res.json(successResponse(status, 'OctoBot sync status retrieved'));
}));

/**
 * ============================================
 * BACKTEST ROUTES
 * Historical Strategy Analysis
 * ============================================
 */

/**
 * GET /api/v1/backtest/summary - Get backtest summary
 */
router.get('/v1/backtest/summary', asyncHandler(async (req, res) => {
  const { days = 30 } = req.query;
  logger.info('Fetching backtest summary', { days });
  const summary = await claudeEngineClient.request('GET', `/api/v1/backtest/summary?days=${days}`);
  res.json(successResponse(summary, 'Backtest summary retrieved'));
}));

/**
 * GET /api/v1/backtest/accuracy - Get prediction accuracy by symbol
 */
router.get('/v1/backtest/accuracy', asyncHandler(async (req, res) => {
  const { days = 30 } = req.query;
  logger.info('Fetching backtest accuracy', { days });
  const accuracy = await claudeEngineClient.request('GET', `/api/v1/backtest/accuracy?days=${days}`);
  res.json(successResponse(accuracy, 'Backtest accuracy retrieved'));
}));

/**
 * GET /api/v1/backtest/calibration - Get confidence calibration data
 */
router.get('/v1/backtest/calibration', asyncHandler(async (req, res) => {
  const { days = 30 } = req.query;
  logger.info('Fetching backtest calibration', { days });
  const calibration = await claudeEngineClient.request('GET', `/api/v1/backtest/calibration?days=${days}`);
  res.json(successResponse(calibration, 'Backtest calibration retrieved'));
}));

/**
 * ============================================
 * AI PROVIDER ROUTES
 * ============================================
 */

/**
 * GET /api/v1/ai-providers - Get available AI providers
 */
router.get('/v1/ai-providers', asyncHandler(async (req, res) => {
  logger.info('Fetching AI providers');
  const providers = await claudeEngineClient.request('GET', '/api/v1/ai-providers');
  res.json(providers);
}));

/**
 * POST /api/v1/ai-providers/:provider - Set AI provider
 */
router.post('/v1/ai-providers/:provider', asyncHandler(async (req, res) => {
  const { provider } = req.params;
  logger.info('Setting AI provider', { provider });
  const result = await claudeEngineClient.request('POST', `/api/v1/ai-providers/${provider}`);
  res.json(result);
}));

/**
 * GET /api/v1/ai-providers/:provider/health - Check AI provider health
 */
router.get('/v1/ai-providers/:provider/health', asyncHandler(async (req, res) => {
  const { provider } = req.params;
  logger.info('Checking AI provider health', { provider });
  const health = await claudeEngineClient.request('GET', `/api/v1/ai-providers/${provider}/health`);
  res.json(health);
}));

/**
 * ============================================
 * SENTIMENT ROUTES - Market Sentiment Data
 * ============================================
 */

/**
 * GET /api/sentiment/fear-greed - Get Fear & Greed Index
 */
router.get('/sentiment/fear-greed', asyncHandler(async (req, res) => {
  logger.info('Fetching Fear & Greed Index');
  const data = await claudeEngineClient.request('GET', '/api/v1/sentiment/fear-greed');
  res.json(successResponse(data, 'Fear & Greed Index retrieved'));
}));

/**
 * GET /api/sentiment/market - Get overall market sentiment
 */
router.get('/sentiment/market', asyncHandler(async (req, res) => {
  logger.info('Fetching market sentiment');
  const data = await claudeEngineClient.request('GET', '/api/v1/sentiment/market');
  res.json(successResponse(data, 'Market sentiment retrieved'));
}));

module.exports = router;
