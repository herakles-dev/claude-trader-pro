import React, { useState, useEffect } from 'react'
import TradingViewChart from '../components/TradingViewChart'
import MarketOverview from '../components/MarketOverview'
import SentimentIndicators from '../components/SentimentIndicators'
import PredictionCard from '../components/PredictionCard'
import SystemHealth from '../components/SystemHealth'
import AutomatedCycle from '../components/AutomatedCycle'
import TradePerformance from '../components/TradePerformance'
import SignalHealth from '../components/SignalHealth'
import { useMultipleMarkets } from '../hooks/useMarketData'
import { logComponentData, logMarketData } from '../utils/debugLogger'

function Dashboard() {
  const [selectedSymbol, setSelectedSymbol] = useState('BTC')
  const [chartInterval, setChartInterval] = useState('60')

  const symbols = ['BTC', 'ETH', 'SOL']
  const { marketsData } = useMultipleMarkets(symbols)

  // Debug logging when market data loads
  useEffect(() => {
    if (marketsData) {
      logComponentData('Dashboard', 'marketsData', marketsData, { symbols })
      logMarketData('Dashboard.jsx', marketsData)
      console.log('%c[DASHBOARD DEBUG] Markets data:', 'color: #22c55e', marketsData)

      // Check each symbol's data integrity
      symbols.forEach(symbol => {
        const data = marketsData[symbol]
        if (data) {
          console.log(`%c[DASHBOARD DEBUG] ${symbol} data:`, 'color: #3b82f6', {
            current_price: data.current_price,
            price_change_percentage_24h: data.price_change_percentage_24h,
            total_volume: data.total_volume,
            notAvailable: data.notAvailable,
          })
          if (data.notAvailable) {
            console.warn(`%c[DASHBOARD DEBUG] ${symbol} marked as not available`, 'color: #ef4444')
          }
          if (data.current_price === 0 || data.current_price === undefined) {
            console.warn(`%c[DASHBOARD DEBUG] ${symbol} has invalid price: ${data.current_price}`, 'color: #ef4444')
          }
        } else {
          console.warn(`%c[DASHBOARD DEBUG] No data for ${symbol}`, 'color: #ef4444')
        }
      })
    }
  }, [marketsData])

  const intervals = [
    { label: '15m', value: '15' },
    { label: '1h', value: '60' },
    { label: '4h', value: '240' },
    { label: '1D', value: 'D' },
  ]

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between space-y-4 sm:space-y-0">
        <div>
          <h1 className="text-3xl font-bold text-white">Trading Dashboard</h1>
          <p className="text-gray-400 mt-1">
            AI-powered cryptocurrency trading intelligence
          </p>
        </div>

        {/* Symbol Selector */}
        <div className="flex items-center space-x-3">
          <span className="text-sm text-gray-400">Symbol:</span>
          <div className="flex space-x-2">
            {symbols.map((symbol) => (
              <button
                key={symbol}
                onClick={() => setSelectedSymbol(symbol)}
                className={`px-4 py-2 rounded-lg font-medium transition-colors duration-200 ${
                  selectedSymbol === symbol
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
                }`}
              >
                {symbol}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Quick Stats Bar */}
      {marketsData && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {symbols.map((symbol) => {
            const data = marketsData[symbol]
            if (!data) return null

            const isPositive = data.price_change_percentage_24h >= 0

            return (
              <div
                key={symbol}
                className={`card p-4 cursor-pointer transition-all ${
                  selectedSymbol === symbol
                    ? 'ring-2 ring-blue-500'
                    : 'hover:border-gray-600'
                }`}
                onClick={() => setSelectedSymbol(symbol)}
              >
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-sm text-gray-400">{symbol}/USDT</div>
                    <div className="text-xl font-bold text-white font-mono">
                      ${data.current_price?.toLocaleString()}
                    </div>
                  </div>
                  <div className="text-right">
                    <div
                      className={`text-lg font-semibold ${
                        isPositive ? 'text-green-400' : 'text-red-400'
                      }`}
                    >
                      {isPositive ? '+' : ''}
                      {data.price_change_percentage_24h?.toFixed(2)}%
                    </div>
                    <div className="text-xs text-gray-500">24h</div>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Main Grid Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column - Chart (takes 2 columns on large screens) */}
        <div className="lg:col-span-2 space-y-6">
          {/* Chart Controls */}
          <div className="card p-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold text-white">
                {selectedSymbol}/USDT Chart
              </h2>
              <div className="flex items-center space-x-2">
                <span className="text-sm text-gray-400">Interval:</span>
                <div className="flex space-x-1">
                  {intervals.map((interval) => (
                    <button
                      key={interval.value}
                      onClick={() => setChartInterval(interval.value)}
                      className={`px-3 py-1 text-sm rounded transition-colors ${
                        chartInterval === interval.value
                          ? 'bg-blue-600 text-white'
                          : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                      }`}
                    >
                      {interval.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* TradingView Chart */}
          <div className="card p-4">
            <TradingViewChart symbol={selectedSymbol} interval={chartInterval} />
          </div>

          {/* Market Overview */}
          <MarketOverview symbol={selectedSymbol} />
        </div>

        {/* Right Column - Sidebar */}
        <div className="space-y-6">
          {/* Paper Trading Performance */}
          <TradePerformance symbol={`${selectedSymbol}/USDT`} />

          {/* OctoBot Signal Health */}
          <SignalHealth />

          {/* Automated 4-Hour Cycle */}
          <AutomatedCycle />

          {/* Latest Prediction */}
          <PredictionCard symbol={selectedSymbol} />

          {/* Sentiment Indicators */}
          <SentimentIndicators />

          {/* System Health */}
          <SystemHealth />
        </div>
      </div>

      {/* Bottom Info Banner */}
      <div className="card p-4 bg-gradient-to-r from-blue-900/20 to-purple-900/20 border-blue-700">
        <div className="flex items-center space-x-3">
          <span className="text-2xl">💡</span>
          <div>
            <div className="text-sm font-medium text-white">
              Trading with AI Intelligence
            </div>
            <div className="text-xs text-gray-400 mt-1">
              ClaudeTrAIder Pro uses advanced AI models to analyze market data,
              sentiment, and technical indicators to provide actionable predictions.
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Dashboard
