import React, { useState, useEffect } from 'react'

// ==================== TYPE DEFINITIONS ====================

interface Prediction {
  cycleHour: number
  predictionType: 'up' | 'down'
  confidence: number
  createdAt: string
}

interface Cycle {
  id: string
  cycleStart: string
  cycleEnd: string
  status: 'active' | 'completed'
  predictions: Array<Prediction | null>
}

interface PredictionTimelineProps {
  cycle: Cycle | null
}

// ==================== UTILITY FUNCTIONS ====================

const formatTime = (isoString: string): string => {
  const date = new Date(isoString)
  return date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
  })
}

const calculateProgress = (start: string, end: string): number => {
  const now = Date.now()
  const startTime = new Date(start).getTime()
  const endTime = new Date(end).getTime()
  
  if (now < startTime) return 0
  if (now > endTime) return 100
  
  const elapsed = now - startTime
  const total = endTime - startTime
  return Math.round((elapsed / total) * 100)
}

const calculateRemainingTime = (end: string): string => {
  const now = Date.now()
  const endTime = new Date(end).getTime()
  const remaining = endTime - now
  
  if (remaining <= 0) return 'Completed'
  
  const hours = Math.floor(remaining / (1000 * 60 * 60))
  const minutes = Math.floor((remaining % (1000 * 60 * 60)) / (1000 * 60))
  const seconds = Math.floor((remaining % (1000 * 60)) / 1000)
  
  if (hours > 0) return `${hours}h ${minutes}m remaining`
  if (minutes > 0) return `${minutes}m ${seconds}s remaining`
  return `${seconds}s remaining`
}

const getPredictionStatus = (
  prediction: Prediction | null,
  currentHour: number,
  cycleProgress: number
): 'completed' | 'pending' | 'generating' | 'error' => {
  if (!prediction) {
    // If we're past this hour and still no prediction, it's an error
    const hourEndProgress = (currentHour / 4) * 100
    if (cycleProgress > hourEndProgress + 5) return 'error' // 5% buffer
    
    // If we're in this hour's window, it's generating
    const hourStartProgress = ((currentHour - 1) / 4) * 100
    if (cycleProgress >= hourStartProgress && cycleProgress <= hourEndProgress) {
      return 'generating'
    }
    
    return 'pending'
  }
  return 'completed'
}

// ==================== SUB-COMPONENTS ====================

const PredictionSlot: React.FC<{
  hour: number
  prediction: Prediction | null
  status: 'completed' | 'pending' | 'generating' | 'error'
}> = ({ hour, prediction, status }) => {
  const [showTooltip, setShowTooltip] = useState(false)
  
  const getStatusIcon = (): string => {
    switch (status) {
      case 'completed': return '✓'
      case 'pending': return '○'
      case 'generating': return '⏳'
      case 'error': return '⚠️'
    }
  }
  
  const getStatusColor = (): string => {
    switch (status) {
      case 'completed': return 'bg-gray-800 border-gray-600'
      case 'pending': return 'bg-gray-900/50 border-gray-700'
      case 'generating': return 'bg-blue-900/20 border-blue-600 animate-pulse'
      case 'error': return 'bg-red-900/20 border-red-600'
    }
  }
  
  const getPredictionColor = (type: 'up' | 'down'): string => {
    return type === 'up' ? 'text-green-400' : 'text-red-400'
  }
  
  return (
    <div className="relative flex-1 min-w-0">
      <div
        className={`relative rounded-lg border-2 p-4 transition-all duration-300 ${getStatusColor()}`}
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
      >
        {/* Hour Number */}
        <div className="text-center mb-2">
          <span className="text-xs text-gray-500 font-medium">Hour {hour}</span>
        </div>
        
        {/* Status Icon */}
        <div className="text-center mb-2">
          <span className="text-2xl">{getStatusIcon()}</span>
        </div>
        
        {/* Prediction Details */}
        {status === 'completed' && prediction && (
          <>
            {/* Direction Arrow */}
            <div className={`text-center mb-1 ${getPredictionColor(prediction.predictionType)}`}>
              <span className="text-3xl font-bold">
                {prediction.predictionType === 'up' ? '↑' : '↓'}
              </span>
              <div className="text-xs font-semibold uppercase mt-1">
                {prediction.predictionType}
              </div>
            </div>
            
            {/* Confidence */}
            <div className="text-center">
              <div className="text-sm font-bold text-white">
                {Math.round(prediction.confidence * 100)}%
              </div>
              <div className="text-xs text-gray-500">confidence</div>
            </div>
          </>
        )}
        
        {status === 'pending' && (
          <div className="text-center text-gray-600 text-sm py-2">
            Waiting...
          </div>
        )}
        
        {status === 'generating' && (
          <div className="text-center text-blue-400 text-sm py-2">
            <div className="animate-pulse">Analyzing...</div>
          </div>
        )}
        
        {status === 'error' && (
          <div className="text-center text-red-400 text-sm py-2">
            Failed
          </div>
        )}
        
        {/* Tooltip */}
        {showTooltip && prediction && (
          <div className="absolute z-10 bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg shadow-xl text-xs whitespace-nowrap">
            <div className="text-gray-400">Generated at:</div>
            <div className="text-white font-mono">{formatTime(prediction.createdAt)}</div>
            <div className="absolute top-full left-1/2 transform -translate-x-1/2 -mt-1">
              <div className="border-4 border-transparent border-t-gray-900"></div>
            </div>
          </div>
        )}
      </div>
      
      {/* Connector Line */}
      {hour < 4 && (
        <div className="absolute top-1/2 left-full w-4 h-0.5 bg-gray-700 transform -translate-y-1/2 hidden md:block" />
      )}
    </div>
  )
}

