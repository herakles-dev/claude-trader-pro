/**
 * Debug Logger for ClaudeTrader Pro
 * Logs all frontend data loads with detailed context for data integrity tracking
 */

const DEBUG_ENABLED = true // Set to false in production
const LOG_STYLES = {
  api: 'color: #3b82f6; font-weight: bold',      // Blue for API calls
  data: 'color: #22c55e; font-weight: bold',     // Green for data received
  error: 'color: #ef4444; font-weight: bold',    // Red for errors
  warning: 'color: #f59e0b; font-weight: bold',  // Orange for warnings
  component: 'color: #a855f7; font-weight: bold', // Purple for component loads
}

/**
 * Log an API request
 */
export const logApiRequest = (endpoint, params = {}) => {
  if (!DEBUG_ENABLED) return
  console.groupCollapsed(`%c[API REQUEST] ${endpoint}`, LOG_STYLES.api)
  console.log('Timestamp:', new Date().toISOString())
  console.log('Endpoint:', endpoint)
  console.log('Params:', params)
  console.groupEnd()
}

/**
 * Log API response data
 */
export const logApiResponse = (endpoint, response, rawResponse = null) => {
  if (!DEBUG_ENABLED) return
  console.groupCollapsed(`%c[API RESPONSE] ${endpoint}`, LOG_STYLES.data)
  console.log('Timestamp:', new Date().toISOString())
  console.log('Endpoint:', endpoint)
  console.log('Processed Data:', response)
  if (rawResponse) {
    console.log('Raw Response:', rawResponse)
  }

  // Data integrity checks
  if (response === null || response === undefined) {
    console.warn('%c[WARNING] Response is null/undefined', LOG_STYLES.warning)
  }
  if (Array.isArray(response) && response.length === 0) {
    console.warn('%c[WARNING] Response is empty array', LOG_STYLES.warning)
  }
  if (typeof response === 'object' && response !== null && Object.keys(response).length === 0) {
    console.warn('%c[WARNING] Response is empty object', LOG_STYLES.warning)
  }

  console.groupEnd()
}

/**
 * Log API error
 */
export const logApiError = (endpoint, error) => {
  if (!DEBUG_ENABLED) return
  console.groupCollapsed(`%c[API ERROR] ${endpoint}`, LOG_STYLES.error)
  console.log('Timestamp:', new Date().toISOString())
  console.log('Endpoint:', endpoint)
  console.error('Error:', error)
  console.log('Error Message:', error?.message || 'Unknown error')
  console.log('Error Response:', error?.response?.data)
  console.groupEnd()
}

/**
 * Log component data load
 */
export const logComponentData = (componentName, dataName, data, metadata = {}) => {
  if (!DEBUG_ENABLED) return
  console.groupCollapsed(`%c[COMPONENT DATA] ${componentName} - ${dataName}`, LOG_STYLES.component)
  console.log('Timestamp:', new Date().toISOString())
  console.log('Component:', componentName)
  console.log('Data Name:', dataName)
  console.log('Data:', data)
  console.log('Metadata:', metadata)

  // Data integrity checks
  checkDataIntegrity(componentName, dataName, data)

  console.groupEnd()
}

/**
 * Check data integrity and log warnings
 */
const checkDataIntegrity = (source, dataName, data) => {
  const issues = []

  // Check for null/undefined
  if (data === null || data === undefined) {
    issues.push('Data is null/undefined')
  }

  // Check for empty arrays
  if (Array.isArray(data) && data.length === 0) {
    issues.push('Array is empty')
  }

  // Check for empty objects
  if (typeof data === 'object' && data !== null && !Array.isArray(data) && Object.keys(data).length === 0) {
    issues.push('Object is empty')
  }

  // Check for NaN values in numbers
  if (typeof data === 'number' && isNaN(data)) {
    issues.push('Value is NaN')
  }

  // Check arrays for undefined/null items
  if (Array.isArray(data)) {
    const nullItems = data.filter(item => item === null || item === undefined)
    if (nullItems.length > 0) {
      issues.push(`Array contains ${nullItems.length} null/undefined items`)
    }
  }

  // Log warnings
  if (issues.length > 0) {
    console.warn(`%c[DATA INTEGRITY] ${source} - ${dataName}:`, LOG_STYLES.warning, issues)
  }
}

/**
 * Log trade data specifically
 */
