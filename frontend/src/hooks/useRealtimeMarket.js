/**
 * Real-time Market Data Hook
 * Automatically subscribes to symbol updates and provides live data
 */

import { useEffect, useState } from 'react';
import { useWebSocket } from '../context/WebSocketContext';

/**
 * Hook to get real-time market data for a symbol
 * @param {string} symbol - Trading symbol (e.g., 'BTC/USDT')
 * @returns {Object} - Market data object or null
 */
export function useRealtimeMarket(symbol) {
  const { marketData, subscribe, unsubscribe, connected } = useWebSocket();
  const [data, setData] = useState(null);

  useEffect(() => {
    if (!symbol || !connected) {
      return;
    }

    // Subscribe to symbol updates
    subscribe(symbol);

    // Cleanup: unsubscribe on unmount
    return () => {
      unsubscribe(symbol);
    };
  }, [symbol, connected, subscribe, unsubscribe]);

  useEffect(() => {
    // Update local state when market data changes
    if (marketData[symbol]) {
      setData(marketData[symbol]);
    }
  }, [marketData, symbol]);

  return data;
}

/**
 * Hook to get real-time market data for multiple symbols
 * @param {string[]} symbols - Array of trading symbols
 * @returns {Object} - Map of symbol -> market data
 */
export function useRealtimeMarkets(symbols = []) {
  const { marketData, subscribe, unsubscribe, connected } = useWebSocket();
  const [data, setData] = useState({});

  useEffect(() => {
    if (!symbols.length || !connected) {
      return;
    }

    // Subscribe to all symbols
    symbols.forEach(symbol => {
      subscribe(symbol);
    });

    // Cleanup: unsubscribe from all symbols
    return () => {
      symbols.forEach(symbol => {
        unsubscribe(symbol);
      });
    };
  }, [symbols.join(','), connected, subscribe, unsubscribe]);

  useEffect(() => {
    // Update local state with all subscribed symbols
    const filtered = {};
    symbols.forEach(symbol => {
      if (marketData[symbol]) {
        filtered[symbol] = marketData[symbol];
      }
    });
    setData(filtered);
  }, [marketData, symbols.join(',')]);

  return data;
}

/**
 * Hook to watch for price changes
 * @param {string} symbol - Trading symbol
 * @param {function} callback - Callback function when price changes
 */
export function usePriceAlert(symbol, callback) {
  const data = useRealtimeMarket(symbol);
  const [previousPrice, setPreviousPrice] = useState(null);

  useEffect(() => {
    if (!data || !data.price) {
      return;
    }

    if (previousPrice !== null && previousPrice !== data.price) {
      const change = data.price - previousPrice;
      const changePercent = (change / previousPrice) * 100;
      
      callback({
        symbol,
        oldPrice: previousPrice,
        newPrice: data.price,
        change,
        changePercent
      });
    }

    setPreviousPrice(data.price);
  }, [data?.price]);
}

export default useRealtimeMarket;
