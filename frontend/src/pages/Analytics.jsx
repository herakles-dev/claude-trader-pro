import React, { useState } from 'react'
import {
  AnalyticsTabs,
  OverviewTab,
  PatternsTab,
  ConditionsTab,
  CalibrationTab,
  TradingTab,
} from '../components/analytics'

function Analytics() {
  const [activeTab, setActiveTab] = useState('overview')
  const [timeRange, setTimeRange] = useState('30d')

  const timeRanges = [
    { label: '7d', value: '7d' },
    { label: '30d', value: '30d' },
    { label: '90d', value: '90d' },
    { label: 'All', value: 'all' },
  ]

  const renderTabContent = () => {
    switch (activeTab) {
      case 'overview':
        return <OverviewTab timeRange={timeRange} />
      case 'patterns':
        return <PatternsTab timeRange={timeRange} />
      case 'conditions':
        return <ConditionsTab timeRange={timeRange} />
      case 'calibration':
        return <CalibrationTab timeRange={timeRange} />
      case 'trading':
        return <TradingTab timeRange={timeRange} />
      default:
        return <OverviewTab timeRange={timeRange} />
    }
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between space-y-4 sm:space-y-0">
        <div>
          <h1 className="text-3xl font-bold text-white">Analytics Dashboard</h1>
          <p className="text-gray-400 mt-1">
            Performance metrics, patterns, and insights
          </p>
        </div>

        {/* Time Range Selector */}
        <div className="flex items-center space-x-2">
          {timeRanges.map((range) => (
            <button
              key={range.value}
              onClick={() => setTimeRange(range.value)}
              className={`px-4 py-2 rounded-lg font-medium transition-colors duration-200 ${
                timeRange === range.value
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
              }`}
            >
              {range.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab Navigation */}
      <AnalyticsTabs activeTab={activeTab} onTabChange={setActiveTab} />

      {/* Tab Content */}
      {renderTabContent()}
    </div>
  )
}

export default Analytics
