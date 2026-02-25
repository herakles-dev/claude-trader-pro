import React from 'react'

const tabs = [
  { id: 'overview', label: 'Overview', icon: '📊' },
  { id: 'patterns', label: 'Patterns', icon: '🎯' },
  { id: 'conditions', label: 'Conditions', icon: '📈' },
  { id: 'calibration', label: 'Calibration', icon: '🎚️' },
  { id: 'trading', label: 'Trading', icon: '💹' },
]

function AnalyticsTabs({ activeTab, onTabChange }) {
  return (
    <div className="border-b border-gray-700 mb-6">
      <nav className="flex space-x-1 overflow-x-auto pb-px" aria-label="Analytics tabs">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => onTabChange(tab.id)}
            className={`
              flex items-center space-x-2 px-4 py-3 text-sm font-medium rounded-t-lg
              transition-colors duration-200 whitespace-nowrap
              ${activeTab === tab.id
                ? 'bg-gray-800 text-white border-b-2 border-blue-500'
                : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'
              }
            `}
            aria-current={activeTab === tab.id ? 'page' : undefined}
          >
            <span>{tab.icon}</span>
            <span>{tab.label}</span>
          </button>
        ))}
      </nav>
    </div>
  )
}

export default AnalyticsTabs
