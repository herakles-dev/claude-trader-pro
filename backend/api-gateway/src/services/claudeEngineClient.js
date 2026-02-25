/**
 * Claude Engine HTTP Client
 * Handles communication with Claude Engine backend service
 * Features: retry logic, circuit breaker, timeout handling
 */

const axios = require('axios');
const config = require('../config');
const logger = require('../config/logger');
const { trackBackendCall } = require('../middleware/metrics');
const { errors } = require('../middleware/errorHandler');

class CircuitBreaker {
  constructor(threshold = 5, timeout = 60000) {
    this.failureCount = 0;
    this.failureThreshold = threshold;
    this.timeout = timeout;
    this.state = 'CLOSED'; // CLOSED, OPEN, HALF_OPEN
    this.nextAttempt = Date.now();
  }

  recordSuccess() {
    this.failureCount = 0;
    this.state = 'CLOSED';
  }

  recordFailure() {
    this.failureCount += 1;
    
    if (this.failureCount >= this.failureThreshold) {
      this.state = 'OPEN';
      this.nextAttempt = Date.now() + this.timeout;
      logger.error('Circuit breaker opened', {
        failureCount: this.failureCount,
        nextAttempt: new Date(this.nextAttempt).toISOString()
      });
    }
  }

  canAttempt() {
    if (this.state === 'CLOSED') {
      return true;
    }

    if (this.state === 'OPEN' && Date.now() > this.nextAttempt) {
      this.state = 'HALF_OPEN';
      logger.info('Circuit breaker entering half-open state');
      return true;
    }

    return false;
  }

  getState() {
    return {
      state: this.state,
      failureCount: this.failureCount,
      nextAttempt: this.state === 'OPEN' ? new Date(this.nextAttempt).toISOString() : null
    };
  }
}

class ClaudeEngineClient {
  constructor() {
    this.baseURL = config.services.claudeEngine.url;
    this.timeout = config.services.claudeEngine.timeout;
    this.maxRetries = config.services.claudeEngine.retries;
    this.circuitBreaker = new CircuitBreaker();

    // Get API key from config for service-to-service auth
    const apiKey = config.security?.apiKey;

    this.client = axios.create({
      baseURL: this.baseURL,
      timeout: this.timeout,
      headers: {
        'Content-Type': 'application/json',
        'User-Agent': 'ClaudeTrader-API-Gateway/1.0',
        ...(apiKey && { 'X-API-Key': apiKey })
      }
    });

    // Add request interceptor for logging
    this.client.interceptors.request.use(
      (request) => {
        logger.debug('Claude Engine request', {
          method: request.method,
          url: request.url,
          params: request.params
        });
        return request;
      },
      (error) => {
        logger.error('Request interceptor error', { error: error.message });
        return Promise.reject(error);
      }
    );

    // Add response interceptor
    this.client.interceptors.response.use(
      (response) => {
        this.circuitBreaker.recordSuccess();
        return response;
      },
      (error) => {
        this.circuitBreaker.recordFailure();
        return Promise.reject(error);
      }
    );
  }

