/**
 * Market Data Fetcher Service
 * Periodically fetches market data and broadcasts to WebSocket clients
 * Features: caching, error recovery, throttling
 */

const axios = require('axios');
const logger = require('../config/logger');
const config = require('../config');
const claudeEngineClient = require('./claudeEngineClient');
const NodeCache = require('node-cache');

class MarketDataFetcher {
  constructor() {
    this.cache = new NodeCache({
      stdTTL: 60, // 60 seconds TTL - reduced API calls
      checkperiod: 30
    });

    this.fetchInterval = null;
    this.broadcastCallback = null;
    this.isRunning = false;
    this.fetchIntervalMs = 60000; // 60 seconds - respect rate limits
    this.lastFetchTimestamp = 0;
    this.minFetchInterval = 30000; // Minimum 30s between fetches
    
    // Track symbols to fetch
    this.activeSymbols = new Set([
      'BTC/USDT',
      'ETH/USDT',
      'SOL/USDT',
      'BNB/USDT',
      'XRP/USDT'
    ]);
    
    // Performance metrics
    this.metrics = {
      totalFetches: 0,
      successfulFetches: 0,
      failedFetches: 0,
      lastFetchTime: null,
      averageFetchDuration: 0
    };
  }

  /**
   * Start periodic market data fetching
   */
  start(broadcastCallback) {
    if (this.isRunning) {
      logger.warn('Market data fetcher already running');
      return;
    }

    if (typeof broadcastCallback !== 'function') {
      throw new Error('Broadcast callback must be a function');
    }

    this.broadcastCallback = broadcastCallback;
    this.isRunning = true;

    // Immediate first fetch
    this.fetchAllMarketData();

    // Setup periodic fetching
    this.fetchInterval = setInterval(() => {
      this.fetchAllMarketData();
    }, this.fetchIntervalMs);

    logger.info('Market data fetcher started', {
      interval: `${this.fetchIntervalMs}ms`,
      symbols: Array.from(this.activeSymbols)
    });
  }

  /**
   * Stop market data fetching
   */
  stop() {
    if (this.fetchInterval) {
      clearInterval(this.fetchInterval);
      this.fetchInterval = null;
    }

    this.isRunning = false;
    logger.info('Market data fetcher stopped');
  }

