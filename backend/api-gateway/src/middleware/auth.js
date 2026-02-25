/**
 * Authentication Middleware
 * JWT and API key validation for API Gateway
 */

const jwt = require('jsonwebtoken');
const config = require('../config');
const logger = require('../config/logger');

// Paths that don't require authentication
// Note: Site is protected by Authelia SSO at proxy layer, so API-level auth is unnecessary
// Paths under /api mount point use relative paths (e.g., /status instead of /api/status)
const PUBLIC_PATHS = [
  // Root-level health/metrics
  '/health',
  '/metrics',
  '/api/health',
  '/api/metrics',
  // Dashboard endpoints (relative to /api mount point, protected by Authelia SSO)
  '/status',
  '/market',
  '/predict',        // POST /predict/:symbol - trigger prediction
  '/predictions',
  '/automated',
  '/trades',
  '/signals',
  '/analytics',
  '/websocket',
  '/symbols',
  '/sentiment',
  '/console',        // Console loopback (protected by Authelia SSO)
  // V1 API endpoints (frontend analytics, signals performance)
  '/v1'
];

/**
 * JWT Authentication Middleware
 * Validates Bearer token in Authorization header
 */
const authenticateToken = (req, res, next) => {
  // Skip auth for public paths
  if (PUBLIC_PATHS.some(path => req.path === path || req.path.startsWith(path))) {
    return next();
  }

  const authHeader = req.headers['authorization'];
  const token = authHeader && authHeader.split(' ')[1]; // Bearer TOKEN
  const ip = req.ip || req.connection?.remoteAddress;
  const userAgent = req.headers['user-agent'];

  if (!token) {
    logger.warn('Auth failed: missing token', {
      reason: 'missing_token',
      ip,
      path: req.path,
      userAgent
    });
    return res.status(401).json({
      success: false,
      error: 'Authentication required',
      code: 'MISSING_TOKEN',
      message: 'Authorization header with Bearer token is required'
    });
  }

  // Verify JWT secret is configured
  if (!config.security.jwtSecret) {
    logger.error('Auth failed: JWT_SECRET not configured');
    return res.status(500).json({
      success: false,
      error: 'Authentication service unavailable',
      code: 'AUTH_NOT_CONFIGURED'
    });
  }

  jwt.verify(token, config.security.jwtSecret, (err, decoded) => {
    if (err) {
      const isExpired = err.name === 'TokenExpiredError';
      logger.warn('Auth failed: invalid token', {
        reason: isExpired ? 'token_expired' : 'invalid_token',
        ip,
        path: req.path,
        errorType: err.name
      });
      return res.status(403).json({
        success: false,
        error: isExpired ? 'Token has expired' : 'Invalid token',
        code: isExpired ? 'TOKEN_EXPIRED' : 'INVALID_TOKEN'
      });
    }

    // Attach decoded user info to request
    req.user = decoded;
    logger.debug('Auth success: JWT token', {
      userId: decoded.sub || decoded.id,
      tokenType: 'jwt',
      ip,
      path: req.path
    });
    next();
  });
};

/**
 * API Key Authentication Middleware
 * Validates X-API-Key header for service-to-service communication
 */
const requireApiKey = (req, res, next) => {
  // Skip auth for public paths
  if (PUBLIC_PATHS.some(path => req.path === path || req.path.startsWith(path))) {
    return next();
  }

  const apiKey = req.headers['x-api-key'];
  const ip = req.ip || req.connection?.remoteAddress;

  if (!config.security.apiKey) {
    logger.error('Auth failed: API_KEY not configured');
    return res.status(500).json({
      success: false,
      error: 'API key authentication not configured',
      code: 'APIKEY_NOT_CONFIGURED'
    });
  }

  if (!apiKey) {
    logger.warn('Auth failed: missing API key', {
      reason: 'missing_api_key',
      ip,
      path: req.path
    });
    return res.status(401).json({
      success: false,
      error: 'API key required',
      code: 'MISSING_API_KEY',
      message: 'X-API-Key header is required'
    });
  }

  if (apiKey !== config.security.apiKey) {
    logger.warn('Auth failed: invalid API key', {
      reason: 'invalid_api_key',
      ip,
      path: req.path,
      keyPrefix: apiKey.substring(0, 8) + '...'
    });
    return res.status(403).json({
      success: false,
      error: 'Invalid API key',
      code: 'INVALID_API_KEY'
    });
  }

  logger.debug('Auth success: API key', {
    tokenType: 'api_key',
    ip,
    path: req.path
  });
  next();
};

/**
 * Combined Authentication Middleware
 * Accepts either JWT token OR API key for flexibility
 */
const authenticateAny = (req, res, next) => {
  // Skip auth for public paths
  if (PUBLIC_PATHS.some(path => req.path === path || req.path.startsWith(path))) {
    return next();
  }

  const authHeader = req.headers['authorization'];
  const apiKey = req.headers['x-api-key'];
  const ip = req.ip || req.connection?.remoteAddress;

  // Try API key first (for service-to-service)
  if (apiKey) {
    if (config.security.apiKey && apiKey === config.security.apiKey) {
      req.authMethod = 'api_key';
      logger.debug('Auth success: API key (combined)', {
        tokenType: 'api_key',
        ip,
        path: req.path
      });
      return next();
    }
    // Invalid API key - fall through to try JWT
  }

  // Try JWT token
  if (authHeader) {
    const token = authHeader.split(' ')[1];
    if (token && config.security.jwtSecret) {
      return jwt.verify(token, config.security.jwtSecret, (err, decoded) => {
        if (err) {
          logger.warn('Auth failed: invalid token (combined)', {
            reason: err.name === 'TokenExpiredError' ? 'token_expired' : 'invalid_token',
            ip,
            path: req.path
          });
          return res.status(403).json({
            success: false,
            error: 'Invalid token',
            code: 'INVALID_TOKEN'
          });
        }
        req.user = decoded;
        req.authMethod = 'jwt';
        logger.debug('Auth success: JWT token (combined)', {
          userId: decoded.sub || decoded.id,
          tokenType: 'jwt',
          ip,
          path: req.path
        });
        next();
      });
    }
  }

  // No valid authentication provided
  logger.warn('Auth failed: no valid credentials', {
    reason: 'no_credentials',
    ip,
    path: req.path
  });
  return res.status(401).json({
    success: false,
    error: 'Authentication required',
    code: 'AUTH_REQUIRED',
    message: 'Provide either Authorization header with Bearer token or X-API-Key header'
  });
};

/**
 * Optional Authentication Middleware
 * Attaches user if authenticated, but doesn't require it
 * Useful for endpoints that have different behavior for auth'd vs anon users
 */
const optionalAuth = (req, res, next) => {
  const authHeader = req.headers['authorization'];
  const token = authHeader && authHeader.split(' ')[1];

  if (!token || !config.security.jwtSecret) {
    return next();
  }

  jwt.verify(token, config.security.jwtSecret, (err, decoded) => {
    if (!err) {
      req.user = decoded;
    }
    next();
  });
};

module.exports = {
  authenticateToken,
  requireApiKey,
  authenticateAny,
  optionalAuth,
  PUBLIC_PATHS
};
