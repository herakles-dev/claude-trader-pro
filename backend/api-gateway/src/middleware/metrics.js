/**
 * Prometheus Metrics for Claude Trader API Gateway (Express.js)
 * 
 * This module provides Prometheus metrics collection for the Express.js API Gateway.
 */

const promClient = require('prom-client');

// Create a Registry
const register = new promClient.Registry();

// Add default metrics (CPU, memory, etc.)
promClient.collectDefaultMetrics({ register });

// HTTP Request Metrics
const httpRequestsTotal = new promClient.Counter({
  name: 'http_requests_total',
  help: 'Total number of HTTP requests',
  labelNames: ['method', 'route', 'status'],
  registers: [register]
});

const httpRequestDuration = new promClient.Histogram({
  name: 'http_request_duration_seconds',
  help: 'Duration of HTTP requests in seconds',
  labelNames: ['method', 'route', 'status'],
  buckets: [0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
  registers: [register]
});

// WebSocket Metrics
const wsConnectionsActive = new promClient.Gauge({
  name: 'websocket_connections_active',
  help: 'Number of active WebSocket connections',
  registers: [register]
});

const wsMessagesTotal = new promClient.Counter({
  name: 'websocket_messages_total',
  help: 'Total WebSocket messages',
  labelNames: ['direction', 'type'], // direction: inbound/outbound, type: event type
  registers: [register]
});

// Backend Service Metrics (calls to claude-engine)
const backendRequestsTotal = new promClient.Counter({
  name: 'backend_requests_total',
  help: 'Total requests to backend services',
  labelNames: ['service', 'endpoint', 'status'],
  registers: [register]
});

const backendRequestDuration = new promClient.Histogram({
  name: 'backend_request_duration_seconds',
  help: 'Duration of backend service requests',
  labelNames: ['service', 'endpoint'],
  buckets: [0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
  registers: [register]
});

// Database Query Metrics
const dbQueryDuration = new promClient.Histogram({
  name: 'db_query_duration_seconds',
  help: 'Database query duration',
  labelNames: ['operation', 'table'],
  buckets: [0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0],
  registers: [register]
});

const dbConnectionsActive = new promClient.Gauge({
  name: 'db_connections_active',
  help: 'Number of active database connections',
  registers: [register]
});

// Rate Limiting Metrics
const rateLimitHits = new promClient.Counter({
  name: 'rate_limit_hits_total',
  help: 'Total number of rate limit hits',
  labelNames: ['endpoint'],
  registers: [register]
});

// Cache Metrics
const cacheHits = new promClient.Counter({
  name: 'cache_hits_total',
  help: 'Total cache hits',
  labelNames: ['cache_type'],
  registers: [register]
});

const cacheMisses = new promClient.Counter({
  name: 'cache_misses_total',
  help: 'Total cache misses',
  labelNames: ['cache_type'],
  registers: [register]
});

/**
 * Express middleware to collect HTTP metrics
 */
function metricsMiddleware(req, res, next) {
  const start = Date.now();
  
  // Track response to record metrics
  res.on('finish', () => {
    const duration = (Date.now() - start) / 1000;
    const route = req.route ? req.route.path : req.path;
    
    httpRequestsTotal.labels(req.method, route, res.statusCode).inc();
    httpRequestDuration.labels(req.method, route, res.statusCode).observe(duration);
  });
  
  next();
}

/**
 * Metrics endpoint handler
 */
async function metricsEndpoint(req, res) {
  res.set('Content-Type', register.contentType);
  const metrics = await register.metrics();
  res.end(metrics);
}

/**
 * Track WebSocket connection
 */
function trackWebSocketConnection(connected) {
  if (connected) {
    wsConnectionsActive.inc();
  } else {
    wsConnectionsActive.dec();
  }
}

/**
 * Track WebSocket message
 */
function trackWebSocketMessage(direction, type) {
  wsMessagesTotal.labels(direction, type).inc();
}

/**
 * Track backend service call
 */
async function trackBackendCall(service, endpoint, callback) {
  const start = Date.now();
  let status = 'success';
  
  try {
    const result = await callback();
    return result;
  } catch (error) {
    status = 'error';
    throw error;
  } finally {
    const duration = (Date.now() - start) / 1000;
    
    backendRequestsTotal.labels(service, endpoint, status).inc();
    backendRequestDuration.labels(service, endpoint).observe(duration);
  }
}

/**
 * Track database query
 */
async function trackDatabaseQuery(operation, table, callback) {
  const start = Date.now();
  
  try {
    const result = await callback();
    return result;
  } finally {
    const duration = (Date.now() - start) / 1000;
    dbQueryDuration.labels(operation, table).observe(duration);
  }
}

/**
 * Record rate limit hit
 */
function recordRateLimitHit(endpoint) {
  rateLimitHits.labels(endpoint).inc();
}

/**
 * Record cache access
 */
function recordCacheAccess(cacheType, hit) {
  if (hit) {
    cacheHits.labels(cacheType).inc();
  } else {
    cacheMisses.labels(cacheType).inc();
  }
}

/**
 * Update database connection count
 */
function updateDbConnections(count) {
  dbConnectionsActive.set(count);
}

module.exports = {
  register,
  metricsMiddleware,
  metricsEndpoint,
  trackWebSocketConnection,
  trackWebSocketMessage,
  trackBackendCall,
  trackDatabaseQuery,
  recordRateLimitHit,
  recordCacheAccess,
  updateDbConnections,
  // Export individual metrics for custom tracking
  httpRequestsTotal,
  httpRequestDuration,
  wsConnectionsActive,
  wsMessagesTotal,
  backendRequestsTotal,
  backendRequestDuration
};
