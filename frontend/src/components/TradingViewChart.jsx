import React, { useEffect, useRef } from 'react'

function TradingViewChart({ symbol = 'BTC', interval = '60' }) {
  const container = useRef()

  useEffect(() => {
    // Map our symbols to TradingView format
    const symbolMap = {
      BTC: 'BINANCE:BTCUSDT',
      ETH: 'BINANCE:ETHUSDT',
      SOL: 'BINANCE:SOLUSDT',
    }

    const script = document.createElement('script')
    script.src = 'https://s3.tradingview.com/tv.js'
    script.async = true
    script.onload = () => {
      if (typeof TradingView !== 'undefined') {
        new TradingView.widget({
          width: '100%',
          height: 500,
          symbol: symbolMap[symbol] || 'BINANCE:BTCUSDT',
          interval: interval,
          timezone: 'Etc/UTC',
          theme: 'dark',
          style: '1',
          locale: 'en',
          toolbar_bg: '#1f2937',
          enable_publishing: false,
          allow_symbol_change: true,
          container_id: container.current.id,
          studies: [
            'RSI@tv-basicstudies',
            'MACD@tv-basicstudies',
            'Volume@tv-basicstudies',
          ],
          backgroundColor: '#111827',
          gridColor: '#1f2937',
          hide_side_toolbar: false,
          details: true,
          hotlist: true,
          calendar: true,
        })
      }
    }
    document.head.appendChild(script)

    return () => {
      // Cleanup
      if (document.head.contains(script)) {
        document.head.removeChild(script)
      }
    }
  }, [symbol, interval])

  return (
    <div className="tradingview-widget-container">
      <div id="tradingview_chart" ref={container} className="rounded-lg overflow-hidden" />
    </div>
  )
}

export default TradingViewChart
