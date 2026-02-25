import React, { useState } from 'react';

interface FourHourDecisionProps {
  decision: {
    finalDecision: 'up' | 'down';
    aggregatedConfidence: number;
    voteBreakdown: {
      upCount: number;
      downCount: number;
      upWeighted: number;
      downWeighted: number;
    };
    confidenceStats: {
      min: number;
      max: number;
      avg: number;
      stdDev: number;
    };
    decisionReasoning: string;
    createdAt: string;
  } | null;
  loading?: boolean;
}

const FourHourDecision: React.FC<FourHourDecisionProps> = ({ decision, loading = false }) => {
  const [showFullReasoning, setShowFullReasoning] = useState(false);

  // Loading state
  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow-lg p-8 animate-pulse">
        <div className="h-32 bg-gray-200 rounded mb-4"></div>
        <div className="h-20 bg-gray-200 rounded mb-4"></div>
        <div className="h-16 bg-gray-200 rounded"></div>
      </div>
    );
  }

  // Empty state - waiting for predictions
  if (!decision) {
    return (
      <div className="bg-white rounded-lg shadow-lg p-8 border-2 border-dashed border-gray-300">
        <div className="text-center">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-gray-100 rounded-full mb-4">
            <svg className="w-8 h-8 text-gray-400 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
          </div>
          <h3 className="text-xl font-semibold text-gray-700 mb-2">Waiting for 4 predictions to complete...</h3>
          <p className="text-gray-500">The 4-hour aggregated decision will appear once all predictions are ready.</p>
        </div>
      </div>
    );
  }

  // Calculate time ago
  const getTimeAgo = (timestamp: string): string => {
    const now = new Date();
    const created = new Date(timestamp);
    const diffMs = now.getTime() - created.getTime();
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffMins = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));

    if (diffHours > 0) {
      return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
    }
    return `${diffMins} minute${diffMins > 1 ? 's' : ''} ago`;
  };

  // Get confidence color
  const getConfidenceColor = (confidence: number): string => {
    if (confidence >= 70) return 'text-green-600';
    if (confidence >= 50) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getConfidenceBgColor = (confidence: number): string => {
    if (confidence >= 70) return 'bg-green-100 border-green-300';
    if (confidence >= 50) return 'bg-yellow-100 border-yellow-300';
    return 'bg-red-100 border-red-300';
  };

  const getConfidenceRingColor = (confidence: number): string => {
    if (confidence >= 70) return 'stroke-green-600';
    if (confidence >= 50) return 'stroke-yellow-600';
    return 'stroke-red-600';
  };

  // Decision colors
  const isUp = decision.finalDecision === 'up';
  const decisionColor = isUp ? 'text-green-600' : 'text-red-600';
  const decisionBgColor = isUp ? 'bg-green-50 border-green-300' : 'bg-red-50 border-red-300';
  const decisionIcon = isUp ? '↑' : '↓';
  const decisionText = isUp ? 'UP' : 'DOWN';

  // Truncate reasoning
  const reasoningPreview = decision.decisionReasoning.length > 200 
    ? decision.decisionReasoning.substring(0, 200) + '...' 
    : decision.decisionReasoning;

  // Calculate circle progress (SVG circle circumference = 2πr, r=45)
  const radius = 45;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (decision.aggregatedConfidence / 100) * circumference;

  return (
    <div className="bg-white rounded-lg shadow-lg p-8 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-gray-800">4-Hour Aggregated Decision</h2>
        <span className="text-sm text-gray-500">
          Decision made {getTimeAgo(decision.createdAt)}
        </span>
      </div>

      {/* Main Decision Display */}
      <div className={`${decisionBgColor} border-2 rounded-xl p-8 mb-6 animate-scale-in`}>
        <div className="flex items-center justify-center gap-8">
          {/* Decision Icon */}
          <div className="text-center">
            <div className={`${decisionColor} text-8xl font-bold mb-2 animate-bounce-subtle`}>
              {decisionIcon}
            </div>
            <div className={`${decisionColor} text-5xl font-extrabold tracking-wider`}>
              {decisionText}
            </div>
          </div>

          {/* Confidence Ring */}
          <div className="relative">
            <svg className="w-32 h-32 transform -rotate-90">
              {/* Background circle */}
              <circle
                cx="64"
                cy="64"
                r={radius}
                stroke="currentColor"
                strokeWidth="8"
                fill="none"
                className="text-gray-200"
              />
              {/* Progress circle */}
              <circle
                cx="64"
                cy="64"
                r={radius}
                stroke="currentColor"
                strokeWidth="8"
                fill="none"
                strokeDasharray={circumference}
                strokeDashoffset={offset}
                className={`${getConfidenceRingColor(decision.aggregatedConfidence)} transition-all duration-1000 ease-out`}
                strokeLinecap="round"
              />
            </svg>
            {/* Confidence percentage */}
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center">
                <div className={`text-3xl font-bold ${getConfidenceColor(decision.aggregatedConfidence)}`}>
                  {decision.aggregatedConfidence.toFixed(1)}%
                </div>
                <div className="text-xs text-gray-500">confidence</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Vote Breakdown */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
          <h4 className="text-sm font-semibold text-gray-600 mb-2">Vote Count</h4>
          <div className="flex items-center justify-between">
            <span className="text-green-600 font-bold text-lg">
              {decision.voteBreakdown.upCount} UP
            </span>
            <span className="text-gray-400">|</span>
            <span className="text-red-600 font-bold text-lg">
              {decision.voteBreakdown.downCount} DOWN
            </span>
          </div>
        </div>

        <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
          <h4 className="text-sm font-semibold text-gray-600 mb-2">Weighted Scores</h4>
          <div className="flex items-center justify-between">
            <span className="text-green-600 font-bold text-lg">
              {decision.voteBreakdown.upWeighted.toFixed(2)}
            </span>
            <span className="text-gray-400">|</span>
            <span className="text-red-600 font-bold text-lg">
              {decision.voteBreakdown.downWeighted.toFixed(2)}
            </span>
          </div>
        </div>
      </div>

      {/* Confidence Statistics */}
      <div className="mb-6">
        <h4 className="text-sm font-semibold text-gray-700 mb-3">Confidence Statistics</h4>
        <div className="grid grid-cols-4 gap-3">
          <div className="bg-blue-50 rounded-lg p-3 border border-blue-200">
            <div className="text-xs text-blue-600 font-semibold mb-1">MIN</div>
            <div className="text-xl font-bold text-blue-700">{decision.confidenceStats.min.toFixed(1)}%</div>
          </div>
          <div className="bg-purple-50 rounded-lg p-3 border border-purple-200">
            <div className="text-xs text-purple-600 font-semibold mb-1">MAX</div>
            <div className="text-xl font-bold text-purple-700">{decision.confidenceStats.max.toFixed(1)}%</div>
          </div>
          <div className="bg-indigo-50 rounded-lg p-3 border border-indigo-200">
            <div className="text-xs text-indigo-600 font-semibold mb-1">AVG</div>
            <div className="text-xl font-bold text-indigo-700">{decision.confidenceStats.avg.toFixed(1)}%</div>
          </div>
          <div className="bg-cyan-50 rounded-lg p-3 border border-cyan-200">
            <div className="text-xs text-cyan-600 font-semibold mb-1">STD DEV</div>
            <div className="text-xl font-bold text-cyan-700">{decision.confidenceStats.stdDev.toFixed(1)}%</div>
          </div>
        </div>
      </div>

      {/* Decision Reasoning */}
      <div className={`${getConfidenceBgColor(decision.aggregatedConfidence)} border rounded-lg p-4`}>
        <h4 className="text-sm font-semibold text-gray-700 mb-2">Decision Reasoning</h4>
        <p className="text-gray-700 text-sm leading-relaxed whitespace-pre-wrap">
          {showFullReasoning ? decision.decisionReasoning : reasoningPreview}
        </p>
        {decision.decisionReasoning.length > 200 && (
          <button
            onClick={() => setShowFullReasoning(!showFullReasoning)}
            className="mt-3 text-sm font-semibold text-blue-600 hover:text-blue-700 transition-colors"
          >
            {showFullReasoning ? '← Show less' : 'Show more →'}
          </button>
        )}
      </div>
    </div>
  );
};

// Add custom animations to tailwind
const styles = `
@keyframes fade-in {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@keyframes scale-in {
  from {
    transform: scale(0.95);
    opacity: 0;
  }
  to {
    transform: scale(1);
    opacity: 1;
  }
}

@keyframes bounce-subtle {
  0%, 100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-10px);
  }
}

.animate-fade-in {
  animation: fade-in 0.5s ease-out;
}

.animate-scale-in {
  animation: scale-in 0.6s ease-out;
}

.animate-bounce-subtle {
  animation: bounce-subtle 2s ease-in-out infinite;
}
`;

export default FourHourDecision;
