import axios from 'axios'
import {
  logApiRequest,
  logApiResponse,
  logApiError,
  addToSessionSummary,
} from '../utils/debugLogger'

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api'

// Create axios instance with default config
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000, // 2 minutes for prediction generation (external API calls take time)
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor with debug logging
api.interceptors.request.use(
  (config) => {
    // Add auth token if available
    const token = localStorage.getItem('auth_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }

    // Debug logging
    const endpoint = config.url
    logApiRequest(endpoint, config.params || config.data || {})
    addToSessionSummary('api', {
      timestamp: new Date().toISOString(),
      endpoint,
      method: config.method,
      params: config.params,
    })

    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor with debug logging
api.interceptors.response.use(
  (response) => {
    // Debug logging for successful responses
    const endpoint = response.config?.url || 'unknown'
    logApiResponse(endpoint, response.data, response)
    return response
  },
  (error) => {
    const endpoint = error.config?.url || 'unknown'

    if (error.response) {
      // Server responded with error status
      console.error('API Error:', error.response.data)
      logApiError(endpoint, error)
      addToSessionSummary('error', {
        timestamp: new Date().toISOString(),
        endpoint,
        status: error.response.status,
        message: error.response.data?.error || error.response.data?.message,
      })

      // Enhance error object with more details
      const apiError = new Error(
        error.response.data?.error ||
        error.response.data?.message ||
        `Request failed with status ${error.response.status}`
      )
      apiError.response = error.response
      apiError.status = error.response.status
      return Promise.reject(apiError)
    } else if (error.request) {
      // Request made but no response
      console.error('Network Error:', error.request)
      logApiError(endpoint, { message: 'Network error - no response', request: error.request })
      addToSessionSummary('error', {
        timestamp: new Date().toISOString(),
        endpoint,
        message: 'Network error - no response',
      })
      const networkError = new Error('Network error: No response from server')
      networkError.request = error.request
      return Promise.reject(networkError)
    } else {
      // Something else happened
      console.error('Error:', error.message)
      logApiError(endpoint, error)
      return Promise.reject(error)
    }
  }
)

// Market API - Uses cached market data from API Gateway
export const marketAPI = {
  // Get cached market data for all symbols
  getCached: () =>
    api.get('/market/cached'),

  // Get current market data for a symbol (from cache)
  getMarket: (symbol = 'BTC') =>
    api.get('/market/cached').then(response => {
      const cachedData = response.data?.data?.data || {}
      const symbolData = cachedData[symbol]
      if (symbolData) {
        return { data: symbolData }
      }
      return {
        data: {
          symbol,
          price: 0,
          change24h: 0,
          changePercent24h: 0,
          volume24h: 0,
          notAvailable: true
        }
      }
    }),

  // Get market data for multiple symbols (from cache)
  // Returns object keyed by symbol for easy lookup
  getMarkets: (symbols = ['BTC', 'ETH', 'SOL']) =>
    api.get('/market/cached').then(response => {
      const cachedData = response.data?.data?.data || {}
      const result = {}
      symbols.forEach(symbol => {
        const symbolData = cachedData[symbol]
        if (symbolData) {
          result[symbol] = symbolData
        } else {
          result[symbol] = {
            symbol,
            current_price: 0,
            price_change_24h: 0,
            price_change_percentage_24h: 0,
            total_volume: 0,
            notAvailable: true
          }
        }
      })
      return { data: result }
    }),

  // Get historical market data (not implemented - returns empty)
  getHistory: (symbol, interval = '1h', limit = 100) =>
    Promise.resolve({ data: [] }),
}

// Sentiment API - Real data from Alternative.me Fear & Greed Index
export const sentimentAPI = {
  // Get Fear & Greed Index
  getFearGreed: () =>
    api.get('/sentiment/fear-greed').then(response => {
      // Extract fear_greed from nested response
      const fgData = response.data?.data?.data?.fear_greed || response.data?.data?.fear_greed
      return {
        data: {
          value: fgData?.value || 50,
          classification: fgData?.classification || 'Neutral',
          timestamp: fgData?.timestamp,
          time_until_update: fgData?.time_until_update
        }
      }
    }).catch(error => {
      console.warn('Failed to fetch Fear & Greed:', error)
      return { data: { value: 50, classification: 'Neutral', notAvailable: true } }
    }),

  // Get market sentiment (includes trend + history)
  getMarket: () =>
    api.get('/sentiment/market').then(response => {
      const data = response.data?.data?.data || response.data?.data
      return { data }
    }).catch(error => {
      console.warn('Failed to fetch market sentiment:', error)
      return { data: { notAvailable: true } }
    }),

  // Get all sentiment data (for backwards compatibility)
  getAll: () =>
    api.get('/sentiment/market').then(response => {
      const data = response.data?.data?.data || response.data?.data
      const fgData = data?.fear_greed
      return {
        data: {
          fear_greed: {
            value: fgData?.value || 50,
            classification: fgData?.classification || 'Neutral',
            timestamp: fgData?.timestamp
          },
          trend: data?.trend,
          history: data?.history,
          source: data?.source
        }
      }
    }).catch(error => {
      console.warn('Failed to fetch sentiment:', error)
      return {
        data: {
          fear_greed: { value: 50, classification: 'Neutral' },
          notAvailable: true
        }
      }
    }),
}

// Prediction API
export const predictionAPI = {
  // Trigger new prediction
  triggerPrediction: (symbol, strategy = 'conservative') =>
    api.post(`/predict/${symbol}`, { strategy }),

  // Transform API prediction to frontend format
  _transformPrediction: (p) => ({
    id: p.prediction_id,
    symbol: p.symbol,
    direction: p.prediction_type,  // API uses prediction_type
    confidence: p.confidence,
    reasoning: p.reasoning,
    created_at: p.timestamp,  // API uses timestamp
    strategy: 'conservative',  // Default, not in API response
    cost_usd: p.cost_usd,
    was_correct: p.was_correct,
    actual_movement: p.actual_movement,
  }),

  // Get latest prediction - use automated predictions history
  getLatest: (symbol = 'BTC') => {
    // Convert short symbols to full format (BTC -> BTC/USDT)
    const fullSymbol = symbol.includes('/') ? symbol : `${symbol}/USDT`
    return api.get('/automated/predictions/history', {
      params: {
        limit: 1,
        symbol: fullSymbol,
      }
    }).then(response => {
      const predictions = response.data?.data?.predictions || []
      const transformed = predictions.map(predictionAPI._transformPrediction)
      return {
        ...response,
        data: transformed.length > 0 ? transformed[0] : null
      }
    })
  },

  // Get prediction history with pagination - use automated predictions
  getPredictions: (params = {}) => {
    const {
      page = 1,
      limit = 20,
      symbol = '',
      offset = 0,
    } = params

    // Convert short symbols to full format (BTC -> BTC/USDT)
    const fullSymbol = symbol ? (symbol.includes('/') ? symbol : `${symbol}/USDT`) : ''

    return api.get('/automated/predictions/history', {
      params: {
        limit,
        offset,
        ...(fullSymbol && { symbol: fullSymbol }),
      },
    }).then(response => {
      const data = response.data?.data || {}
      const predictions = (data.predictions || []).map(predictionAPI._transformPrediction)
      return {
        ...response,
        data: {
          ...response.data,
          data: {
            ...data,
            predictions,
            pagination: {
              total: data.total || 0,
              total_pages: Math.ceil((data.total || 0) / limit),
              page,
              limit,
            }
          }
        }
      }
    })
  },

  // Get prediction by ID
  getById: (id) =>
    api.get(`/predictions/${id}`),

  // Get prediction evaluation/outcome (not implemented yet)
  getEvaluation: (id) =>
    Promise.resolve({ data: null }),
}

// Analytics API
export const analyticsAPI = {
  // Get accuracy metrics
  getAccuracy: (timeRange = '30d') =>
    api.get('/analytics/accuracy', { params: { range: timeRange } }),

  // Get cost tracking (days parameter - number of days to look back)
  getCosts: (days = 7) =>
    api.get('/analytics/costs', { params: { days } }),

  // Get performance metrics
  getPerformance: (symbol = null) =>
    api.get('/analytics/performance', { params: { symbol } }),

  // Get prediction distribution
  getDistribution: () =>
    api.get('/analytics/distribution'),

  // Get daily statistics
  getDailyStats: (days = 30) =>
    api.get('/analytics/daily-stats', { params: { days } }),

  // Pattern performance analytics
  getPatterns: (minOccurrences = 5) =>
    api.get('/v1/automated/analytics/patterns', {
      params: { min_occurrences: minOccurrences }
    }),

  // Market conditions/regime analytics
  getConditions: (days = 30) =>
    api.get('/v1/automated/analytics/conditions', { params: { days } }),

  // Confidence calibration analytics
  getCalibration: (days = 30) =>
    api.get('/v1/automated/analytics/calibration', { params: { days } }),
}

// System API
export const systemAPI = {
  // Check system health
  getHealth: () =>
    api.get('/health'),

  // Get service status
  getStatus: () =>
    api.get('/status'),

  // Get system configuration
  getConfig: () =>
    api.get('/system/config'),

  // Update configuration
  updateConfig: (config) =>
    api.put('/system/config', config),

  // Get WebSocket stats
  getWebSocketStats: () =>
    api.get('/websocket/stats'),
}

// AI Provider API
export const aiProviderAPI = {
  // Get available AI providers and their status
  getProviders: () =>
    api.get('/v1/ai-providers'),

  // Set the current AI provider
  setProvider: (provider) =>
    api.post(`/v1/ai-providers/${provider}`),

  // Check health of specific provider
  checkHealth: (provider) =>
    api.get(`/v1/ai-providers/${provider}/health`),
}

// Automated Predictions API (4-hour cycle system)
export const automatedAPI = {
  // Get current active prediction cycle
  getCurrentCycle: () =>
    api.get('/automated/cycle/current'),

  // Get latest 4-hour decision
  getLatestDecision: () =>
    api.get('/automated/decision/latest'),

  // Get automated prediction history
  getPredictionHistory: (params = {}) => {
    const { limit = 20, offset = 0, symbol } = params
    return api.get('/automated/predictions/history', {
      params: { limit, offset, ...(symbol && { symbol }) }
    })
  },

  // Get scheduler status and metrics
  getStatus: () =>
    api.get('/automated/status'),

  // Trigger manual prediction
  triggerNow: () =>
    api.post('/automated/predict/now'),

  // Trigger manual evaluation
  triggerEvaluation: () =>
    api.post('/v1/automated/evaluate'),

  // Get the prompt used for a specific prediction
  getPredictionPrompt: (predictionId) =>
    api.get(`/automated/predictions/${predictionId}/prompt`),
}

// Costs API
export const costsAPI = {
  // Get cost summary
  getSummary: (days = 7) =>
    api.get('/analytics/costs', { params: { days } }),

  // Get daily cost breakdown
  getDaily: (days = 30) =>
    api.get('/analytics/costs', { params: { days } }),
}

// Trades API (Paper Trading Performance)
export const tradesAPI = {
  // Get trade statistics (P&L, win rate)
  getStatistics: (params = {}) => {
    const { symbol, days = 30 } = params
    return api.get('/trades/statistics', {
      params: { days, ...(symbol && { symbol }) }
    })
  },

  // Get recent trades with pagination
  getRecent: (params = {}) => {
    const { symbol, limit = 20, offset = 0, status } = params
    return api.get('/trades/recent', {
      params: { limit, offset, ...(symbol && { symbol }), ...(status && { status }) }
    })
  },

  // Get open positions only
  getOpenPositions: (params = {}) => {
    const { symbol } = params
    return api.get('/trades/recent', {
      params: { status: 'open', limit: 50, ...(symbol && { symbol }) }
    })
  },

  // Get full trade history with pagination
  getHistory: (params = {}) => {
    const { symbol, limit = 50, offset = 0, status, sortBy = 'executed_at', sortDir = 'desc' } = params
    return api.get('/trades/recent', {
      params: {
        limit,
        offset,
        ...(symbol && { symbol }),
        ...(status && { status }),
        sort_by: sortBy,
        sort_dir: sortDir
      }
    })
  },

  // Risk of Ruin from trading history (Monte Carlo simulation)
  getRiskOfRuin: (days = 30) =>
    api.get('/trades/risk/ruin', { params: { days } }),

  // Portfolio concentration risk analysis
  getConcentrationRisk: () =>
    api.get('/trades/risk/concentration'),
}

// Signals API (OctoBot Integration Health)
export const signalsAPI = {
  // Get signal health status
  getHealth: () =>
    api.get('/signals/health'),

  // Get latest trading signal
  getLatest: (symbol = 'BTC/USDT') =>
    api.get('/signals/latest', { params: { symbol } }),

  // Signal-trade performance correlation
  getPerformance: (params = {}) => {
    const { symbol = 'BTC/USDT', days = 30 } = params
    return api.get('/v1/signals/performance', { params: { symbol, days } })
  },

  // Daily performance breakdown
  getDailyPerformance: (params = {}) => {
    const { symbol = 'BTC/USDT', days = 30 } = params
    return api.get('/v1/signals/performance/daily', { params: { symbol, days } })
  },

  // OctoBot Integration
  getOctoBotHealth: () =>
    api.get('/v1/signals/octobot/health'),

  getOctoBotPortfolio: () =>
    api.get('/v1/signals/octobot/portfolio'),

  getOctoBotOrders: () =>
    api.get('/v1/signals/octobot/orders'),

  getOctoBotClosedOrders: (limit = 50) =>
    api.get('/v1/signals/octobot/orders/closed', { params: { limit } }),

  // Sync operations
  triggerSync: () =>
    api.post('/v1/signals/octobot/sync'),

  getSyncStatus: () =>
    api.get('/v1/signals/octobot/sync/status'),

  // Execute signal via OctoBot
  executeSignal: (symbol = 'BTC/USDT', force = false) =>
    api.post('/v1/signals/execute', { symbol, force }),
}

// Backtest API (Historical Strategy Analysis)
export const backtestAPI = {
  // Get backtest summary statistics
  getSummary: (days = 30) =>
    api.get('/v1/backtest/summary', { params: { days } }),

  // Get prediction accuracy by symbol
  getAccuracy: (days = 30) =>
    api.get('/v1/backtest/accuracy', { params: { days } }),

  // Get confidence calibration data
  getCalibration: (days = 30) =>
    api.get('/v1/backtest/calibration', { params: { days } }),

  // Run new backtest analysis
  runBacktest: (params = {}) => {
    const { days = 30, symbol } = params
    return api.post('/v1/backtest/run', { days, ...(symbol && { symbol }) })
  },
}

// Export default API instance
export default api
