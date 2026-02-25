import React from 'react'

const getGradeStyle = (grade) => {
  if (!grade) return { color: 'text-gray-400', bg: 'bg-gray-700' }
  const letter = grade.charAt(0).toUpperCase()
  switch (letter) {
    case 'A':
      return { color: 'text-green-400', bg: 'bg-green-900/50' }
    case 'B':
      return { color: 'text-blue-400', bg: 'bg-blue-900/50' }
    case 'C':
      return { color: 'text-yellow-400', bg: 'bg-yellow-900/50' }
    case 'D':
    case 'F':
      return { color: 'text-red-400', bg: 'bg-red-900/50' }
    default:
      return { color: 'text-gray-400', bg: 'bg-gray-700' }
  }
}

function PatternIndicator({ name, grade, accuracy, compact = false }) {
  if (!name) return null

  const style = getGradeStyle(grade)

  if (compact) {
    return (
      <div className="flex items-center space-x-2">
        <span className="text-gray-300 text-sm">{name}</span>
        {grade && (
          <span className={`px-1.5 py-0.5 rounded text-xs font-bold ${style.bg} ${style.color}`}>
            {grade}
          </span>
        )}
      </div>
    )
  }

  return (
    <div className="bg-gray-900/50 rounded-lg p-3 space-y-1">
      <div className="flex items-center justify-between">
        <span className="text-sm text-gray-300 font-medium">{name}</span>
        {grade && (
          <span className={`px-2 py-0.5 rounded text-xs font-bold ${style.bg} ${style.color}`}>
            {grade}
          </span>
        )}
      </div>
      {accuracy !== undefined && (
        <div className="text-xs text-gray-500">
          {(accuracy * 100).toFixed(0)}% historical accuracy
        </div>
      )}
    </div>
  )
}

export default PatternIndicator
