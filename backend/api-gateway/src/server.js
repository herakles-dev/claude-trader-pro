/**
 * ClaudeTrader Pro API Gateway
 * Express.js server with WebSocket support
 * Port: 8100
 */

const express = require('express');
const http = require('http');
const cors = require('cors');
const helmet = require('helmet');
const compression = require('compression');
const cookieParser = require('cookie-parser');
const morgan = require('morgan');

// Import config and logger
const config = require('./config');
const logger = require('./config/logger');

// Import middleware
const {
  metricsMiddleware,
  metricsEndpoint
} = require('./middleware/metrics');
const { globalLimiter } = require('./middleware/rateLimiter');
const {
  errorHandler,
  notFoundHandler
} = require('./middleware/errorHandler');
const { authenticateAny } = require('./middleware/auth');

// Import routes
const apiRoutes = require('./routes/api');

// Import services
const websocketServer = require('./services/websocketServer');

// Create Express app
const app = express();
const server = http.createServer(app);

// Trust proxy (for rate limiting behind reverse proxy)
app.set('trust proxy', 1);

// ============================================
// MIDDLEWARE SETUP (Order matters!)
// ============================================

// 1. Security headers
app.use(helmet({
  contentSecurityPolicy: false, // Allow for development
  crossOriginEmbedderPolicy: false
}));

// 2. CORS
app.use(cors(config.cors));

// 3. Request logging (Morgan with Winston)
app.use(morgan('combined', { stream: logger.stream }));

// 4. Body parsing
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true, limit: '10mb' }));
app.use(cookieParser());

// 5. Compression
app.use(compression());

// 6. Metrics middleware (early in stack for accurate timing)
app.use(metricsMiddleware);

// 7. Global rate limiting
app.use(globalLimiter);

// ============================================
// ROUTES
// ============================================

// Health check (no rate limiting)
app.get('/health', (req, res) => {
  res.json({
    status: 'healthy',
    service: 'claude-trader-api-gateway',
    version: config.app.version,
    timestamp: new Date().toISOString()
  });
});

// Metrics endpoint (Prometheus)
app.get('/metrics', metricsEndpoint);

// Root endpoint
app.get('/', (req, res) => {
  res.json({
    service: 'ClaudeTrader Pro API Gateway',
    version: config.app.version,
    status: 'operational',
    documentation: '/api/health',
    websocket: config.websocket.enabled,
    timestamp: new Date().toISOString()
  });
});

// API routes (protected by authentication)
app.use('/api', authenticateAny, apiRoutes);

// ============================================
// ERROR HANDLING
// ============================================

// 404 handler (must be after all routes)
app.use(notFoundHandler);

// Global error handler (must be last)
app.use(errorHandler);

// ============================================
// WEBSOCKET SETUP
// ============================================

if (config.websocket.enabled) {
  websocketServer.initialize(server);
  logger.info('WebSocket server enabled');
}

// ============================================
// SERVER STARTUP
// ============================================

function startServer() {
  const port = config.app.port;

  server.listen(port, () => {
    logger.info('Server started successfully', {
      service: config.app.name,
      version: config.app.version,
      port,
      environment: config.app.env,
      endpoints: {
        health: `http://localhost:${port}/health`,
        metrics: `http://localhost:${port}/metrics`,
        api: `http://localhost:${port}/api`
      },
      websocket: config.websocket.enabled,
      features: {
        cors: config.cors.origin,
        rateLimit: `${config.rateLimit.maxRequests} requests per ${config.rateLimit.windowMs}ms`,
        logging: config.logging.level
      }
    });

    // Log integrations
    logger.info('Service integrations', {
      claudeEngine: config.services.claudeEngine.url,
      database: `${config.database.host}:${config.database.port}/${config.database.name}`,
      redis: config.redis.enabled ? `${config.redis.host}:${config.redis.port}` : 'disabled',
      loki: config.logging.lokiUrl || 'not configured'
    });
  });

  server.on('error', (error) => {
    if (error.code === 'EADDRINUSE') {
      logger.error(`Port ${port} is already in use`);
    } else if (error.code === 'EACCES') {
      logger.error(`Port ${port} requires elevated privileges`);
    } else {
      logger.error('Server error', { error: error.message, stack: error.stack });
    }
    process.exit(1);
  });
}

// ============================================
// GRACEFUL SHUTDOWN
// ============================================

function gracefulShutdown(signal) {
  logger.info(`${signal} received, starting graceful shutdown`);

  // Stop accepting new connections
  server.close(() => {
    logger.info('HTTP server closed');

    // Shutdown WebSocket server
    if (config.websocket.enabled) {
      websocketServer.shutdown();
    }

    // Close database connections (if needed)
    // dbPool.end();

    logger.info('Graceful shutdown completed');
    process.exit(0);
  });

  // Force shutdown after 30 seconds
  setTimeout(() => {
    logger.error('Forced shutdown after timeout');
    process.exit(1);
  }, 30000);
}

// Handle shutdown signals
process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));
process.on('SIGINT', () => gracefulShutdown('SIGINT'));

// Handle uncaught errors
process.on('uncaughtException', (error) => {
  logger.error('Uncaught exception', {
    error: error.message,
    stack: error.stack
  });
  process.exit(1);
});

process.on('unhandledRejection', (reason, promise) => {
  logger.error('Unhandled rejection', {
    reason,
    promise
  });
  // Don't exit - log and continue
});

// ============================================
// START SERVER
// ============================================

startServer();

// Export for testing
module.exports = { app, server };
