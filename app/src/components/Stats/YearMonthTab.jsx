import { useState, useMemo, useEffect } from 'react'
import { PhotoGrid } from '../PhotoGrid'

export function YearMonthTab({ entries, onClickEntry }) {
  const availableYears = useMemo(() => {
    const years = [...new Set(entries.map(e => e.date.slice(0, 4)))].sort().reverse()
    return years
  }, [entries])

  const currentYear = String(new Date().getFullYear())
  const [selectedYear, setSelectedYear] = useState('')

  useEffect(() => {
    if (availableYears.length === 0) return
    setSelectedYear(prev =>
      prev && availableYears.includes(prev)
        ? prev
        : availableYears.includes(currentYear) ? currentYear : availableYears[0]
    )
  }, [availableYears, currentYear])

  const yearStats = useMemo(() => {
    const counts = {}
    entries.forEach(e => {
      const y = e.date.slice(0, 4)
      counts[y] = (counts[y] || 0) + 1
    })
    return Object.entries(counts).sort(([a], [b]) => a.localeCompare(b))
  }, [entries])

  const monthlyGroups = useMemo(() => {
    const photoEntries = entries.filter(e => e.photo_path && e.date.slice(0, 4) === selectedYear)
    const groups = {}
    photoEntries.forEach(e => {
      const m = e.date.slice(0, 7)
      if (!groups[m]) groups[m] = []
      groups[m].push(e)
    })
    return Object.entries(groups).sort(([a], [b]) => b.localeCompare(a))
  }, [entries, selectedYear])

  return (
    <div>
      <table className="stats-table">
        <thead>
          <tr>
            <th>年</th>
            <th>回数</th>
          </tr>
        </thead>
        <tbody>
          {yearStats.map(([year, count]) => (
            <tr key={year}>
              <td>{year}</td>
              <td style={{ color: 'var(--gold-light)', fontWeight: 700 }}>{count}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <select
        className="year-select"
        value={selectedYear}
        onChange={e => setSelectedYear(e.target.value)}
      >
        {availableYears.map(y => <option key={y} value={y}>{y}年</option>)}
      </select>

      {monthlyGroups.length === 0 && (
        <p style={{ color: 'var(--muted)', fontSize: '0.875rem' }}>該当する写真がありません。</p>
      )}
      {monthlyGroups.map(([month, monthEntries]) => (
        <div key={month}>
          <p className="group-label">{parseInt(month.slice(5))}月 · {monthEntries.length}件</p>
          <PhotoGrid entries={monthEntries} onClickEntry={onClickEntry} />
        </div>
      ))}
    </div>
  )
}