  /**
   * Fetch market data for all active symbols using batched API call.
   *
   * IMPORTANT: Uses CoinGecko's /coins/markets endpoint (not /simple/price)
   * because only /coins/markets returns high_24h and low_24h values.
   *
   * Flow:
   * 1. Rate limit check to respect CoinGecko free tier (30 calls/min)
   * 2. Map trading pairs (BTC/USDT) to CoinGecko IDs (bitcoin)
   * 3. Single batch API call for all coins (reduces rate limit usage)
   * 4. Transform response to consistent internal format
   * 5. Cache by both formats (BTC/USDT and BTC) for frontend compatibility
   * 6. Broadcast updates via WebSocket to connected clients
   * 7. On error, serve stale cached data with {stale: true} flag
   */
  async fetchAllMarketData() {
    const startTime = Date.now();
    const results = [];

    // Rate limiting: CoinGecko free tier allows ~30 calls/min
    // Minimum 30s between fetches prevents hitting limits
    const timeSinceLastFetch = startTime - this.lastFetchTimestamp;
    if (timeSinceLastFetch < this.minFetchInterval) {
      logger.debug('Skipping fetch - rate limit', {
        timeSinceLastFetch,
        minInterval: this.minFetchInterval
      });
      return;
    }

    logger.debug('Fetching market data for all symbols (batched)', {
      symbolCount: this.activeSymbols.size
    });

    try {
      // Map trading pair format (BTC/USDT) to CoinGecko ID format (bitcoin)
      // CoinGecko uses lowercase slug names, not ticker symbols
      const coinMap = {
        'BTC/USDT': 'bitcoin',
        'ETH/USDT': 'ethereum',
        'SOL/USDT': 'solana',
        'BNB/USDT': 'binancecoin',
        'XRP/USDT': 'ripple'
      };

      // Build comma-separated list of coin IDs for batch request
      const coinIds = Array.from(this.activeSymbols)
        .map(s => coinMap[s])
        .filter(Boolean)  // Remove any unmapped symbols
        .join(',');

      // CRITICAL: Use /coins/markets endpoint, NOT /simple/price
      // Only /coins/markets returns: high_24h, low_24h, market_cap, total_volume
      // /simple/price only returns: current_price, price_change_24h
      const response = await axios.get(
        `https://api.coingecko.com/api/v3/coins/markets`,
        {
          params: {
            vs_currency: 'usd',
            ids: coinIds,
            order: 'market_cap_desc',
            per_page: 10,
            page: 1,
            sparkline: false,
            price_change_percentage: '24h'
          },
          timeout: 10000
        }
      );

      this.lastFetchTimestamp = Date.now();

      // Index response by coin ID for O(1) lookup when processing symbols
      const coinDataMap = {};
      for (const coin of response.data) {
        coinDataMap[coin.id] = coin;
      }

      // Transform each coin's data to our internal format
      for (const symbol of this.activeSymbols) {
        const coinId = coinMap[symbol];
        const data = coinDataMap[coinId];

        if (data) {
          // Extract base symbol (BTC from BTC/USDT) for frontend display
          const baseSymbol = symbol.split('/')[0];

          // Normalize to consistent format used throughout the app
          const transformedData = {
            symbol: baseSymbol,
            current_price: data.current_price,
            price_change_24h: data.price_change_24h || 0,
            price_change_percentage_24h: data.price_change_percentage_24h || 0,
            high_24h: data.high_24h,   // Only available from /coins/markets
            low_24h: data.low_24h,     // Only available from /coins/markets
            total_volume: data.total_volume || 0,
            market_cap: data.market_cap || null,
            last_updated: data.last_updated || new Date().toISOString(),
            source: 'coingecko'
          };

          // Cache by both key formats for flexibility:
          // - 'BTC/USDT': used by internal services
          // - 'BTC': used by frontend components
          this.cache.set(symbol, transformedData);
          this.cache.set(baseSymbol, transformedData);
          results.push(transformedData);
          this.metrics.successfulFetches++;
        } else {
          this.metrics.failedFetches++;
        }
      }

      // Push real-time updates to all WebSocket clients
      if (results.length > 0 && this.broadcastCallback) {
        results.forEach(data => {
          this.broadcastCallback('market_update', data);
        });
      }

      const duration = Date.now() - startTime;
      this.updateMetrics(duration);

      logger.info('Market data fetch completed (batched)', {
        successful: results.length,
        failed: this.activeSymbols.size - results.length,
        duration: `${duration}ms`
      });

    } catch (error) {
      logger.error('Market data batch fetch error', {
        error: error.message
      });

      // Graceful degradation: serve stale cached data on API failure
      // The {stale: true} flag lets consumers know data may be outdated
      for (const symbol of this.activeSymbols) {
        const cached = this.cache.get(symbol);
        if (cached) {
          results.push({ ...cached, stale: true });
        }
      }

      // Still broadcast stale data to keep UI responsive
      if (results.length > 0 && this.broadcastCallback) {
        results.forEach(data => {
          this.broadcastCallback('market_update', data);
        });
      }
    }
  }