const ProgressBar: React.FC<{ progress: number }> = ({ progress }) => {
  return (
    <div className="w-full">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-gray-400">Cycle Progress</span>
        <span className="text-sm font-bold text-white">{progress}%</span>
      </div>
      <div className="w-full bg-gray-800 rounded-full h-3 overflow-hidden">
        <div
          className="bg-gradient-to-r from-blue-500 via-purple-500 to-pink-500 h-full transition-all duration-1000 ease-out rounded-full"
          style={{ width: `${progress}%` }}
        >
          <div className="h-full w-full bg-gradient-to-r from-transparent via-white to-transparent opacity-30 animate-shimmer" />
        </div>
      </div>
    </div>
  )
}

// ==================== MAIN COMPONENT ====================

const PredictionTimeline: React.FC<PredictionTimelineProps> = ({ cycle }) => {
  const [currentTime, setCurrentTime] = useState(Date.now())
  
  // Update current time every second for real-time countdown
  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentTime(Date.now())
    }, 1000)
    
    return () => clearInterval(interval)
  }, [])
  
  // Empty state - no active cycle
  if (!cycle) {
    return (
      <div className="card p-6">
        <h3 className="text-xl font-bold text-white mb-4">Prediction Timeline</h3>
        <div className="text-center py-12 space-y-4">
          <div className="text-6xl mb-4">📊</div>
          <p className="text-gray-400">No active prediction cycle</p>
          <p className="text-sm text-gray-500">
            The automated trading system will generate a new 4-hour cycle soon
          </p>
        </div>
      </div>
    )
  }
  
  const progress = calculateProgress(cycle.cycleStart, cycle.cycleEnd)
  const remainingTime = calculateRemainingTime(cycle.cycleEnd)
  
  // Ensure predictions array has exactly 4 slots
  const predictions: Array<Prediction | null> = Array(4)
    .fill(null)
    .map((_, idx) => cycle.predictions[idx] || null)
  
  return (
    <div className="card p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-xl font-bold text-white">Prediction Timeline</h3>
        <div className="flex items-center space-x-2">
          <span className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold ${
            cycle.status === 'active' 
              ? 'bg-green-900/30 text-green-400 border border-green-700' 
              : 'bg-gray-900/30 text-gray-400 border border-gray-700'
          }`}>
            {cycle.status === 'active' ? '🟢 Active' : '⚫ Completed'}
          </span>
        </div>
      </div>
      
      {/* Cycle Info */}
      <div className="bg-gradient-to-r from-blue-900/20 via-purple-900/20 to-pink-900/20 border border-gray-700 rounded-lg p-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
          <div>
            <div className="text-gray-400 mb-1">Cycle Start</div>
            <div className="text-white font-mono">{formatTime(cycle.cycleStart)}</div>
          </div>
          <div>
            <div className="text-gray-400 mb-1">Cycle End</div>
            <div className="text-white font-mono">{formatTime(cycle.cycleEnd)}</div>
          </div>
          <div>
            <div className="text-gray-400 mb-1">Remaining</div>
            <div className="text-white font-semibold">{remainingTime}</div>
          </div>
        </div>
      </div>
      
      {/* Progress Bar */}
      <ProgressBar progress={progress} />
      
      {/* Timeline Slots - Horizontal on Desktop, Vertical on Mobile */}
      <div className="space-y-4">
        <div className="text-sm font-medium text-gray-400 mb-4">
          4-Hour Prediction Cycle
        </div>
        
        {/* Desktop Layout - Horizontal */}
        <div className="hidden md:flex items-center space-x-4">
          {predictions.map((prediction, idx) => {
            const hour = idx + 1
            const status = getPredictionStatus(prediction, hour, progress)
            return (
              <PredictionSlot
                key={hour}
                hour={hour}
                prediction={prediction}
                status={status}
              />
            )
          })}
        </div>
        
        {/* Mobile Layout - Vertical */}
        <div className="flex md:hidden flex-col space-y-3">
          {predictions.map((prediction, idx) => {
            const hour = idx + 1
            const status = getPredictionStatus(prediction, hour, progress)
            return (
              <PredictionSlot
                key={hour}
                hour={hour}
                prediction={prediction}
                status={status}
              />
            )
          })}
        </div>
      </div>
      
      {/* Cycle ID Footer */}
      <div className="pt-4 border-t border-gray-700 text-xs text-gray-500 text-center">
        Cycle ID: <span className="font-mono text-gray-400">{cycle.id}</span>
      </div>
    </div>
  )
}

// ==================== STYLES (for shimmer animation) ====================
// Add this to your global CSS or Tailwind config:
// @keyframes shimmer {
//   0% { transform: translateX(-100%); }
//   100% { transform: translateX(100%); }
// }
// .animate-shimmer {
//   animation: shimmer 2s infinite;
// }

export default PredictionTimeline