export const logTradeData = (source, trades, stats = null) => {
  if (!DEBUG_ENABLED) return
  console.groupCollapsed(`%c[TRADE DATA] ${source}`, LOG_STYLES.data)
  console.log('Timestamp:', new Date().toISOString())
  console.log('Source:', source)
  console.log('Trade Count:', trades?.length || 0)
  console.log('Trades:', trades)
  if (stats) {
    console.log('Statistics:', stats)
    // Check for expected fields
    const expectedFields = ['total_trades', 'total_pnl', 'win_rate', 'winning_trades', 'losing_trades']
    const missingFields = expectedFields.filter(field => stats[field] === undefined)
    if (missingFields.length > 0) {
      console.warn('%c[WARNING] Missing expected fields:', LOG_STYLES.warning, missingFields)
    }
  }
  console.groupEnd()
}

/**
 * Log prediction data specifically
 */
export const logPredictionData = (source, predictions, pagination = null) => {
  if (!DEBUG_ENABLED) return
  console.groupCollapsed(`%c[PREDICTION DATA] ${source}`, LOG_STYLES.data)
  console.log('Timestamp:', new Date().toISOString())
  console.log('Source:', source)
  console.log('Prediction Count:', predictions?.length || 0)
  console.log('Predictions:', predictions)
  if (pagination) {
    console.log('Pagination:', pagination)
  }
  // Check prediction structure
  if (predictions && predictions.length > 0) {
    const sample = predictions[0]
    const expectedFields = ['id', 'symbol', 'direction', 'confidence']
    const missingFields = expectedFields.filter(field => sample[field] === undefined)
    if (missingFields.length > 0) {
      console.warn('%c[WARNING] Sample prediction missing fields:', LOG_STYLES.warning, missingFields)
    }
  }
  console.groupEnd()
}

/**
 * Log market data specifically
 */
export const logMarketData = (source, marketData) => {
  if (!DEBUG_ENABLED) return
  console.groupCollapsed(`%c[MARKET DATA] ${source}`, LOG_STYLES.data)
  console.log('Timestamp:', new Date().toISOString())
  console.log('Source:', source)
  console.log('Market Data:', marketData)
  // Check for expected fields
  if (marketData && typeof marketData === 'object') {
    Object.entries(marketData).forEach(([symbol, data]) => {
      if (data) {
        const expectedFields = ['current_price', 'price_change_percentage_24h']
        const missingFields = expectedFields.filter(field => data[field] === undefined)
        if (missingFields.length > 0) {
          console.warn(`%c[WARNING] ${symbol} missing fields:`, LOG_STYLES.warning, missingFields)
        }
        if (data.current_price === 0) {
          console.warn(`%c[WARNING] ${symbol} has zero price`, LOG_STYLES.warning)
        }
      }
    })
  }
  console.groupEnd()
}

/**
 * Log analytics data specifically
 */
export const logAnalyticsData = (source, type, data) => {
  if (!DEBUG_ENABLED) return
  console.groupCollapsed(`%c[ANALYTICS DATA] ${source} - ${type}`, LOG_STYLES.data)
  console.log('Timestamp:', new Date().toISOString())
  console.log('Source:', source)
  console.log('Type:', type)
  console.log('Data:', data)
  console.groupEnd()
}

/**
 * Create a summary of all data loaded in the current session
 */
let sessionDataSummary = {
  apiCalls: [],
  errors: [],
  warnings: [],
}

export const addToSessionSummary = (type, data) => {
  if (!DEBUG_ENABLED) return
  if (type === 'api') sessionDataSummary.apiCalls.push(data)
  if (type === 'error') sessionDataSummary.errors.push(data)
  if (type === 'warning') sessionDataSummary.warnings.push(data)
}

export const getSessionSummary = () => {
  return { ...sessionDataSummary }
}

export const clearSessionSummary = () => {
  sessionDataSummary = { apiCalls: [], errors: [], warnings: [] }
}

/**
 * Print session summary to console
 */
export const printSessionSummary = () => {
  if (!DEBUG_ENABLED) return
  console.group('%c[SESSION SUMMARY]', 'color: #8b5cf6; font-weight: bold; font-size: 14px')
  console.log('Total API Calls:', sessionDataSummary.apiCalls.length)
  console.log('Total Errors:', sessionDataSummary.errors.length)
  console.log('Total Warnings:', sessionDataSummary.warnings.length)
  console.log('Details:', sessionDataSummary)
  console.groupEnd()
}

// Export a window reference for console debugging
if (typeof window !== 'undefined') {
  window.__claudeTraderDebug = {
    getSessionSummary,
    printSessionSummary,
    clearSessionSummary,
    DEBUG_ENABLED,
  }
}

export default {
  logApiRequest,
  logApiResponse,
  logApiError,
  logComponentData,
  logTradeData,
  logPredictionData,
  logMarketData,
  logAnalyticsData,
  addToSessionSummary,
  getSessionSummary,
  printSessionSummary,
  clearSessionSummary,
}
