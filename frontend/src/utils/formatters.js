import { format, formatDistance, formatRelative } from 'date-fns'

/**
 * Format price with appropriate decimal places
 */
export function formatPrice(price, decimals = 2) {
  if (price === null || price === undefined) return '--'
  
  const num = Number(price)
  if (isNaN(num)) return '--'

  // Use more decimals for small numbers
  if (num < 1) decimals = 6
  else if (num < 10) decimals = 4
  else if (num < 100) decimals = 3

  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(num)
}

/**
 * Format price with currency symbol
 */
export function formatCurrency(price, currency = 'USD', decimals = 2) {
  if (price === null || price === undefined) return '--'
  
  const num = Number(price)
  if (isNaN(num)) return '--'

  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(num)
}

/**
 * Format large numbers with abbreviations (K, M, B)
 */
export function formatLargeNumber(num) {
  if (num === null || num === undefined) return '--'
  
  const value = Number(num)
  if (isNaN(value)) return '--'

  if (value >= 1e9) {
    return `${(value / 1e9).toFixed(2)}B`
  } else if (value >= 1e6) {
    return `${(value / 1e6).toFixed(2)}M`
  } else if (value >= 1e3) {
    return `${(value / 1e3).toFixed(2)}K`
  }
  return value.toFixed(2)
}

/**
 * Format percentage with sign and color class
 */
export function formatPercentage(value, includeSign = true) {
  if (value === null || value === undefined) return '--'
  
  const num = Number(value)
  if (isNaN(num)) return '--'

  const sign = num > 0 ? '+' : ''
  const formatted = `${includeSign ? sign : ''}${num.toFixed(2)}%`
  
  return formatted
}

/**
 * Get color class for percentage change
 */
export function getPercentageColor(value) {
  const num = Number(value)
  if (isNaN(num) || num === 0) return 'text-gray-400'
  return num > 0 ? 'text-green-400' : 'text-red-400'
}

/**
 * Format date to human-readable string
 */
export function formatDate(date, formatString = 'MMM dd, yyyy HH:mm') {
  if (!date) return '--'
  
  try {
    const dateObj = typeof date === 'string' ? new Date(date) : date
    return format(dateObj, formatString)
  } catch (error) {
    console.error('Date formatting error:', error)
    return '--'
  }
}

/**
 * Format date relative to now (e.g., "2 hours ago")
 */
export function formatRelativeTime(date) {
  if (!date) return '--'
  
  try {
    const dateObj = typeof date === 'string' ? new Date(date) : date
    return formatDistance(dateObj, new Date(), { addSuffix: true })
  } catch (error) {
    console.error('Relative time formatting error:', error)
    return '--'
  }
}

/**
 * Format timestamp to time only
 */
export function formatTime(timestamp) {
  if (!timestamp) return '--'
  
  try {
    const date = typeof timestamp === 'string' ? new Date(timestamp) : timestamp
    return format(date, 'HH:mm:ss')
  } catch (error) {
    console.error('Time formatting error:', error)
    return '--'
  }
}

/**
 * Format confidence score as percentage
 */
export function formatConfidence(confidence) {
  if (confidence === null || confidence === undefined) return '--'
  
  const value = Number(confidence)
  if (isNaN(value)) return '--'

  // Confidence is typically 0-1, convert to percentage
  const percentage = value > 1 ? value : value * 100
  return `${percentage.toFixed(1)}%`
}

/**
 * Get confidence color based on value
 */
export function getConfidenceColor(confidence) {
  const value = Number(confidence) > 1 ? Number(confidence) : Number(confidence) * 100
  
  if (value >= 80) return 'text-green-400'
  if (value >= 60) return 'text-yellow-400'
  if (value >= 40) return 'text-orange-400'
  return 'text-red-400'
}

/**
 * Format prediction direction with emoji
 */
export function formatDirection(direction) {
  if (!direction) return '--'
  
  const dir = direction.toUpperCase()
  if (dir === 'UP' || dir === 'LONG' || dir === 'BUY') {
    return '🔼 UP'
  } else if (dir === 'DOWN' || dir === 'SHORT' || dir === 'SELL') {
    return '🔽 DOWN'
  } else if (dir === 'NEUTRAL' || dir === 'HOLD') {
    return '➖ NEUTRAL'
  }
  return direction
}

/**
 * Get direction color class
 */
export function getDirectionColor(direction) {
  if (!direction) return 'text-gray-400'
  
  const dir = direction.toUpperCase()
  if (dir === 'UP' || dir === 'LONG' || dir === 'BUY') {
    return 'text-green-400'
  } else if (dir === 'DOWN' || dir === 'SHORT' || dir === 'SELL') {
    return 'text-red-400'
  }
  return 'text-gray-400'
}

/**
 * Format volume with abbreviation
 */
export function formatVolume(volume) {
  return formatLargeNumber(volume)
}

/**
 * Truncate text with ellipsis
 */
export function truncate(text, maxLength = 50) {
  if (!text) return ''
  if (text.length <= maxLength) return text
  return text.substring(0, maxLength) + '...'
}

/**
 * Format symbol display (e.g., BTC/USDT)
 */
export function formatSymbol(symbol, quote = 'USDT') {
  if (!symbol) return '--'
  return `${symbol}/${quote}`
}

/**
 * Parse and format API error messages
 */
export function formatError(error) {
  if (typeof error === 'string') return error
  
  if (error.response?.data?.message) {
    return error.response.data.message
  }
  
  if (error.message) {
    return error.message
  }
  
  return 'An unexpected error occurred'
}
