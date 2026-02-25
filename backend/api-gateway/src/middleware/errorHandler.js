/**
 * Centralized Error Handling Middleware
 * Provides consistent error responses and logging
 */

const logger = require('../config/logger');
const config = require('../config');

/**
 * Custom API Error class
 */
class ApiError extends Error {
  constructor(statusCode, message, isOperational = true, details = null) {
    super(message);
    this.statusCode = statusCode;
    this.isOperational = isOperational;
    this.details = details;
    Error.captureStackTrace(this, this.constructor);
  }
}

/**
 * Standard error response format
 */
function formatErrorResponse(err, req) {
  const statusCode = err.statusCode || 500;
  const isDevelopment = config.app.env === 'development';

  return {
    success: false,
    error: err.message || 'Internal server error',
    data: null,
    timestamp: new Date().toISOString(),
    path: req.path,
    method: req.method,
    ...(err.details && { details: err.details }),
    ...(isDevelopment && err.stack && { stack: err.stack })
  };
}

/**
 * Log error with appropriate level
 */
function logError(err, req) {
  const errorInfo = {
    message: err.message,
    statusCode: err.statusCode,
    path: req.path,
    method: req.method,
    ip: req.ip,
    userAgent: req.headers['user-agent'],
    ...(err.details && { details: err.details })
  };

  if (err.statusCode >= 500) {
    logger.error('Server error', {
      ...errorInfo,
      stack: err.stack
    });
  } else if (err.statusCode >= 400) {
    logger.warn('Client error', errorInfo);
  } else {
    logger.info('Error handled', errorInfo);
  }
}

/**
 * Main error handler middleware
 */
function errorHandler(err, req, res, next) {
  // Log the error
  logError(err, req);

  // Send error response
  const response = formatErrorResponse(err, req);
  res.status(err.statusCode || 500).json(response);
}

/**
 * 404 Not Found handler
 */
function notFoundHandler(req, res, next) {
  const error = new ApiError(
    404,
    `Route ${req.method} ${req.path} not found`,
    true,
    {
      availableRoutes: [
        'GET /health',
        'GET /metrics',
        'GET /api/market/:symbol',
        'POST /api/predict/:symbol',
        'GET /api/predictions',
        'GET /api/predictions/:id',
        'GET /api/analytics/accuracy',
        'GET /api/analytics/costs'
      ]
    }
  );
  next(error);
}

/**
 * Async error wrapper
 * Catches async errors and passes them to error handler
 */
function asyncHandler(fn) {
  return (req, res, next) => {
    Promise.resolve(fn(req, res, next)).catch(next);
  };
}

/**
 * Validation error handler
 */
function validationErrorHandler(errors) {
  return new ApiError(
    400,
    'Validation failed',
    true,
    {
      fields: errors.array ? errors.array() : errors
    }
  );
}

/**
 * Create error by status code
 */
function createError(statusCode, message, details = null) {
  return new ApiError(statusCode, message, true, details);
}

/**
 * Common error creators
 */
const errors = {
  badRequest: (message = 'Bad request', details = null) => 
    createError(400, message, details),
  
  unauthorized: (message = 'Unauthorized', details = null) => 
    createError(401, message, details),
  
  forbidden: (message = 'Forbidden', details = null) => 
    createError(403, message, details),
  
  notFound: (resource = 'Resource', details = null) => 
    createError(404, `${resource} not found`, details),
  
  conflict: (message = 'Conflict', details = null) => 
    createError(409, message, details),
  
  tooManyRequests: (message = 'Too many requests', details = null) => 
    createError(429, message, details),
  
  internal: (message = 'Internal server error', details = null) => 
    createError(500, message, details),
  
  badGateway: (service = 'Backend service', details = null) => 
    createError(502, `${service} unavailable`, details),
  
  serviceUnavailable: (message = 'Service temporarily unavailable', details = null) => 
    createError(503, message, details),
  
  gatewayTimeout: (service = 'Backend service', details = null) => 
    createError(504, `${service} timeout`, details),
  
  notImplemented: (message = 'Not implemented', details = null) => 
    createError(501, message, details)
};

module.exports = {
  ApiError,
  errorHandler,
  notFoundHandler,
  asyncHandler,
  validationErrorHandler,
  createError,
  errors
};
