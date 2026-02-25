import React from 'react'

function CalibrationBadge({ stated, actual }) {
  if (stated === undefined || actual === undefined) {
    return null
  }

  const statedPercent = stated * 100
  const actualPercent = actual * 100
  const diff = actualPercent - statedPercent

  let status, color, bgColor
  if (Math.abs(diff) <= 5) {
    status = 'Calibrated'
    color = 'text-green-400'
    bgColor = 'bg-green-900/30 border-green-700'
  } else if (diff > 5) {
    status = 'Underconfident'
    color = 'text-blue-400'
    bgColor = 'bg-blue-900/30 border-blue-700'
  } else {
    status = 'Overconfident'
    color = 'text-yellow-400'
    bgColor = 'bg-yellow-900/30 border-yellow-700'
  }

  return (
    <div className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ${bgColor}`}>
      <span className={color}>{status}</span>
    </div>
  )
}

export default CalibrationBadge