  /**
   * Fetch market data for a single symbol using CoinGecko API.
   *
   * Used for on-demand requests (e.g., when a new symbol is added).
   * Prefers cached data to reduce API calls. Falls back to stale cache on error.
   *
   * @param {string} symbol - Trading pair (BTC/USDT) or base symbol (BTC)
   * @returns {Object|null} Transformed market data or null if unavailable
   */
  async fetchMarketDataForSymbol(symbol) {
    try {
      // Cache-first strategy: return cached data if available (TTL: 60s)
      const cached = this.cache.get(symbol);
      if (cached) {
        logger.debug('Returning cached market data', { symbol });
        return cached;
      }

      // Symbol mapping supports both formats:
      // - Trading pairs: 'BTC/USDT' (from OctoBot)
      // - Base symbols: 'BTC' (from frontend)
      const coinMap = {
        'BTC/USDT': 'bitcoin',
        'ETH/USDT': 'ethereum',
        'SOL/USDT': 'solana',
        'BNB/USDT': 'binancecoin',
        'XRP/USDT': 'ripple',
        'BTC': 'bitcoin',
        'ETH': 'ethereum',
        'SOL': 'solana',
        'BNB': 'binancecoin',
        'XRP': 'ripple'
      };

      const coinId = coinMap[symbol];
      if (!coinId) {
        logger.warn('Unknown symbol for CoinGecko', { symbol });
        return null;
      }

      // CRITICAL: Use /coins/markets endpoint (not /simple/price)
      // This is the same endpoint as batch fetch - ensures consistent data
      const response = await axios.get(
        `https://api.coingecko.com/api/v3/coins/markets`,
        {
          params: {
            vs_currency: 'usd',
            ids: coinId,
            order: 'market_cap_desc',
            per_page: 1,
            page: 1,
            sparkline: false,
            price_change_percentage: '24h'
          },
          timeout: 5000
        }
      );

      const data = response.data[0];
      if (!data) {
        throw new Error(`No data returned for ${coinId}`);
      }

      // Normalize symbol format for frontend (strip /USDT suffix)
      const baseSymbol = symbol.includes('/') ? symbol.split('/')[0] : symbol;

      // Transform to internal format (matches batch fetch output)
      const transformedData = {
        symbol: baseSymbol,
        current_price: data.current_price,
        price_change_24h: data.price_change_24h || 0,
        price_change_percentage_24h: data.price_change_percentage_24h || 0,
        high_24h: data.high_24h,    // Requires /coins/markets endpoint
        low_24h: data.low_24h,      // Requires /coins/markets endpoint
        total_volume: data.total_volume || 0,
        market_cap: data.market_cap || null,
        last_updated: data.last_updated || new Date().toISOString(),
        source: 'coingecko'
      };

      // Dual-key caching for maximum compatibility
      this.cache.set(symbol, transformedData);
      this.cache.set(baseSymbol, transformedData);

      logger.debug('Fetched market data from CoinGecko', { symbol, price: transformedData.current_price });

      return transformedData;

    } catch (error) {
      logger.error('Failed to fetch market data', {
        symbol,
        error: error.message
      });

      // Graceful degradation: prefer stale data over no data
      // UI can check {stale: true} flag to show warning if needed
      const staleCache = this.cache.get(symbol);
      if (staleCache) {
        logger.warn('Returning stale cache data', { symbol });
        return { ...staleCache, stale: true };
      }

      return null;
    }
  }

  /**
   * Add symbol to active fetch list
   */
  addSymbol(symbol) {
    if (!this.activeSymbols.has(symbol)) {
      this.activeSymbols.add(symbol);
      logger.info('Added symbol to fetch list', { 
        symbol,
        totalSymbols: this.activeSymbols.size 
      });

      // Fetch immediately
      this.fetchMarketDataForSymbol(symbol).then(data => {
        if (data && this.broadcastCallback) {
          this.broadcastCallback('market_update', data);
        }
      });
    }
  }

  /**
   * Remove symbol from active fetch list
   */
  removeSymbol(symbol) {
    if (this.activeSymbols.has(symbol)) {
      this.activeSymbols.delete(symbol);
      this.cache.del(symbol);
      logger.info('Removed symbol from fetch list', { 
        symbol,
        totalSymbols: this.activeSymbols.size 
      });
    }
  }

  /**
   * Get cached market data
   */
  getCachedData(symbol) {
    return this.cache.get(symbol) || null;
  }

  /**
   * Get all cached market data
   */
  getAllCachedData() {
    const data = {};
    this.cache.keys().forEach(key => {
      data[key] = this.cache.get(key);
    });
    return data;
  }

  /**
   * Update performance metrics
   */
  updateMetrics(duration) {
    this.metrics.totalFetches++;
    this.metrics.lastFetchTime = new Date().toISOString();
    
    // Calculate rolling average
    if (this.metrics.averageFetchDuration === 0) {
      this.metrics.averageFetchDuration = duration;
    } else {
      this.metrics.averageFetchDuration = 
        (this.metrics.averageFetchDuration * 0.8) + (duration * 0.2);
    }
  }

  /**
   * Get statistics
   */
  getStats() {
    return {
      isRunning: this.isRunning,
      activeSymbols: Array.from(this.activeSymbols),
      symbolCount: this.activeSymbols.size,
      fetchInterval: this.fetchIntervalMs,
      cacheKeys: this.cache.keys().length,
      metrics: this.metrics
    };
  }

  /**
   * Clear all cached data
   */
  clearCache() {
    this.cache.flushAll();
    logger.info('Market data cache cleared');
  }
}

// Export singleton instance
module.exports = new MarketDataFetcher();
