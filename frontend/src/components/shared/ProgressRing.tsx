interface ProgressRingProps {
  value: number     // 0-100
  size?: number
  strokeWidth?: number
  color?: string
  label?: string
  sublabel?: string
}

export function ProgressRing({
  value,
  size = 80,
  strokeWidth = 8,
  color = '#6366f1',
  label,
  sublabel,
}: ProgressRingProps) {
  const radius = (size - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius
  const strokeDashoffset = circumference - (value / 100) * circumference

  return (
    <div className="relative inline-flex items-center justify-center">
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#e5e7eb"
          strokeWidth={strokeWidth}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset 0.5s ease' }}
        />
      </svg>
      <div className="absolute flex flex-col items-center justify-center">
        {label ? (
          <>
            <span className="text-sm font-semibold text-gray-900">{label}</span>
            {sublabel && <span className="text-xs text-gray-500">{sublabel}</span>}
          </>
        ) : (
          <span className="text-sm font-semibold text-gray-900">{Math.round(value)}%</span>
        )}
      </div>
    </div>
  )
}
