/**
 * Rate Limiting Middleware
 * Protects API from abuse with configurable limits per endpoint
 */

const rateLimit = require('express-rate-limit');
const config = require('../config');
const logger = require('../config/logger');
const { recordRateLimitHit } = require('./metrics');

/**
 * Create rate limiter with custom handler
 */
function createRateLimiter(options = {}) {
  const defaults = {
    windowMs: config.rateLimit.windowMs,
    max: config.rateLimit.maxRequests,
    standardHeaders: true,
    legacyHeaders: false,
    handler: (req, res) => {
      const endpoint = req.path;
      
      // Record metrics
      recordRateLimitHit(endpoint);
      
      // Log rate limit event
      logger.warn('Rate limit exceeded', {
        ip: req.ip,
        endpoint,
        method: req.method,
        headers: req.headers['user-agent']
      });
      
      res.status(429).json({
        success: false,
        error: 'Too many requests, please try again later.',
        data: null,
        timestamp: new Date().toISOString(),
        retryAfter: Math.ceil(options.windowMs / 1000) || 60
      });
    },
    skip: (req) => {
      // Skip rate limiting for health checks
      return req.path === '/health' || req.path === '/metrics';
    }
  };

  return rateLimit({ ...defaults, ...options });
}

/**
 * Global rate limiter (applies to all routes)
 */
const globalLimiter = createRateLimiter({
  windowMs: 60 * 1000, // 1 minute
  max: 100, // 100 requests per minute
  message: 'Too many requests from this IP, please try again later.'
});

/**
 * Strict rate limiter for expensive operations
 */
const strictLimiter = createRateLimiter({
  windowMs: 60 * 1000, // 1 minute
  max: 10, // 10 requests per minute
  message: 'Rate limit exceeded for this operation.'
});

/**
 * Prediction endpoint limiter
 */
const predictionLimiter = createRateLimiter({
  windowMs: 60 * 1000, // 1 minute
  max: 20, // 20 predictions per minute
  message: 'Prediction rate limit exceeded. Please wait before requesting more predictions.'
});

/**
 * Market data limiter
 */
const marketDataLimiter = createRateLimiter({
  windowMs: 10 * 1000, // 10 seconds
  max: 30, // 30 requests per 10 seconds
  message: 'Market data rate limit exceeded.'
});

/**
 * Auth endpoint limiter (prevent brute force)
 */
const authLimiter = createRateLimiter({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 5, // 5 attempts per 15 minutes
  skipSuccessfulRequests: true,
  message: 'Too many authentication attempts. Please try again later.'
});

module.exports = {
  globalLimiter,
  strictLimiter,
  predictionLimiter,
  marketDataLimiter,
  authLimiter,
  createRateLimiter
};
