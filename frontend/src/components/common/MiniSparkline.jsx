import React from 'react'

function MiniSparkline({ data = [], color = '#22c55e', height = 30, width = 100 }) {
  if (!data || data.length === 0) {
    return (
      <div className="h-8 flex items-center justify-center text-gray-600 text-xs">
        No data
      </div>
    )
  }

  // Normalize data if it's an array of objects
  const values = data.map(d => (typeof d === 'object' ? d.value || d.pnl || 0 : d))

  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1

  // Generate SVG path
  const padding = 2
  const effectiveHeight = height - padding * 2
  const effectiveWidth = width - padding * 2

  const points = values.map((value, index) => {
    const x = padding + (index / (values.length - 1)) * effectiveWidth
    const y = padding + effectiveHeight - ((value - min) / range) * effectiveHeight
    return `${x},${y}`
  })

  const pathD = `M ${points.join(' L ')}`

  // Determine color based on trend (last value vs first value)
  const trendColor = values[values.length - 1] >= values[0] ? '#22c55e' : '#ef4444'
  const lineColor = color === 'auto' ? trendColor : color

  return (
    <svg width={width} height={height} className="inline-block">
      <path
        d={pathD}
        fill="none"
        stroke={lineColor}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* End point dot */}
      <circle
        cx={padding + effectiveWidth}
        cy={padding + effectiveHeight - ((values[values.length - 1] - min) / range) * effectiveHeight}
        r="3"
        fill={lineColor}
      />
    </svg>
  )
}

export default MiniSparkline
