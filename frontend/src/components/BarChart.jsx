import { useEffect, useRef, useState } from 'react'
import { formatCompact } from '../lib/format'

const HEIGHT = 220
const MARGIN = { top: 12, right: 8, bottom: 28, left: 44 }
const MAX_BAR = 24
const RADIUS = 4

// Round the axis to clean numbers: 0, 2.5K, 5K, 7.5K, 10K
function niceTicks(max, count = 4) {
  if (max <= 0) return [0, 250, 500, 750, 1000]
  const raw = max / count
  const power = 10 ** Math.floor(Math.log10(raw))
  const n = raw / power
  const step = (n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10) * power
  return Array.from({ length: count + 1 }, (_, i) => i * step)
}

// A bar with a rounded top and a square bottom on the baseline
function barPath(x, y, width, height) {
  const r = Math.min(RADIUS, width / 2, height)
  const base = y + height
  return `M${x},${base} V${y + r} Q${x},${y} ${x + r},${y} H${x + width - r} Q${x + width},${y} ${x + width},${y + r} V${base} Z`
}

/**
 * Single-series column chart with hover/tap tooltip.
 * data: [{ key, label, tooltipLabel, value }]
 */
export default function BarChart({ data, formatValue, ariaLabel }) {
  const containerRef = useRef(null)
  const [width, setWidth] = useState(0)
  const [active, setActive] = useState(null)

  useEffect(() => {
    const element = containerRef.current
    if (!element) return
    // Measure now, then again whenever the size changes (e.g. phone rotated)
    setWidth(element.getBoundingClientRect().width)
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width))
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  const innerWidth = Math.max(width - MARGIN.left - MARGIN.right, 0)
  const innerHeight = HEIGHT - MARGIN.top - MARGIN.bottom
  const ticks = niceTicks(Math.max(...data.map((d) => d.value), 0))
  const top = ticks[ticks.length - 1]
  const slot = data.length ? innerWidth / data.length : 0
  const barWidth = Math.max(Math.min(MAX_BAR, slot * 0.6), 1)
  // Show only as many x labels as fit (about one per 48px)
  const labelEvery = Math.max(1, Math.ceil(data.length / Math.max(1, Math.floor(innerWidth / 48))))
  const y = (value) => MARGIN.top + innerHeight - (value / top) * innerHeight
  const activeItem = active !== null ? data[active] : null

  return (
    <div ref={containerRef} className="relative w-full select-none" onMouseLeave={() => setActive(null)}>
      {width > 0 && (
        <svg width={width} height={HEIGHT} role="img" aria-label={ariaLabel}>
          {ticks.map((tick) => (
            <g key={tick}>
              <line
                x1={MARGIN.left}
                x2={width - MARGIN.right}
                y1={y(tick)}
                y2={y(tick)}
                stroke={tick === 0 ? 'var(--line-strong)' : 'var(--line)'}
                strokeWidth="1"
              />
              <text x={MARGIN.left - 8} y={y(tick)} dy="0.32em" textAnchor="end" className="tabular fill-muted text-[11px]">
                {formatCompact(tick)}
              </text>
            </g>
          ))}

          {data.map((d, i) => {
            const x = MARGIN.left + i * slot
            const barHeight = Math.max(((d.value || 0) / top) * innerHeight, 0)
            return (
              <g key={d.key}>
                {active === i && (
                  <rect x={x} y={MARGIN.top} width={slot} height={innerHeight} fill="var(--soft)" />
                )}
                {barHeight > 0 && (
                  <path d={barPath(x + (slot - barWidth) / 2, y(d.value), barWidth, barHeight)} fill="var(--chart-1)" />
                )}
                {i % labelEvery === 0 && (
                  <text x={x + slot / 2} y={HEIGHT - 8} textAnchor="middle" className="fill-muted text-[11px]">
                    {d.label}
                  </text>
                )}
                {/* Invisible, larger target so hovering or tapping is easy */}
                <rect
                  x={x}
                  y={MARGIN.top}
                  width={slot}
                  height={innerHeight}
                  fill="transparent"
                  onMouseEnter={() => setActive(i)}
                  onClick={() => setActive(i)}
                />
              </g>
            )
          })}
        </svg>
      )}

      {activeItem && (
        <div
          className="pointer-events-none absolute z-10 -translate-x-1/2 rounded-lg border border-line bg-card px-3 py-2 text-xs shadow-lg"
          style={{
            left: Math.min(Math.max(MARGIN.left + active * slot + slot / 2, 70), width - 70),
            top: Math.max(y(activeItem.value) - 56, 0),
          }}
        >
          <p className="whitespace-nowrap text-ink-2">{activeItem.tooltipLabel || activeItem.label}</p>
          <p className="whitespace-nowrap font-semibold text-ink">{formatValue(activeItem.value)}</p>
        </div>
      )}
    </div>
  )
}