  /**
   * Retry logic with exponential backoff
   */
  async retryRequest(requestFn, retries = this.maxRetries) {
    for (let attempt = 0; attempt <= retries; attempt++) {
      try {
        return await requestFn();
      } catch (error) {
        const isLastAttempt = attempt === retries;
        
        if (isLastAttempt) {
          throw error;
        }

        // Exponential backoff: 100ms, 200ms, 400ms
        const delay = Math.min(100 * Math.pow(2, attempt), 1000);
        
        logger.warn('Retrying request', {
          attempt: attempt + 1,
          maxRetries: retries,
          delay,
          error: error.message
        });

        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }
  }

  /**
   * Check if service is available
   */
  async healthCheck() {
    try {
      const response = await trackBackendCall(
        'claude-engine',
        '/api/v1/health',
        async () => {
          const res = await this.client.get('/api/v1/health', { timeout: 15000 });
          return res.data;
        }
      );
      return response;
    } catch (error) {
      logger.error('Claude Engine health check failed', { error: error.message });
      throw errors.badGateway('Claude Engine');
    }
  }

  /**
   * Get predictions list with optional filters
   */
  async getPredictions(params = {}) {
    if (!this.circuitBreaker.canAttempt()) {
      throw errors.serviceUnavailable('Claude Engine circuit breaker is open', 
        this.circuitBreaker.getState()
      );
    }

    try {
      const data = await this.retryRequest(async () => {
        return await trackBackendCall(
          'claude-engine',
          '/api/v1/predictions',
          async () => {
            const response = await this.client.get('/api/v1/predictions', { params });
            return response.data;
          }
        );
      });

      return data;
    } catch (error) {
      this.handleError(error, 'getPredictions', params);
    }
  }

  /**
   * Trigger prediction for symbol
   */
  async triggerPrediction(symbol, options = {}) {
    if (!this.circuitBreaker.canAttempt()) {
      throw errors.serviceUnavailable('Claude Engine circuit breaker is open',
        this.circuitBreaker.getState()
      );
    }

    try {
      const data = await this.retryRequest(async () => {
        return await trackBackendCall(
          'claude-engine',
          '/api/v1/predict',
          async () => {
            const response = await this.client.post('/api/v1/predict', { 
              symbol, 
              ...options 
            });
            return response.data;
          }
        );
      });

      return data;
    } catch (error) {
      this.handleError(error, 'triggerPrediction', symbol);
    }
  }

  /**
   * Get prediction by ID
   */
  async getPrediction(predictionId) {
    if (!this.circuitBreaker.canAttempt()) {
      throw errors.serviceUnavailable('Claude Engine circuit breaker is open',
        this.circuitBreaker.getState()
      );
    }

    try {
      const data = await this.retryRequest(async () => {
        return await trackBackendCall(
          'claude-engine',
          `/api/v1/predictions/${predictionId}`,
          async () => {
            const response = await this.client.get(`/api/v1/predictions/${predictionId}`);
            return response.data;
          }
        );
      });

      return data;
    } catch (error) {
      this.handleError(error, 'getPrediction', predictionId);
    }
  }

  /**
   * Get accuracy analytics from Claude Engine
   */
  async getAccuracyAnalytics(params = {}) {
    if (!this.circuitBreaker.canAttempt()) {
      throw errors.serviceUnavailable('Claude Engine circuit breaker is open',
        this.circuitBreaker.getState()
      );
    }

    try {
      const data = await this.retryRequest(async () => {
        return await trackBackendCall(
          'claude-engine',
          '/api/v1/accuracy',
          async () => {
            const response = await this.client.get('/api/v1/accuracy', { params });
            return response.data;
          }
        );
      });

      return data;
    } catch (error) {
      this.handleError(error, 'getAccuracyAnalytics', params);
    }
  }

  /**
   * Get cost analytics from Claude Engine
   */
  async getCostAnalytics(params = {}) {
    if (!this.circuitBreaker.canAttempt()) {
      throw errors.serviceUnavailable('Claude Engine circuit breaker is open',
        this.circuitBreaker.getState()
      );
    }

    try {
      const data = await this.retryRequest(async () => {
        return await trackBackendCall(
          'claude-engine',
          '/api/v1/costs',
          async () => {
            const response = await this.client.get('/api/v1/costs', { params });
            return response.data;
          }
        );
      });

      return data;
    } catch (error) {
      this.handleError(error, 'getCostAnalytics', params);
    }
  }

  /**
   * Handle errors and transform to appropriate API errors
   */
  handleError(error, operation, context) {
    logger.error(`Claude Engine ${operation} failed`, {
      context,
      error: error.message,
      circuitBreakerState: this.circuitBreaker.getState()
    });

    if (error.response) {
      // Backend returned an error response
      const status = error.response.status;
      const message = error.response.data?.message || error.message;

      if (status === 404) {
        throw errors.notFound('Resource', { context });
      } else if (status === 400) {
        throw errors.badRequest(message, error.response.data);
      } else if (status >= 500) {
        throw errors.badGateway('Claude Engine', { 
          status,
          message,
          operation,
          context 
        });
      }
    } else if (error.code === 'ECONNABORTED') {
      // Timeout
      throw errors.gatewayTimeout('Claude Engine', {
        timeout: this.timeout,
        operation,
        context
      });
    } else if (error.code === 'ECONNREFUSED') {
      // Connection refused
      throw errors.badGateway('Claude Engine', {
        message: 'Connection refused',
        operation,
        context
      });
    }

    // Generic server error
    throw errors.internal(`Claude Engine ${operation} failed`, {
      message: error.message,
      operation,
      context
    });
  }

  /**
   * Generic request method for proxying arbitrary endpoints
   */
  async request(method, path, data = null, params = null) {
    if (!this.circuitBreaker.canAttempt()) {
      throw errors.serviceUnavailable('Claude Engine circuit breaker is open',
        this.circuitBreaker.getState()
      );
    }

    try {
      const result = await this.retryRequest(async () => {
        return await trackBackendCall(
          'claude-engine',
          path,
          async () => {
            const config = { params };
            let response;

            switch (method.toUpperCase()) {
              case 'GET':
                response = await this.client.get(path, config);
                break;
              case 'POST':
                response = await this.client.post(path, data, config);
                break;
              case 'PUT':
                response = await this.client.put(path, data, config);
                break;
              case 'DELETE':
                response = await this.client.delete(path, config);
                break;
              default:
                throw new Error(`Unsupported HTTP method: ${method}`);
            }

            return response.data;
          }
        );
      });

      return result;
    } catch (error) {
      this.handleError(error, `${method} ${path}`, { data, params });
    }
  }

  /**
   * Get circuit breaker status
   */
  getStatus() {
    return {
      baseURL: this.baseURL,
      timeout: this.timeout,
      circuitBreaker: this.circuitBreaker.getState()
    };
  }
}

// Export singleton instance
module.exports = new ClaudeEngineClient();
